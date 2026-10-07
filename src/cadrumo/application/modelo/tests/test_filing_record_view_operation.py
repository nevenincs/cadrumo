"""The filing-record view binds one receipt and both observation layers."""

from __future__ import annotations

import asyncio
import threading
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.casilla_id import validated_casilla_id
from ....core.operations import OperationEffect, profile_operation_subject
from ....core.period import Period
from ....core.result_disposition import ResultDisposition
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.bindings import CasillaObservation, RegistryModeloObservation
from ....domain.iva_compensation.filed_derivation import M303CompensationBasis
from ....domain.modelos.calculation_revision import CalculationRevisionCatalogue
from ....domain.modelos.filing_record import (
    AeatConfirmationState,
    FilingDeclarationKind,
    FilingOrigin,
    ModeloRecord,
    ModeloRecordCatalogue,
    derive_filing_record_id,
)
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, WorkUnitState, derive_work_unit_id
from ...calculations.observations_repository import (
    ObservationEnvelopePayload,
    ObservationLayers,
    ObservationOverride,
    ObservationSourceKind,
    ResultDispositionProjection,
)
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationRequest
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
    OperationAccessRequest,
)
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..filing_record_list_contracts import ModeloFilingRecordListEntryProjection
from ..filing_record_view_operation import (
    MODELO_FILING_RECORD_VIEW_OPERATION_DEFINITION_ID,
    ModeloFilingObservationLayersProjection,
    ModeloFilingRecordViewProjection,
    ModeloFilingRecordViewRequest,
    build_modelo_filing_record_view_definition,
    build_modelo_filing_record_view_registration,
)
from ..historical_filing_projection import project_historical_filing_content
from ..verification_repository_ports import VerificationRepositoryBundle

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_CALCULATION_REVISION_ID = "a" * 64
_NOW = datetime(2026, 4, 10, 9, 0, tzinfo=UTC)
_RESULT_REFERENCE = "f" * 64
_ACTOR = "gestoria source"


def _source() -> tuple[WorkUnit, ModeloRecord]:
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


def _observation_layers() -> ObservationLayers:
    casilla_id = validated_casilla_id("01", surface="filing view test")

    def observation(amount: str) -> RegistryModeloObservation:
        return RegistryModeloObservation(
            modelo="303",
            filing_year=2026,
            period="1T",
            observations=(
                CasillaObservation(
                    casilla_id=casilla_id,
                    value=Decimal(amount),
                    legal_refs=("synthetic-legal",),
                    source_refs=("synthetic-source",),
                ),
            ),
        )

    disposition = ResultDispositionProjection(
        disposition=ResultDisposition.INGRESO,
        provenance_kind="source_header",
        provenance_locator="synthetic-file:declaration-type",
    )
    official = ObservationEnvelopePayload(
        source_kind=ObservationSourceKind.AEAT_CSV_REGISTER,
        captured_at=_NOW,
        stamped_revision_id="revision-2026",
        observation=observation("10.25"),
        result_disposition=disposition,
        m303_compensation_basis=M303CompensationBasis.RESULTADO,
    )
    override = ObservationOverride(
        actor="operator",
        reason="corrected from supporting evidence",
        recorded_at=_NOW,
        replaced_source_kind=ObservationSourceKind.AEAT_CSV_REGISTER,
        replaced_values={casilla_id: "10.25"},
    )
    pending = ObservationEnvelopePayload(
        source_kind=ObservationSourceKind.OPERATOR_MANUAL,
        captured_at=_NOW,
        stamped_revision_id="revision-2026",
        observation=observation("11.50"),
        override=override,
        result_disposition=disposition,
        m303_compensation_basis=M303CompensationBasis.RESULTADO,
    )
    return ObservationLayers(
        modelo="303",
        filing_year=2026,
        period="1T",
        official=official,
        pending_local=pending,
    )


class _Repository:
    def __init__(self, bucket_id: str, catalogue: BaseModel) -> None:
        self.bucket_id = bucket_id
        self._catalogue = catalogue

    def load(self) -> BaseModel:
        return self._catalogue


class _ObservationRepository:
    def __init__(self, layers: object) -> None:
        self.layers = layers
        self.calls: list[tuple[str, Period, str | None, int]] = []

    def load_observation_layers(self, modelo: str, period: Period, *, member_nif: str | None = None):
        self.calls.append((modelo, period, member_nif, threading.get_ident()))
        return self.layers


