"""The exact filing reader binds one canonical receipt to its profile and work unit."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from ....core.operations import OperationEffect, profile_operation_subject
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.modelos.filing_record import (
    AeatConfirmationState,
    FilingDeclarationKind,
    FilingOrigin,
    ModeloRecord,
    ModeloRecordCatalogue,
    derive_filing_record_id,
)
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, WorkUnitState, derive_work_unit_id
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationRequest
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_contracts import AccessAction, AccessDenialCode, Availability, OperationAccessRequest
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..amendment_context_operation import (
    MODELO_WORK_AMENDMENT_CONTEXT_OPERATION_DEFINITION_ID,
    ModeloWorkAmendmentContextRequest,
    build_modelo_work_amendment_context_definition,
    build_modelo_work_amendment_context_registration,
)
from ..filing_projection import ModeloFilingRecordSnapshot
from ..filing_selection_operation import (
    MODELO_WORK_FILING_RECORD_OPERATION_DEFINITION_ID,
    ModeloWorkFilingRecordProjection,
    ModeloWorkFilingRecordRequest,
    build_modelo_work_filing_record_definition,
    build_modelo_work_filing_record_registration,
)
from ..metadata_projection import ModeloWorkMetadataSnapshot
from ..verification_repository_ports import VerificationRepositoryBundle

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_CALCULATION_REVISION_ID = "a" * 64
_NOW = datetime(2026, 4, 10, 9, 0, tzinfo=UTC)
_RESULT_REFERENCE = "f" * 64
_ACTOR = "gestoria source"


def _source() -> tuple[WorkUnit, ModeloRecord]:
    """Build a valid filing receipt whose profile and period match its unit."""
    period = Period.from_year_and_code(2026, "1T")
    unit_id = derive_work_unit_id(
        bucket_id=str(_PROFILE), modelo="303", filing_year=2026, period=period, revision_id="test-revision"
    )
    filing_id = derive_filing_record_id(
        work_unit_id=unit_id,
        calculation_revision_id=_CALCULATION_REVISION_ID,
        filed_by=_ACTOR,
    )
    unit = WorkUnit(
        work_unit_id=unit_id,
        bucket_id=str(_PROFILE),
        modelo="303",
        filing_year=2026,
        period=period,
        revision_id="test-revision",
        name="First-quarter return",
        created_at=_NOW,
        updated_at=_NOW,
        state=WorkUnitState.BORRADOR,
        current_calculation_revision_id=_CALCULATION_REVISION_ID,
        filed_calculation_revision_id=_CALCULATION_REVISION_ID,
        current_filing_record_id=filing_id,
    )
    record = ModeloRecord(
        filing_record_id=filing_id,
        work_unit_id=unit_id,
        calculation_revision_id=_CALCULATION_REVISION_ID,
        bucket_id=str(_PROFILE),
        modelo="303",
        filing_year=2026,
        period=period,
        filed_at=_NOW,
        filed_by=_ACTOR,
        origin=FilingOrigin.LOCAL,
        confirmation=AeatConfirmationState.PENDIENTE,
        declaration_kind=FilingDeclarationKind.ORIGINAL,
    )
    return unit, record


class _Repository:
    def __init__(self, *, bucket_id: str, catalogue: BaseModel) -> None:
        self.bucket_id = bucket_id
        self._catalogue = catalogue

    def load(self) -> BaseModel:
        return self._catalogue


def _bundle(
    *,
    unit: WorkUnit | None = None,
    record: ModeloRecord | None = None,
    work_bucket_id: str | None = None,
    filing_bucket_id: str | None = None,
) -> VerificationRepositoryBundle:
    """Supply only the two read ports used by this reader; no report port exists."""
    source_unit, source_record = _source()
    resolved_unit = unit or source_unit
    resolved_record = record or source_record
    bundle = SimpleNamespace(
        work_unit=_Repository(
            bucket_id=work_bucket_id or str(_PROFILE),
            catalogue=WorkUnitCatalogue(work_units={resolved_unit.work_unit_id: resolved_unit}),
        ),
        filing=_Repository(
            bucket_id=filing_bucket_id or str(_PROFILE),
            catalogue=ModeloRecordCatalogue(records={resolved_record.filing_record_id: resolved_record}),
        ),
    )
    return cast(VerificationRepositoryBundle, cast(object, bundle))


def _build(bundle: VerificationRepositoryBundle):
    def factory(profile_id: str, *, operation: PinnedAuthorityOperation) -> VerificationRepositoryBundle:
        assert profile_id == str(_PROFILE)
        assert isinstance(operation, PinnedAuthorityOperation)
        return bundle

    definition = build_modelo_work_filing_record_definition(factory)
    registration = build_modelo_work_filing_record_registration(definition, factory)
    return definition, registration, OperationRegistry(definitions=(definition,), public_registrations=(registration,))


def _request(record: ModeloRecord, *, profile_id: UUID = _PROFILE) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=MODELO_WORK_FILING_RECORD_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        payload=ModeloWorkFilingRecordRequest(profile_id=profile_id, filing_record_id=record.filing_record_id),
    )


def _access_context(
    registration, *, operation: PinnedAuthorityOperation | None, profile_id: UUID = _PROFILE
) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=profile_id,
        destination_id=uuid4(),
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
        authority_operation=operation,
    )


@pytest.mark.parametrize("kind", ["filing", "amendment"])
def test_fresh_filing_reads_refuse_missing_pin_before_repository_creation(kind: str) -> None:
    unit, record = _source()
    calls = 0

    def unavailable_factory(_bucket_id: str, *, operation: PinnedAuthorityOperation) -> VerificationRepositoryBundle:
        nonlocal calls
        calls += 1
        raise AssertionError("a fresh read needs pinned authority before private repository access")

    if kind == "filing":
        definition = build_modelo_work_filing_record_definition(unavailable_factory)
        registration = build_modelo_work_filing_record_registration(definition, unavailable_factory)
        request = _request(record)
    else:
        definition = build_modelo_work_amendment_context_definition(unavailable_factory)
        registration = build_modelo_work_amendment_context_registration(definition, unavailable_factory)
        request = OperationRequest[BaseModel](
            definition_id=MODELO_WORK_AMENDMENT_CONTEXT_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(_PROFILE)),
            payload=ModeloWorkAmendmentContextRequest(profile_id=_PROFILE, filing_record_id=record.filing_record_id),
        )
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    context = OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=uuid4(),
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
    )

    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_operation_access(registry=registry, request=request, context=context)

    assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE
    assert calls == 0

    admitted = OperationAccessRequest(
        profile_id=_PROFILE,
        definition_id=request.definition_id,
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.CLI,
        periods=frozenset({unit.period}),
        period_independent=False,
        destination_id=context.destination_id,
    )
    historical = OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=context.destination_id,
        action=AccessAction.RESULT,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
        admitted_request=admitted,
    )
    resolved = resolve_operation_access(registry=registry, request=request, context=historical)
    assert resolved.request.periods == admitted.periods
    assert calls == 0


def test_filing_reader_scopes_submission_to_exact_profile_record_and_period(
    *, operation: PinnedAuthorityOperation
) -> None:
    """Fresh access derives its period from the exact canonical filing and owning unit."""
    unit, record = _source()
    definition, registration, registry = _build(_bundle(unit=unit, record=record))
    request = _request(record)

    resolved = resolve_operation_access(
        registry=registry,
        request=request,
        context=_access_context(registration, operation=operation),
    )

    assert resolved.request.periods == frozenset({unit.period})
    assert not resolved.request.period_independent
    assert resolved.request.profile_id == _PROFILE
    assert definition.result_type is ModeloWorkFilingRecordProjection
    assert registration.contract.result_schema is not None
    result_binding = next(
        binding
        for binding in registration.schema_bindings
        if binding.identity.schema_id == registration.contract.result_schema.schema_id
    )
    assert result_binding.identity == registration.contract.result_schema
    assert result_binding.model_type is ModeloWorkFilingRecordProjection


@pytest.mark.parametrize(
    ("filing_bucket_id", "record_update", "expected_reason"),
    [
        (str(_OTHER_PROFILE), {}, AccessDenialCode.PROFILE_MISMATCH),
        (
            str(_PROFILE),
            {"bucket_id": str(_OTHER_PROFILE)},
            AccessDenialCode.PROFILE_MISMATCH,
        ),
        (
            str(_PROFILE),
            {"period": Period.from_year_and_code(2026, "2T")},
            AccessDenialCode.PROFILE_MISMATCH,
        ),
    ],
)
def test_filing_reader_refuses_foreign_or_coordinate_mismatched_source(
    filing_bucket_id: str,
    record_update: dict[str, object],
    expected_reason: AccessDenialCode,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """A same-id row from another bucket or period cannot supply the requested unit."""
    unit, record = _source()
    mismatched = record.model_copy(update=record_update) if record_update else record
    bundle = _bundle(unit=unit, record=mismatched, filing_bucket_id=filing_bucket_id)
    _definition, registration, registry = _build(bundle)

    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_operation_access(
            registry=registry,
            request=_request(record),
            context=_access_context(registration, operation=operation),
        )

    assert refused.value.reason is expected_reason


@pytest.mark.parametrize("kind", ["filing", "amendment"])
def test_filing_and_amendment_access_refuse_identity_before_pin_or_shape(kind: str) -> None:
    """Profile identity precedes pins while each registered resolver retains shape refusal."""
    _unit_value, record = _source()
    bundle = _bundle(record=record)
    if kind == "filing":
        _definition, registration, registry = _build(bundle)
        request = _request(record)
    else:

        def factory(profile_id: str, *, operation: PinnedAuthorityOperation) -> VerificationRepositoryBundle:
            assert profile_id == str(_PROFILE)
            assert isinstance(operation, PinnedAuthorityOperation)
            return bundle

        definition = build_modelo_work_amendment_context_definition(factory)
        registration = build_modelo_work_amendment_context_registration(definition, factory)
        registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
        request = OperationRequest[BaseModel](
            definition_id=MODELO_WORK_AMENDMENT_CONTEXT_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(_PROFILE)),
            payload=ModeloWorkAmendmentContextRequest(profile_id=_PROFILE, filing_record_id=record.filing_record_id),
        )

    with pytest.raises(ProfileAccessRefusedError) as foreign_profile:
        resolve_operation_access(
            registry=registry,
            request=request,
            context=_access_context(registration, operation=None, profile_id=_OTHER_PROFILE),
        )
    assert foreign_profile.value.reason is AccessDenialCode.PROFILE_MISMATCH

    wrong_subject = request.model_copy(update={"subject_ref": record.work_unit_id})
    with pytest.raises(ProfileAccessRefusedError) as foreign_subject:
        resolve_operation_access(
            registry=registry,
            request=wrong_subject,
            context=_access_context(registration, operation=None),
        )
    assert foreign_subject.value.reason is AccessDenialCode.PROFILE_MISMATCH

    resolver = registration.access_resolver
    assert resolver is not None
    no_pin_context = _access_context(registration, operation=None, profile_id=_OTHER_PROFILE)
    malformed_requests = (
        request.model_copy(update={"definition_id": "wrong.definition", "subject_ref": "wrong-subject"}),
        request.model_copy(update={"payload": object(), "subject_ref": "wrong-subject"}),
    )
    for malformed_request in malformed_requests:
        with pytest.raises(ProfileAccessRefusedError) as malformed:
            resolver(malformed_request, no_pin_context)
        assert malformed.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE


def test_filing_executor_stores_typed_source_projection_without_a_report_repository(
    *, operation: PinnedAuthorityOperation
) -> None:
    """The encrypted result ties the exact selected receipt to its unit and actor."""
    unit, record = _source()
    bundle = _bundle(unit=unit, record=record)
    definition, registration, _registry = _build(bundle)
    request = _request(record)

    class Events:
        def __init__(self) -> None:
            self.phases: list[str] = []
            self.effects: list[OperationEffect] = []

        async def phase(self, phase_code: str) -> None:
            self.phases.append(phase_code)

        async def effect(self, effect: OperationEffect) -> None:
            self.effects.append(effect)

    class Operands:
        def __init__(self) -> None:
            self.value: BaseModel | None = None

        async def put(self, operand: BaseModel, *, written_at: datetime) -> str:
            assert written_at.tzinfo is not None
            self.value = operand
            return _RESULT_REFERENCE

    events = Events()
    operands = Operands()
    context = SimpleNamespace(
        authority_operation=operation,
        identity=SimpleNamespace(subject_ref=request.subject_ref),
        events=events,
        operands=operands,
    )

    result_reference = asyncio.run(definition.executor_factory.create().execute(request, context))

    assert result_reference == _RESULT_REFERENCE
    assert events.phases == [MODELO_WORK_FILING_RECORD_OPERATION_DEFINITION_ID]
    assert events.effects == [OperationEffect.NONE]
    assert type(operands.value) is ModeloWorkFilingRecordProjection
    projection = operands.value
    assert projection.profile_id == _PROFILE
    assert projection.record.filing_record_id == record.filing_record_id
    assert projection.record.filed_by == record.filed_by
    assert projection.unit.work_unit_id == unit.work_unit_id
    assert projection.unit.current_filing_record_id == record.filing_record_id
    assert projection.record.calculation_revision_id == record.calculation_revision_id
    assert registration.contract.result_schema is not None
    result_binding = next(
        binding
        for binding in registration.schema_bindings
        if binding.identity.schema_id == registration.contract.result_schema.schema_id
    )
    assert result_binding.model_type is ModeloWorkFilingRecordProjection
    restored = ModeloWorkFilingRecordProjection.model_validate_json(projection.model_dump_json())
    assert type(restored) is ModeloWorkFilingRecordProjection
    assert isinstance(projection.record, ModeloFilingRecordSnapshot)
    assert isinstance(projection.unit, ModeloWorkMetadataSnapshot)
