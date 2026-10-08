"""The filing-record list is a bounded whole-profile operation."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.operations import OperationEffect, profile_operation_subject
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.modelos.filing_record import (
    AeatConfirmationState,
    AeatRegisterRef,
    ExternalEvidence,
    ExternalEvidenceKind,
    FilingDeclarationKind,
    FilingOrigin,
    ModeloRecord,
    ModeloRecordCatalogue,
    ModeloRecordStatus,
    derive_filing_record_id,
)
from ....domain.modelos.work_unit import derive_work_unit_id
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
from ..filing_record_list_contracts import (
    ModeloFilingRecordListEntryProjection,
    ModeloFilingRecordListProjection,
    ModeloFilingRecordListRequest,
)
from ..filing_record_list_operation import (
    MODELO_FILING_RECORD_LIST_OPERATION_DEFINITION_ID,
    build_modelo_filing_record_list_definition,
    build_modelo_filing_record_list_registration,
)
from ..verification_repository_ports import VerificationRepositoryBundle

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_REVISION = "a" * 64
_NOW = datetime(2026, 4, 10, 9, 0, tzinfo=UTC)


def _record(
    *,
    profile_id: UUID = _PROFILE,
    actor: str = "synthetic filing operator",
    modelo: str = "303",
    year: int = 2026,
    period_code: str = "1T",
    status: ModeloRecordStatus = ModeloRecordStatus.VIGENTE,
    confirmed: bool = False,
) -> ModeloRecord:
    period = Period.from_year_and_code(year, period_code)
    work_unit_id = derive_work_unit_id(
        bucket_id=str(profile_id),
        modelo=modelo,
        filing_year=year,
        period=period,
        revision_id=f"test-{actor}-{modelo}-{year}-{period_code}",
    )
    filing_record_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=_REVISION,
        filed_by=actor,
    )
    return ModeloRecord(
        filing_record_id=filing_record_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=_REVISION,
        bucket_id=str(profile_id),
        modelo=modelo,
        filing_year=year,
        period=period,
        filed_at=_NOW,
        filed_by=actor,
        origin=FilingOrigin.AEAT if confirmed else FilingOrigin.LOCAL,
        confirmation=AeatConfirmationState.CONFIRMADA if confirmed else AeatConfirmationState.PENDIENTE,
        declaration_kind=FilingDeclarationKind.ORIGINAL,
        aeat_register=AeatRegisterRef(expediente_id="synthetic-expediente") if confirmed else None,
        external_evidence=(
            ExternalEvidence(
                kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
                reference_id="synthetic-evidence",
                imported_at=_NOW,
            )
            if confirmed
            else None
        ),
        status=status,
        superseded_at=_NOW if status is ModeloRecordStatus.SUPERSEDIDO else None,
        superseded_by_filing_record_id="f" * 64 if status is ModeloRecordStatus.SUPERSEDIDO else None,
    )


class _FilingRepository:
    def __init__(self, bucket_id: str, records: tuple[ModeloRecord, ...]) -> None:
        self.bucket_id = bucket_id
        self._catalogue = ModeloRecordCatalogue(records={record.filing_record_id: record for record in records})

    def load(self) -> ModeloRecordCatalogue:
        return self._catalogue


def _bundle(*records: ModeloRecord, repository_bucket_id: str | None = None) -> VerificationRepositoryBundle:
    return cast(
        VerificationRepositoryBundle,
        cast(
            object,
            SimpleNamespace(
                filing=_FilingRepository(repository_bucket_id or str(_PROFILE), tuple(records)),
            ),
        ),
    )


def _setup(bundle: VerificationRepositoryBundle):
    def factory(profile_id: str, *, operation: PinnedAuthorityOperation) -> VerificationRepositoryBundle:
        assert profile_id == str(_PROFILE)
        assert operation is not None
        return bundle

    definition = build_modelo_filing_record_list_definition(factory)
    registration = build_modelo_filing_record_list_registration(definition)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    return factory, definition, registration, registry


def _request(
    *,
    profile_id: UUID = _PROFILE,
    modelo: str | None = None,
    include_superseded: bool = False,
) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=MODELO_FILING_RECORD_LIST_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        payload=ModeloFilingRecordListRequest(
            profile_id=profile_id,
            modelo=modelo,
            include_superseded=include_superseded,
        ),
    )


def _access_context(
    registration,
    *,
    operation: PinnedAuthorityOperation,
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


def test_request_and_list_rows_are_strict_frozen_and_allowlisted() -> None:
    record = _record(confirmed=True)
    payload = ModeloFilingRecordListRequest(profile_id=_PROFILE, modelo="303")
    row = ModeloFilingRecordListEntryProjection.from_record(record)
    projection = ModeloFilingRecordListProjection(
        profile_id=_PROFILE,
        modelo="303",
        include_superseded=False,
        record_count=1,
        records=(row,),
    )

    restored = ModeloFilingRecordListProjection.model_validate_json(projection.model_dump_json())

    assert restored == projection
    assert restored.records[0].aeat_register is not None
    assert restored.records[0].external_evidence is not None
    assert payload.modelo == "303"
    assert "source_transaction_ids" not in projection.model_dump_json()
    assert "settlement" not in projection.model_dump_json()
    with pytest.raises(ValidationError):
        ModeloFilingRecordListRequest.model_validate({"profile_id": _PROFILE, "modelo": "303", "unexpected": 1})
    with pytest.raises(ValidationError):
        ModeloFilingRecordListRequest(profile_id=_PROFILE, modelo="30X")


def test_access_is_exact_profile_and_requires_whole_profile_consent() -> None:
    _factory, definition, registration, registry = _setup(_bundle(_record()))
    operation = cast(PinnedAuthorityOperation, object())
    admitted = resolve_operation_access(
        registry=registry,
        request=_request(),
        context=_access_context(registration, operation=operation),
    )
    assert admitted.request.period_independent
    assert admitted.request.periods == frozenset()
    assert admitted.policy.requires_all_periods
    assert definition.result_type is ModeloFilingRecordListProjection

    result_context = _access_context(
        registration,
        operation=operation,
        action=AccessAction.RESULT,
        admitted=admitted.request,
    )
    result = resolve_operation_access(registry=registry, request=_request(), context=result_context)
    permission = next(iter(result.policy.disclosures))
    assert registration.contract.result_schema is not None
    assert permission.projection_id == registration.contract.result_schema.schema_id
    assert permission.category is DisclosureCategory.TAX_VALUES

    with pytest.raises(ProfileAccessRefusedError) as foreign:
        resolve_operation_access(
            registry=registry,
            request=_request(),
            context=_access_context(registration, operation=operation, profile_id=_OTHER_PROFILE),
        )
    assert foreign.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_capture_filters_exact_profile_and_does_not_truncate(monkeypatch: pytest.MonkeyPatch) -> None:
    from .. import filing_record_list_operation as operation_module

    current_303 = _record(actor="first", modelo="303")
    current_100 = _record(actor="second", modelo="100")
    superseded_303 = _record(actor="third", modelo="303", status=ModeloRecordStatus.SUPERSEDIDO)
    foreign = _record(profile_id=_OTHER_PROFILE, actor="foreign")
    request = ModeloFilingRecordListRequest(profile_id=_PROFILE, modelo="303")
    projection = operation_module._capture(
        request,
        _bundle(current_100, current_303, superseded_303, foreign),
    )
    assert [row.filing_record_id for row in projection.records] == [current_303.filing_record_id]
    assert projection.record_count == 1

    inclusive = operation_module._capture(
        ModeloFilingRecordListRequest(profile_id=_PROFILE, modelo="303", include_superseded=True),
        _bundle(current_100, superseded_303, current_303),
    )
    assert inclusive.record_count == 2
    assert {row.status for row in inclusive.records} == {ModeloRecordStatus.VIGENTE, ModeloRecordStatus.SUPERSEDIDO}

    monkeypatch.setattr(operation_module, "MAX_MODELO_FILING_RECORD_LIST_ROWS", 1)
    with pytest.raises(ProfileAccessRefusedError) as oversized:
        operation_module._capture(
            ModeloFilingRecordListRequest(profile_id=_PROFILE, include_superseded=True),
            _bundle(current_303, current_100, superseded_303),
        )
    assert oversized.value.reason is AccessDenialCode.OPERATION_DENIED


def test_executor_stores_one_projection_and_reports_none() -> None:
    records = (_record(actor="first"), _record(actor="second", modelo="100"))
    bundle = _bundle(*records)
    factory, definition, _registration, _registry = _setup(bundle)
    operation = cast(PinnedAuthorityOperation, object())
    request = _request()
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
            return "f" * 64

    context = SimpleNamespace(
        authority_operation=operation,
        identity=SimpleNamespace(
            definition_id=MODELO_FILING_RECORD_LIST_OPERATION_DEFINITION_ID,
            subject_ref=request.subject_ref,
        ),
        events=Events(),
        operands=Operands(),
    )

    reference = asyncio.run(definition.executor_factory.create().execute(request, context))

    assert reference == "f" * 64
    assert phases == [MODELO_FILING_RECORD_LIST_OPERATION_DEFINITION_ID]
    assert effects == [OperationEffect.NONE]
    assert len(stored) == 1
    assert type(stored[0]) is ModeloFilingRecordListProjection
    assert stored[0].profile_id == _PROFILE
    assert stored[0].record_count == len(records)
    assert factory is not None


def test_capture_refuses_a_foreign_repository_bucket() -> None:
    from .. import filing_record_list_operation as operation_module

    with pytest.raises(ProfileAccessRefusedError) as refused:
        operation_module._capture(
            ModeloFilingRecordListRequest(profile_id=_PROFILE),
            _bundle(_record(), repository_bucket_id=str(_OTHER_PROFILE)),
        )
    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_projection_rejects_mismatched_count_filter_and_order() -> None:
    first = ModeloFilingRecordListEntryProjection.from_record(_record(actor="first"))
    second = ModeloFilingRecordListEntryProjection.from_record(_record(actor="second", modelo="100"))
    with pytest.raises(ValidationError):
        ModeloFilingRecordListProjection(
            profile_id=_PROFILE,
            modelo=None,
            include_superseded=False,
            record_count=0,
            records=(first,),
        )
    with pytest.raises(ValidationError):
        ModeloFilingRecordListProjection(
            profile_id=_PROFILE,
            modelo="303",
            include_superseded=False,
            record_count=1,
            records=(second,),
        )