def _bundle(
    *,
    record: ModeloRecord | None = None,
    unit: WorkUnit | None = None,
    filing_bucket_id: str | None = None,
    work_bucket_id: str | None = None,
    observation_repository: _ObservationRepository | None = None,
    include_record: bool = True,
) -> VerificationRepositoryBundle:
    source_unit, source_record = _source()
    selected_unit = unit or source_unit
    selected_record = record or source_record
    return cast(
        VerificationRepositoryBundle,
        cast(
            object,
            SimpleNamespace(
                filing=_Repository(
                    filing_bucket_id or str(_PROFILE),
                    ModeloRecordCatalogue(
                        records={selected_record.filing_record_id: selected_record} if include_record else {}
                    ),
                ),
                work_unit=_Repository(
                    work_bucket_id or str(_PROFILE),
                    WorkUnitCatalogue(work_units={selected_unit.work_unit_id: selected_unit}),
                ),
                observation=observation_repository or _ObservationRepository(_observation_layers()),
                calculation=_Repository(str(_PROFILE), CalculationRevisionCatalogue()),
            ),
        ),
    )


def _registered(bundle: VerificationRepositoryBundle):
    def factory(profile_id: str, *, operation: PinnedAuthorityOperation) -> VerificationRepositoryBundle:
        assert profile_id == str(_PROFILE)
        assert operation is not None
        return bundle

    definition = build_modelo_filing_record_view_definition(factory)
    registration = build_modelo_filing_record_view_registration(definition, factory)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    return factory, definition, registration, registry


def _request(record: ModeloRecord, *, profile_id: UUID = _PROFILE) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=MODELO_FILING_RECORD_VIEW_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        payload=ModeloFilingRecordViewRequest(profile_id=profile_id, filing_record_id=record.filing_record_id),
    )


def _context(
    registration,
    *,
    operation: PinnedAuthorityOperation | None,
    action: AccessAction = AccessAction.SUBMIT,
    profile_id: UUID = _PROFILE,
    admitted: OperationAccessRequest | None = None,
) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=profile_id,
        destination_id=uuid4(),
        action=action,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
        authority_operation=operation,
        admitted_request=admitted,
    )


def test_view_projection_carries_both_layers_and_bounded_override_audit() -> None:
    _unit, record = _source()
    layers = ModeloFilingObservationLayersProjection.from_layers(_observation_layers())
    projection = ModeloFilingRecordViewProjection(
        profile_id=_PROFILE,
        filing_record_id=record.filing_record_id,
        record=ModeloFilingRecordListEntryProjection.from_record(record),
        observation_layers=layers,
        historical_content=project_historical_filing_content(record, None),
    )

    restored = ModeloFilingRecordViewProjection.model_validate_json(projection.model_dump_json())

    assert restored == projection
    assert restored.record.filing_record_id == record.filing_record_id
    assert restored.observation_layers.official is not None
    assert restored.observation_layers.pending_local is not None
    assert restored.observation_layers.effective_source_kind is ObservationSourceKind.OPERATOR_MANUAL
    assert restored.observation_layers.override is not None
    assert restored.observation_layers.override.replaced_values == (("01", "10.25"),)
    assert "source_metadata" not in projection.model_dump_json()
    assert "source_transaction_ids" not in type(projection.record).model_fields
    assert "settlement" not in type(projection.record).model_fields


def test_submission_scope_is_exact_and_result_disclosure_is_tax_values() -> None:
    unit, record = _source()
    observation_repository = _ObservationRepository(_observation_layers())
    bundle = _bundle(observation_repository=observation_repository)
    _factory, definition, registration, registry = _registered(bundle)
    operation = cast(PinnedAuthorityOperation, object())
    request = _request(record)

    admitted = resolve_operation_access(
        registry=registry,
        request=request,
        context=_context(registration, operation=operation),
    )
    result_context = _context(
        registration,
        operation=operation,
        action=AccessAction.RESULT,
        admitted=admitted.request,
    )
    result = resolve_operation_access(registry=registry, request=request, context=result_context)

    assert admitted.request.periods == frozenset({unit.period})
    assert not admitted.request.period_independent
    assert observation_repository.calls == []
    permission = next(iter(result.policy.disclosures))
    assert permission.destination_id == result_context.destination_id
    assert registration.contract.result_schema is not None
    assert permission.projection_id == registration.contract.result_schema.schema_id
    assert permission.category is DisclosureCategory.TAX_VALUES
    assert definition.result_type is ModeloFilingRecordViewProjection


