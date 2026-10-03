"""The filing-record import stays in secure custody until its guarded write."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
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
    ModeloRecordStatus,
    derive_filing_record_id,
)
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, WorkUnitState, derive_work_unit_id
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
)
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..calculation_action_ports import CalculationActionPorts, CalculationActionPortsFactory
from ..filing_chain_reconciliation import (
    FilingReconciliationNotice,
    FilingReconciliationNoticeCode,
    FilingReconciliationOutcome,
    FilingReconciliationResult,
)
from ..filing_record_import_operation import (
    MODELO_FILING_RECORD_IMPORT_OPERATION_DEFINITION_ID,
    ModeloFilingRecordImportOperationReport,
    ModeloFilingRecordImportProjection,
    ModeloFilingRecordImportReconciliationProjection,
    ModeloFilingRecordImportRequest,
    _project_filing_record_import,
    build_modelo_filing_record_import_definition,
    build_modelo_filing_record_import_registration,
)
from ..filing_record_list_operation import ModeloFilingRecordListEntryProjection

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_REVISION = "a" * 64
_NOW = datetime(2026, 4, 10, 9, 0, tzinfo=UTC)
_REFERENCE = "synthetic-expediente"
_WORK_UNIT_ID = derive_work_unit_id(
    bucket_id=str(_PROFILE),
    modelo="303",
    filing_year=2026,
    period=Period.from_year_and_code(2026, "1T"),
    revision_id="requested-revision",
)


def _unit(*, revision_id: str = "requested-revision", created_at: datetime = _NOW) -> WorkUnit:
    unit_id = derive_work_unit_id(
        bucket_id=str(_PROFILE),
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id=revision_id,
    )
    return WorkUnit(
        work_unit_id=unit_id,
        bucket_id=str(_PROFILE),
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id=revision_id,
        name="Synthetic first quarter",
        created_at=created_at,
        updated_at=created_at,
        state=WorkUnitState.BORRADOR,
    )


def _record(*, work_unit_id: str = _WORK_UNIT_ID) -> ModeloRecord:
    return ModeloRecord(
        filing_record_id=derive_filing_record_id(
            work_unit_id=work_unit_id,
            calculation_revision_id=_REVISION,
            filed_by="synthetic import actor",
        ),
        work_unit_id=work_unit_id,
        calculation_revision_id=_REVISION,
        bucket_id=str(_PROFILE),
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        filed_at=_NOW,
        filed_by="synthetic import actor",
        origin=FilingOrigin.AEAT,
        confirmation=AeatConfirmationState.CONFIRMADA,
        declaration_kind=FilingDeclarationKind.ORIGINAL,
        aeat_register=AeatRegisterRef(expediente_id=_REFERENCE),
        status=ModeloRecordStatus.VIGENTE,
        external_evidence=ExternalEvidence(
            kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
            reference_id=_REFERENCE,
            imported_at=_NOW,
        ),
    )


def _reconciliation(record: ModeloRecord) -> FilingReconciliationResult:
    return FilingReconciliationResult(
        outcome=FilingReconciliationOutcome.APPENDED,
        bucket_id=str(_PROFILE),
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        member_nif=None,
        filing_record_id=record.filing_record_id,
        affected_filing_record_ids=(),
        differing_casilla_ids=(),
        evidence_basis="casillas",
        notices=(
            FilingReconciliationNotice(
                FilingReconciliationNoticeCode.CONTENT_UNAVAILABLE,
                {"reason": "synthetic"},
            ),
        ),
    )


class _WorkUnits:
    def __init__(self, units: tuple[WorkUnit, ...]) -> None:
        self.bucket_id = str(_PROFILE)
        self.catalogue = WorkUnitCatalogue(work_units={unit.work_unit_id: unit for unit in units})

    def load(self) -> WorkUnitCatalogue:
        return self.catalogue

    def add(self, unit: WorkUnit) -> None:
        self.catalogue = WorkUnitCatalogue(work_units={**self.catalogue.work_units, unit.work_unit_id: unit})


def _ports_factory(work_units: _WorkUnits):
    operation = cast(PinnedAuthorityOperation, object())
    ports = SimpleNamespace(
        operation=operation,
        work_unit_repository=work_units,
        work_lifecycle_ports=SimpleNamespace(work_unit_repository=work_units),
        calculation_repository=SimpleNamespace(bucket_id=str(_PROFILE)),
        filing_repository=SimpleNamespace(bucket_id=str(_PROFILE)),
        observation_repository=object(),
        bucket_event_repository=object(),
        profile_read_ports=SimpleNamespace(
            path_values=SimpleNamespace(load_path_values=lambda *, bucket_id: {"identity.tax_id": "B12345678"})
        ),
    )

    def factory(*, bucket_id: str, operation: PinnedAuthorityOperation):
        assert bucket_id == str(_PROFILE)
        assert operation is ports.operation
        return ports

    return operation, cast(CalculationActionPortsFactory, factory)


def _request(
    *,
    source_path: str | None = None,
    casilla_values: tuple[tuple[CasillaId, str], ...] | None = None,
) -> OperationRequest[BaseModel]:
    if casilla_values is None:
        casilla_values = () if source_path is not None else ((validated_casilla_id("01", surface="test"), "1"),)
    return OperationRequest[BaseModel](
        definition_id=MODELO_FILING_RECORD_IMPORT_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=ModeloFilingRecordImportRequest(
            profile_id=_PROFILE,
            work_unit_id=_WORK_UNIT_ID,
            evidence_kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
            evidence_reference_id=_REFERENCE,
            actor="synthetic import actor",
            casilla_values=casilla_values,
            source_path=source_path,
        ),
    )


def test_request_is_secure_immutable_and_requires_one_canonical_input() -> None:
    values = ((validated_casilla_id("01", surface="test"), "12.30"),)
    direct = ModeloFilingRecordImportRequest(
        profile_id=_PROFILE,
        work_unit_id=_WORK_UNIT_ID,
        evidence_kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
        evidence_reference_id=_REFERENCE,
        casilla_values=values,
    )
    spreadsheet = direct.model_copy(update={"casilla_values": (), "source_path": "C:/private/evidence.xlsx"})

    assert direct.casilla_values == values
    assert spreadsheet.source_path == "C:/private/evidence.xlsx"
    with pytest.raises(ValidationError):
        direct.actor = "changed"
    with pytest.raises(ValidationError):
        ModeloFilingRecordImportRequest(
            profile_id=_PROFILE,
            work_unit_id=_WORK_UNIT_ID,
            evidence_kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
            evidence_reference_id=_REFERENCE,
        )
    with pytest.raises(ValidationError):
        ModeloFilingRecordImportRequest(
            profile_id=_PROFILE,
            work_unit_id=_WORK_UNIT_ID,
            evidence_kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
            evidence_reference_id=_REFERENCE,
            casilla_values=values,
            source_path="C:/private/evidence.xlsx",
        )
    with pytest.raises(ValidationError):
        ModeloFilingRecordImportRequest(
            profile_id=_PROFILE,
            work_unit_id=_WORK_UNIT_ID,
            evidence_kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
            evidence_reference_id=_REFERENCE,
            casilla_values=(
                (validated_casilla_id("02", surface="test"), "1"),
                (validated_casilla_id("01", surface="test"), "2"),
            ),
        )


def test_secure_request_definition_and_commit_access_are_exact_profile() -> None:
    work_units = _WorkUnits((_unit(),))
    operation, factory = _ports_factory(work_units)
    definition = build_modelo_filing_record_import_definition(factory)
    registration = build_modelo_filing_record_import_registration(definition, factory)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    request = _request()
    context = OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=uuid4(),
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
        authority_operation=operation,
    )

    admitted = resolve_operation_access(registry=registry, request=request, context=context)
    commit = resolve_operation_access(
        registry=registry,
        request=request,
        context=replace(context, action=AccessAction.COMMIT, admitted_request=admitted.request),
    )

    assert definition.capabilities.request_storage.value == "secure_reference"
    assert definition.capabilities.sensitive_input.value == "secure_reference"
    assert commit.request.periods == frozenset({Period.from_year_and_code(2026, "1T")})
    assert AccessAction.COMMIT in commit.policy.actions
    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_operation_access(
            registry=registry,
            request=request,
            context=replace(context, profile_id=_OTHER_PROFILE),
        )
    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_public_result_omits_source_locators_settlement_and_transaction_ids() -> None:
    record = _record()
    reconciliation = _reconciliation(record)
    projection = ModeloFilingRecordImportProjection(
        profile_id=_PROFILE,
        record=ModeloFilingRecordListEntryProjection.from_record(record),
        reconciliation=ModeloFilingRecordImportReconciliationProjection.from_result(reconciliation),
    )
    rendered = projection.model_dump_json()

    assert "source_path" not in rendered
    assert "source_transaction_ids" not in rendered
    assert "settlement" not in rendered
    assert projection.record.external_evidence is not None
    assert projection.record.external_evidence.reference_id == _REFERENCE

    identity = OperationIdentity(
        operation_id="b" * 64,
        definition_id=MODELO_FILING_RECORD_IMPORT_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
    )
    receipt = OperationTerminalReceipt(
        identity=identity,
        revision=0,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.UPDATED,
        settled_at=_NOW,
        result_ref="c" * 64,
    )
    report = ModeloFilingRecordImportOperationReport(projection=projection, local_write_performed=True)

    assert _project_filing_record_import(report, receipt) == projection
    with pytest.raises(ValueError):
        _project_filing_record_import(
            report.model_copy(update={"local_write_performed": False}),
            receipt,
        )


def test_source_refuses_discarded_or_stale_exact_work_unit_before_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from .. import filing_record_import_operation as operation_module

    discarded = WorkUnit.model_validate(
        _unit().model_dump(mode="python")
        | {
            "state": WorkUnitState.DESCARTADO,
            "discarded_at": _NOW,
            "discarded_by": "synthetic operator",
            "discard_reason": "test fixture",
        }
    )
    discarded_catalogue = _WorkUnits((discarded,))
    ports = SimpleNamespace(
        work_unit_repository=discarded_catalogue,
        work_lifecycle_ports=SimpleNamespace(work_unit_repository=discarded_catalogue),
    )
    with pytest.raises(ProfileAccessRefusedError) as inactive:
        operation_module._selected_work_unit(
            cast(CalculationActionPorts, cast(object, ports)),
            cast(ModeloFilingRecordImportRequest, _request(source_path="C:/evidence.xlsx").payload),
        )
    assert inactive.value.reason is AccessDenialCode.OPERATION_DENIED
    assert set(discarded_catalogue.load().work_units) == {discarded.work_unit_id}

    active = _unit()
    active_catalogue = _WorkUnits((active,))
    monkeypatch.setattr(
        operation_module,
        "law_selected_revision_for_work_target",
        lambda **_kwargs: "different-law-revision",
    )
    with pytest.raises(ProfileAccessRefusedError) as stale:
        operation_module._require_law_current_source_work_unit(
            active,
            operation=cast(PinnedAuthorityOperation, object()),
        )
    assert stale.value.reason is AccessDenialCode.OPERATION_DENIED
    assert set(active_catalogue.load().work_units) == {active.work_unit_id}


def test_executor_parses_source_before_commit_and_guards_source_and_receipt_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from .. import filing_record_import_operation as operation_module

    requested_unit = _unit()
    work_units = _WorkUnits((requested_unit,))
    operation, factory = _ports_factory(work_units)
    state = {"inside_commit": False}
    phases: list[str] = []
    effects: list[OperationEffect] = []
    stored: list[BaseModel] = []
    record = _record(work_unit_id=requested_unit.work_unit_id)
    imported = SimpleNamespace(filing_record=record, reconciliation=_reconciliation(record))

    def parse(_path):
        assert not state["inside_commit"]
        return {validated_casilla_id("01", surface="test"): "12.30"}

    def validate_source(_source):
        assert state["inside_commit"]
        casilla_id = validated_casilla_id("01", surface="test")
        return {casilla_id: "12.30"}, {casilla_id: Decimal("12.30")}

    def import_evidence(**kwargs):
        assert state["inside_commit"]
        assert kwargs["work_unit_id"] == requested_unit.work_unit_id
        assert kwargs["casilla_values"] == {validated_casilla_id("01", surface="test"): Decimal("12.30")}
        assert kwargs["source_lexical_values_by_casilla_id"] == {validated_casilla_id("01", surface="test"): "12.30"}
        assert kwargs["expected_tax_id"] == "B12345678"
        return imported

    monkeypatch.setattr(operation_module, "require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(operation_module, "parse_casilla_lexical_spreadsheet", parse)
    monkeypatch.setattr("cadrumo.application.operations.profile_guard.require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(operation_module, "external_filing_source_casillas", validate_source)
    monkeypatch.setattr(
        operation_module,
        "law_selected_revision_for_work_target",
        lambda **kwargs: kwargs["requested_revision_id"],
    )
    monkeypatch.setattr(operation_module, "import_external_filing_evidence", import_evidence)

    @asynccontextmanager
    async def irreversible_section():
        assert not state["inside_commit"]
        state["inside_commit"] = True
        try:
            yield
        finally:
            state["inside_commit"] = False

    class Events:
        async def phase(self, phase_code: str) -> None:
            phases.append(phase_code)

        async def effect(self, effect: OperationEffect) -> None:
            assert state["inside_commit"]
            effects.append(effect)

    class Operands:
        async def put(self, operand: BaseModel, *, written_at: datetime) -> str:
            assert state["inside_commit"]
            assert written_at.tzinfo is not None
            stored.append(operand)
            return "d" * 64

    definition = build_modelo_filing_record_import_definition(factory)
    request = _request(source_path="C:/private/evidence.xlsx")
    context = SimpleNamespace(
        authority_operation=operation,
        identity=SimpleNamespace(
            definition_id=MODELO_FILING_RECORD_IMPORT_OPERATION_DEFINITION_ID,
            subject_ref=request.subject_ref,
        ),
        events=Events(),
        operands=Operands(),
        cancellation=SimpleNamespace(irreversible_section=irreversible_section),
    )

    reference = asyncio.run(definition.executor_factory.create().execute(request, context))

    assert reference == "d" * 64
    assert effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
    assert len(stored) == 1
    assert isinstance(stored[0], ModeloFilingRecordImportOperationReport)
    assert stored[0].local_write_performed
    assert set(work_units.load().work_units) == {requested_unit.work_unit_id}
    assert phases == [
        "modelo-filing-record-import.prepare",
        "modelo-filing-record-import.commit",
        "modelo-filing-record-import.result",
    ]
