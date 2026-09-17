"""CLI Modelo filing-record rendering tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ....application.modelo.filing_chain_reconciliation import FilingReconciliationOutcome
from ....core.period import Period
from ....domain.modelos.codes import ModeloCode
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
from .._filing_chain_payloads import FilingReconciliationPayload, ObservationLayersPayload
from .._modelo_payloads import FilingRecordImportResult, ModeloRecordShowResult, WorkAmendResult, WorkFileResult
from .._modelo_rendering import filing_record_lines, filing_record_payload

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_WORK_UNIT_ID = "a" * 64
_REVISION_ID = "c" * 64
_PERIOD = Period.from_year_and_code(2026, "1T")
_IMPORTED_AT = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
_FILED_AT = datetime(2026, 4, 16, 12, 0, 0, tzinfo=UTC)
_AMENDS_ID = derive_filing_record_id(
    work_unit_id=_WORK_UNIT_ID, calculation_revision_id="d" * 64, filed_by="aeat-import"
)


def _confirmed_complementaria(evidence_kind: ExternalEvidenceKind, reference_id: str) -> ModeloRecord:
    return ModeloRecord(
        filing_record_id=derive_filing_record_id(
            work_unit_id=_WORK_UNIT_ID,
            calculation_revision_id=_REVISION_ID,
            filed_by="operator-A",
        ),
        work_unit_id=_WORK_UNIT_ID,
        calculation_revision_id=_REVISION_ID,
        bucket_id="default",
        modelo=ModeloCode("130"),
        filing_year=2026,
        period=_PERIOD,
        filed_at=_FILED_AT,
        filed_by="operator-A",
        origin=FilingOrigin.AEAT,
        confirmation=AeatConfirmationState.CONFIRMADA,
        declaration_kind=FilingDeclarationKind.COMPLEMENTARIA,
        aeat_register=AeatRegisterRef(expediente_id="202613000000002Z", tipo_solicitud="complementaria"),
        status=ModeloRecordStatus.VIGENTE,
        external_evidence=ExternalEvidence(kind=evidence_kind, reference_id=reference_id, imported_at=_IMPORTED_AT),
        amends_filing_record_id=_AMENDS_ID,
    )


def _reconciliation(record: ModeloRecord) -> FilingReconciliationPayload:
    return FilingReconciliationPayload(
        outcome=FilingReconciliationOutcome.APPENDED,
        bucket_id=record.bucket_id,
        modelo=str(record.modelo),
        filing_year=record.filing_year,
        period=record.period,
        filing_record_id=record.filing_record_id,
        evidence_basis="casillas",
    )


def test_filing_record_payload_renders_chain_evidence_and_amends() -> None:
    """The record projection carries the chain entry, its register ref, its evidence and its amends link."""
    record = _confirmed_complementaria(ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF, "JUST-2026-130-1T-XYZ789")

    payload = filing_record_payload(record)

    assert payload.amends_filing_record_id == _AMENDS_ID
    assert payload.origin is FilingOrigin.AEAT
    assert payload.confirmation is AeatConfirmationState.CONFIRMADA
    assert payload.declaration_kind is FilingDeclarationKind.COMPLEMENTARIA
    assert payload.aeat_accepted is True
    assert payload.aeat_register is not None
    assert payload.aeat_register.expediente_id == "202613000000002Z"
    evidence = payload.external_evidence
    assert evidence is not None
    assert evidence.kind is ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF
    assert evidence.reference_id == "JUST-2026-130-1T-XYZ789"
    assert evidence.imported_at == _IMPORTED_AT
    payload_dict = payload.model_dump(mode="python")
    show_result = ModeloRecordShowResult.model_validate(
        {**payload_dict, "observation_layers": ObservationLayersPayload()},
    )
    import_result = FilingRecordImportResult.model_validate(
        {**payload_dict, "reconciliation": _reconciliation(record)},
    )
    assert import_result.evidence_kind is evidence.kind
    assert import_result.evidence_reference_id == evidence.reference_id
    assert import_result.reconciliation.outcome is FilingReconciliationOutcome.APPENDED
    amend_result = WorkAmendResult.model_validate(
        {"amendment_kind": "complementaria", "m303_rectificativa_motive": None, **payload_dict},
    )
    assert show_result.external_evidence is not None
    assert amend_result.external_evidence is not None


def test_import_payload_derives_evidence_fields_and_refuses_supplied_ones() -> None:
    """The import result cannot relabel the official evidence it reports."""
    record = _confirmed_complementaria(ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF, "CSV-303-2026-Q1")
    payload = {
        **filing_record_payload(record).model_dump(mode="python"),
        "reconciliation": _reconciliation(record),
    }

    with pytest.raises(ValidationError, match="evidence_kind"):
        FilingRecordImportResult.model_validate({**payload, "evidence_kind": ExternalEvidenceKind.AEAT_CSV_REGISTER})

    derived = FilingRecordImportResult.model_validate(payload)
    assert derived.evidence_kind is ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF
    assert derived.evidence_reference_id == "CSV-303-2026-Q1"


def test_record_payload_refuses_acceptance_that_contradicts_confirmation() -> None:
    """``aeat_accepted`` follows the confirmation state, so a pending entry cannot claim acceptance."""
    record = _confirmed_complementaria(ExternalEvidenceKind.AEAT_LIVE_CAPTURE, "live-ref")
    payload = filing_record_payload(record).model_dump(mode="python")

    with pytest.raises(ValidationError, match="confirmation"):
        WorkFileResult.model_validate({**payload, "confirmation": AeatConfirmationState.PENDIENTE})


def test_filing_record_payload_keeps_absent_evidence_and_links_explicit() -> None:
    """A pending local entry renders no evidence, register or amends link."""
    record = ModeloRecord(
        filing_record_id=derive_filing_record_id(
            work_unit_id=_WORK_UNIT_ID,
            calculation_revision_id=_REVISION_ID,
            filed_by="operator-A",
        ),
        work_unit_id=_WORK_UNIT_ID,
        calculation_revision_id=_REVISION_ID,
        bucket_id="default",
        modelo=ModeloCode("130"),
        filing_year=2026,
        period=_PERIOD,
        filed_at=_FILED_AT,
        filed_by="operator-A",
        origin=FilingOrigin.LOCAL,
        confirmation=AeatConfirmationState.PENDIENTE,
        declaration_kind=FilingDeclarationKind.ORIGINAL,
        status=ModeloRecordStatus.VIGENTE,
    )

    payload = filing_record_payload(record)

    assert payload.external_evidence is None
    assert payload.amends_filing_record_id is None
    assert payload.aeat_register is None
    assert payload.aeat_accepted is False
    file_result = WorkFileResult.model_validate(payload.model_dump(mode="python"))
    assert file_result.confirmation is AeatConfirmationState.PENDIENTE
    assert file_result.external_evidence is None


def test_filing_record_lines_render_chain_evidence_and_amends_in_text_mode() -> None:
    """Text mode shows the chain fields, register ref, evidence and amends link as discrete lines."""
    record = _confirmed_complementaria(ExternalEvidenceKind.AEAT_CSV_REGISTER, "CSV-303-2026-Q1")

    lines = filing_record_lines(record)

    assert "origin\taeat" in lines
    assert "confirmation\tconfirmada" in lines
    assert "declaration_kind\tcomplementaria" in lines
    assert "aeat_register.expediente_id\t202613000000002Z" in lines
    assert "aeat_register.tipo_solicitud\tcomplementaria" in lines
    assert "external_evidence.kind\taeat_csv_register" in lines
    assert "external_evidence.reference_id\tCSV-303-2026-Q1" in lines
    assert f"external_evidence.imported_at\t{_IMPORTED_AT.isoformat()}" in lines
    assert f"amends_filing_record_id\t{_AMENDS_ID}" in lines
