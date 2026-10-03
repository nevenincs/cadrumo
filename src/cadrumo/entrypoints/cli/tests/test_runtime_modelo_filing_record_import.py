"""The filing-record import bridge preserves the existing safe CLI result."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import typer

from ....application.modelo.filing_chain_reconciliation import (
    FilingReconciliationOutcome,
    FilingReconciliationResult,
)
from ....application.modelo.filing_record_import_contracts import (
    MODELO_FILING_RECORD_IMPORT_OPERATION_DEFINITION_ID,
    ModeloFilingRecordImportProjection,
    ModeloFilingRecordImportReconciliationProjection,
    ModeloFilingRecordImportRequest,
)
from ....application.modelo.filing_record_list_contracts import ModeloFilingRecordListEntryProjection
from ....application.runtime.contracts import RuntimeRefusalCode
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....core.period import Period
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
from ....domain.modelos.work_unit import derive_work_unit_id
from .. import runtime_modelo_filing_record_import as bridge
from .._modelo_payloads import FilingRecordImportResult
from ..errors import CliRefusedBoundaryError
from ..registered_operation_contracts import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OPERATION_ID = "b" * 64
_REVISION = "a" * 64
_REFERENCE = "synthetic-expediente"
_NOW = datetime(2026, 4, 10, 9, 0, tzinfo=UTC)
_WORK_UNIT_ID = derive_work_unit_id(
    bucket_id=str(_PROFILE),
    modelo="303",
    filing_year=2026,
    period=Period.from_year_and_code(2026, "1T"),
    revision_id="synthetic-revision",
)


def _projection(
    outcome: FilingReconciliationOutcome = FilingReconciliationOutcome.APPENDED,
) -> ModeloFilingRecordImportProjection:
    record = ModeloRecord(
        filing_record_id=derive_filing_record_id(
            work_unit_id=_WORK_UNIT_ID,
            calculation_revision_id=_REVISION,
            filed_by="synthetic import actor",
        ),
        work_unit_id=_WORK_UNIT_ID,
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
    reconciliation = FilingReconciliationResult(
        outcome=outcome,
        bucket_id=str(_PROFILE),
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        member_nif=None,
        filing_record_id=record.filing_record_id,
        affected_filing_record_ids=(),
        differing_casilla_ids=(),
        evidence_basis="casillas",
        notices=(),
    )
    return ModeloFilingRecordImportProjection(
        profile_id=_PROFILE,
        record=ModeloFilingRecordListEntryProjection.from_record(record),
        reconciliation=ModeloFilingRecordImportReconciliationProjection.from_result(reconciliation),
    )


def _completion(
    projection: ModeloFilingRecordImportProjection,
    *,
    effect: OperationEffect = OperationEffect.UPDATED,
    terminal_condition: OperationTerminalCondition = OperationTerminalCondition.SUCCEEDED,
    refusal_code: str | None = None,
) -> RegisteredOperationCompletion[ModeloFilingRecordImportProjection]:
    return RegisteredOperationCompletion(
        operation_id=_OPERATION_ID,
        projection=projection,
        effect=effect,
        terminal_condition=terminal_condition,
        refusal_code=refusal_code,
    )


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    completion: RegisteredOperationCompletion[ModeloFilingRecordImportProjection],
    submitted: list[ModeloFilingRecordImportRequest],
) -> None:
    client = SimpleNamespace(profile_id=_PROFILE)
    monkeypatch.setattr(bridge, "bound_profile_client", lambda _ctx: client)

    def submit(
        submitted_client: object,
        request: ModeloFilingRecordImportRequest,
        **kwargs: object,
    ) -> RegisteredOperationCompletion[ModeloFilingRecordImportProjection]:
        assert submitted_client is client
        submitted.append(request)
        assert kwargs == {
            "definition_id": MODELO_FILING_RECORD_IMPORT_OPERATION_DEFINITION_ID,
            "subject_ref": profile_operation_subject(str(_PROFILE)),
            "result_type": ModeloFilingRecordImportProjection,
            "request_version": 1,
            "result_version": 1,
            "timeout": 120,
        }
        return completion

    monkeypatch.setattr(bridge, "run_registered_operation", submit)


def _invoke(
    *,
    casilla_values: Mapping[CasillaId, Decimal] | None = None,
    source_file: Path | None = None,
) -> FilingRecordImportResult:
    return bridge.import_modelo_filing_record(
        cast(typer.Context, cast(object, None)),
        work_unit_id=_WORK_UNIT_ID,
        evidence_kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
        evidence_reference_id=_REFERENCE,
        actor="synthetic import actor",
        declared_kind=FilingDeclarationKind.ORIGINAL,
        casilla_values=casilla_values,
        source_file=source_file,
    )


def test_bridge_distinguishes_direct_values_from_secure_source_path(monkeypatch: pytest.MonkeyPatch) -> None:
    projection = _projection()
    submitted: list[ModeloFilingRecordImportRequest] = []
    _bind(monkeypatch, _completion(projection), submitted)

    result = _invoke(casilla_values={validated_casilla_id("01", surface="test"): Decimal("12.30")})

    assert len(submitted) == 1
    assert submitted[0].casilla_values == ((validated_casilla_id("01", surface="test"), "12.30"),)
    assert submitted[0].source_path is None
    assert result.operation == MODELO_FILING_RECORD_IMPORT_OPERATION_DEFINITION_ID
    assert result.evidence_kind is ExternalEvidenceKind.AEAT_CSV_REGISTER
    assert result.evidence_reference_id == _REFERENCE
    assert result.reconciliation.outcome is FilingReconciliationOutcome.APPENDED
    assert result.external_evidence is not None
    assert result.external_evidence.reference_id == _REFERENCE
    assert "source_transaction_ids" not in result.model_dump_json()
    assert "settlement" not in result.model_dump_json()

    source_path = Path("C:/synthetic/evidence.xlsx").resolve()
    file_projection = _projection()
    file_completion = _completion(file_projection)
    submitted_file: list[ModeloFilingRecordImportRequest] = []
    _bind(monkeypatch, file_completion, submitted_file)

    _invoke(source_file=source_path)

    assert submitted_file[0].casilla_values == ()
    assert submitted_file[0].source_path == str(source_path)


@pytest.mark.parametrize(
    ("outcome", "effect", "source_file", "accepted"),
    [
        (FilingReconciliationOutcome.APPENDED, OperationEffect.UPDATED, None, True),
        (FilingReconciliationOutcome.APPENDED, OperationEffect.NONE, None, False),
        (FilingReconciliationOutcome.ALREADY_RECORDED, OperationEffect.NONE, None, True),
        (FilingReconciliationOutcome.ALREADY_RECORDED, OperationEffect.UPDATED, None, False),
        (FilingReconciliationOutcome.ALREADY_RECORDED, OperationEffect.UPDATED, Path("evidence.xlsx"), True),
    ],
)
def test_bridge_requires_receipt_effect_to_match_reconciliation_and_input_mode(
    monkeypatch: pytest.MonkeyPatch,
    outcome: FilingReconciliationOutcome,
    effect: OperationEffect,
    source_file: Path | None,
    accepted: bool,
) -> None:
    submitted: list[ModeloFilingRecordImportRequest] = []
    _bind(monkeypatch, _completion(_projection(outcome), effect=effect), submitted)

    if accepted:
        _invoke(
            source_file=source_file,
            casilla_values=None
            if source_file is not None
            else {validated_casilla_id("01", surface="test"): Decimal("1")},
        )
    else:
        with pytest.raises(CliRefusedBoundaryError):
            _invoke(
                source_file=source_file,
                casilla_values=None
                if source_file is not None
                else {validated_casilla_id("01", surface="test"): Decimal("1")},
            )
    assert len(submitted) == 1


def test_bridge_rejects_both_or_neither_input_mode_before_submission(monkeypatch: pytest.MonkeyPatch) -> None:
    submitted: list[ModeloFilingRecordImportRequest] = []
    _bind(monkeypatch, _completion(_projection()), submitted)

    with pytest.raises(typer.BadParameter):
        _invoke()
    with pytest.raises(typer.BadParameter):
        _invoke(
            source_file=Path("evidence.xlsx"),
            casilla_values={validated_casilla_id("01", surface="test"): Decimal("1")},
        )
    with pytest.raises(typer.BadParameter):
        _invoke(casilla_values={})
    assert submitted == []


def test_bridge_rejects_unsettled_completion(monkeypatch: pytest.MonkeyPatch) -> None:
    submitted: list[ModeloFilingRecordImportRequest] = []
    _bind(
        monkeypatch,
        _completion(_projection(), terminal_condition=OperationTerminalCondition.REFUSED),
        submitted,
    )

    with pytest.raises(CliRefusedBoundaryError) as refused:
        _invoke(casilla_values={validated_casilla_id("01", surface="test"): Decimal("1")})

    assert refused.value.context is not None
    assert refused.value.context["reason"] == RuntimeRefusalCode.INVALID_FRAME.value