def test_view_request_identity_refuses_before_missing_pin_and_shape() -> None:
    _unit, record = _source()
    _factory, _definition, registration, registry = _registered(_bundle())
    request = _request(record)

    with pytest.raises(ProfileAccessRefusedError) as foreign_profile:
        resolve_operation_access(
            registry=registry,
            request=request,
            context=_context(registration, operation=None, profile_id=_OTHER_PROFILE),
        )
    assert foreign_profile.value.reason is AccessDenialCode.PROFILE_MISMATCH

    wrong_subject = request.model_copy(update={"subject_ref": record.work_unit_id})
    with pytest.raises(ProfileAccessRefusedError) as foreign_subject:
        resolve_operation_access(
            registry=registry,
            request=wrong_subject,
            context=_context(registration, operation=None),
        )
    assert foreign_subject.value.reason is AccessDenialCode.PROFILE_MISMATCH

    resolver = registration.access_resolver
    assert resolver is not None
    no_pin_context = _context(registration, operation=None, profile_id=_OTHER_PROFILE)
    malformed_requests = (
        request.model_copy(update={"definition_id": "wrong.definition", "subject_ref": "wrong-subject"}),
        request.model_copy(update={"payload": object(), "subject_ref": "wrong-subject"}),
    )
    for malformed_request in malformed_requests:
        with pytest.raises(ProfileAccessRefusedError) as malformed:
            resolver(malformed_request, no_pin_context)
        assert malformed.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE


def test_executor_reads_layers_once_on_worker_and_stores_one_typed_result() -> None:
    _unit, record = _source()
    observation_repository = _ObservationRepository(_observation_layers())
    bundle = _bundle(observation_repository=observation_repository)
    _factory, definition, _registration_value, _registry = _registered(bundle)
    operation = cast(PinnedAuthorityOperation, object())
    request = _request(record)
    owner_thread = threading.get_ident()
    phases: list[str] = []
    effects: list[OperationEffect] = []
    stored: list[BaseModel] = []

    class Events:
        async def phase(self, phase_code: str) -> None:
            phases.append(phase_code)

        async def effect(self, effect: OperationEffect) -> None:
            effects.append(effect)

    class Operands:
        async def put(self, operand: BaseModel, *, written_at: datetime) -> str:
            assert written_at.tzinfo is not None
            stored.append(operand)
            return _RESULT_REFERENCE

    context = SimpleNamespace(
        authority_operation=operation,
        identity=SimpleNamespace(
            definition_id=MODELO_FILING_RECORD_VIEW_OPERATION_DEFINITION_ID,
            subject_ref=request.subject_ref,
        ),
        events=Events(),
        operands=Operands(),
    )

    reference = asyncio.run(definition.executor_factory.create().execute(request, context))

    assert reference == _RESULT_REFERENCE
    assert phases == [MODELO_FILING_RECORD_VIEW_OPERATION_DEFINITION_ID]
    assert effects == [OperationEffect.NONE]
    assert len(observation_repository.calls) == 1
    assert observation_repository.calls[0][:3] == ("303", record.period, None)
    assert observation_repository.calls[0][3] != owner_thread
    assert type(stored[0]) is ModeloFilingRecordViewProjection
    assert stored[0].filing_record_id == record.filing_record_id


def test_missing_receipt_and_cross_profile_catalogues_fail_closed() -> None:
    _unit, record = _source()
    operation = cast(PinnedAuthorityOperation, object())
    _factory, _definition, registration, registry = _registered(_bundle(include_record=False))

    with pytest.raises(ProfileAccessRefusedError) as missing:
        resolve_operation_access(
            registry=registry,
            request=_request(record),
            context=_context(registration, operation=operation),
        )
    assert missing.value.reason is AccessDenialCode.OPERATION_DENIED

    foreign_bundle = _bundle(filing_bucket_id=str(_OTHER_PROFILE))
    _foreign_factory, _foreign_definition, foreign_registration, foreign_registry = _registered(foreign_bundle)
    with pytest.raises(ProfileAccessRefusedError) as foreign:
        resolve_operation_access(
            registry=foreign_registry,
            request=_request(record),
            context=_context(foreign_registration, operation=operation),
        )
    assert foreign.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_projection_refuses_mismatched_coordinates_and_oversized_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _unit, record = _source()
    layers = ModeloFilingObservationLayersProjection.from_layers(_observation_layers()).model_copy(
        update={"period": "2T"}
    )
    with pytest.raises(ValidationError):
        ModeloFilingRecordViewProjection(
            profile_id=_PROFILE,
            filing_record_id=record.filing_record_id,
            record=ModeloFilingRecordListEntryProjection.from_record(record),
            observation_layers=layers,
            historical_content=project_historical_filing_content(record, None),
        )

    from .. import filing_record_view_operation as operation_module

    monkeypatch.setattr(operation_module, "_RESULT_DOCUMENT_MAX_BYTES", 1)
    bundle = _bundle()
    request = ModeloFilingRecordViewRequest(profile_id=_PROFILE, filing_record_id=record.filing_record_id)
    with pytest.raises(ProfileAccessRefusedError) as oversized:
        operation_module._capture(request, bundle)
    assert oversized.value.reason is AccessDenialCode.OPERATION_DENIED


def test_request_rejects_malformed_filing_identity() -> None:
    with pytest.raises(ValidationError):
        ModeloFilingRecordViewRequest(profile_id=_PROFILE, filing_record_id="bad-id")
