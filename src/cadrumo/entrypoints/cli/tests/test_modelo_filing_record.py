"""CLI Modelo filing-record rendering tests."""

from __future__ import annotations

import pytest

from ....core.period import Period

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_filing_record_payload_renders_external_evidence_and_amends() -> None:
    """The JSON-format emitter for ``aeat app modelo filing-record show``
    surfaces both ``external_evidence`` (kind / reference_id / imported_at)
    and ``amends_filing_record_id`` so amendment chains are operator-discoverable
    from the record's own listing surface, not only via the amend action."""

    from datetime import UTC, datetime

    from ....domain.modelos.codes import ModeloCode
    from ....domain.modelos.filing_record import (
        ExternalEvidence,
        ExternalEvidenceKind,
        ModeloRecord,
        ModeloRecordStatus,
        derive_filing_record_id,
    )
    from .._modelo_payloads import FilingRecordImportResult, ModeloRecordShowResult, WorkAmendResult
    from .._modelo_rendering import filing_record_payload as _filing_record_payload

    imported_at = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
    filed_at = datetime(2026, 4, 16, 12, 0, 0, tzinfo=UTC)
    work_unit_id = "a" * 64
    revision_id = "c" * 64
    amends_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id="d" * 64,
        filed_by="aeat-import",
    )
    record = ModeloRecord(
        filing_record_id=derive_filing_record_id(
            work_unit_id=work_unit_id,
            calculation_revision_id=revision_id,
            filed_by="operator-A",
        ),
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        bucket_id="default",
        modelo=ModeloCode("130"),
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        filed_at=filed_at,
        filed_by="operator-A",
        notes=None,
        aeat_accepted=True,
        status=ModeloRecordStatus.VIGENTE,
        external_evidence=ExternalEvidence(
            kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            reference_id="JUST-2026-130-1T-XYZ789",
            imported_at=imported_at,
        ),
        amends_filing_record_id=amends_id,
    )

    payload = _filing_record_payload(record)

    assert payload.amends_filing_record_id == amends_id
    evidence = payload.external_evidence
    assert evidence is not None
    assert evidence.kind is ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF
    assert evidence.reference_id == "JUST-2026-130-1T-XYZ789"
    assert evidence.imported_at == imported_at
    payload_dict = payload.model_dump(mode="python")
    show_result = ModeloRecordShowResult.model_validate(payload_dict)
    # evidence_kind and evidence_reference_id are DERIVED from the evidence row
    # now, so they are not supplied -- and supplying them is refused.
    import_result = FilingRecordImportResult.model_validate(payload_dict)
    assert import_result.evidence_kind is evidence.kind
    assert import_result.evidence_reference_id == evidence.reference_id
    amend_result = WorkAmendResult.model_validate({"amendment_kind": "complementaria", **payload_dict})
    assert show_result.external_evidence is not None
    assert import_result.external_evidence is not None
    assert amend_result.external_evidence is not None


def test_import_payload_rejects_external_evidence_that_differs_from_import_metadata() -> None:
    """The import result cannot relabel or detach the official evidence it reports."""

    from datetime import UTC, datetime

    from pydantic import ValidationError

    from ....domain.modelos.filing_record import ExternalEvidenceKind, ModeloRecordStatus
    from .._modelo_payloads import FilingRecordImportResult

    payload = {
        "evidence_kind": ExternalEvidenceKind.AEAT_CSV_REGISTER,
        "evidence_reference_id": "CSV-303-2026-Q1",
        "filing_record_id": "a" * 64,
        "work_unit_id": "b" * 64,
        "calculation_revision_id": "c" * 64,
        "bucket_id": "default",
        "modelo": "303",
        "filing_year": 2026,
        "period": Period.from_year_and_code(2026, "1T"),
        "filed_at": datetime(2026, 4, 16, 12, 0, tzinfo=UTC),
        "filed_by": "operator-A",
        "aeat_accepted": True,
        "status": ModeloRecordStatus.VIGENTE,
        "external_evidence": {
            "kind": ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            "reference_id": "CSV-303-2026-Q1",
            "imported_at": datetime(2026, 4, 16, 12, 0, tzinfo=UTC),
        },
    }

    # The two flat fields are derived from ``external_evidence`` rather than
    # accepted beside it, so the divergence this test names cannot be built at
    # all: the payload is refused for SUPPLYING them, not for disagreeing.
    #
    # That is a stronger guarantee than the validator it replaced. A check that
    # two inputs agree can only fire when someone remembers to run it; a value
    # with one source has nothing to disagree with.
    with pytest.raises(ValidationError, match="evidence_kind"):
        FilingRecordImportResult.model_validate(payload)

    derived = FilingRecordImportResult.model_validate(
        {k: v for k, v in payload.items() if k not in {"evidence_kind", "evidence_reference_id"}},
    )
    assert derived.evidence_kind is ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF
    assert derived.evidence_reference_id == "CSV-303-2026-Q1"


def test_filing_record_payload_omits_evidence_fields_when_absent() -> None:
    """A locally-filed record (no external_evidence, no amends link)
    surfaces those fields as ``None`` in JSON so downstream consumers
    can rely on the schema shape without optional-key checks."""

    from datetime import UTC, datetime

    from ....domain.modelos.codes import ModeloCode
    from ....domain.modelos.filing_record import ModeloRecord, ModeloRecordStatus, derive_filing_record_id
    from .._modelo_payloads import ModeloRecordShowResult, WorkFileResult
    from .._modelo_rendering import filing_record_payload as _filing_record_payload

    work_unit_id = "a" * 64
    revision_id = "c" * 64
    filed_at = datetime(2026, 4, 16, 12, 0, 0, tzinfo=UTC)
    record = ModeloRecord(
        filing_record_id=derive_filing_record_id(
            work_unit_id=work_unit_id,
            calculation_revision_id=revision_id,
            filed_by="operator-A",
        ),
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        bucket_id="default",
        modelo=ModeloCode("130"),
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        filed_at=filed_at,
        filed_by="operator-A",
        notes=None,
        aeat_accepted=False,
        status=ModeloRecordStatus.VIGENTE,
    )

    payload = _filing_record_payload(record)

    assert payload.external_evidence is None
    assert payload.amends_filing_record_id is None
    payload_dict = payload.model_dump(mode="python")
    file_result = WorkFileResult.model_validate(payload_dict)
    show_result = ModeloRecordShowResult.model_validate(payload_dict)
    assert file_result.external_evidence is None
    assert file_result.amends_filing_record_id is None
    assert show_result.external_evidence is None
    assert show_result.amends_filing_record_id is None


def test_filing_record_lines_renders_external_evidence_and_amends_in_text_mode() -> None:
    """The text-format emitter surfaces ``external_evidence.{kind, reference_id,
    imported_at}`` and ``amends_filing_record_id`` as discrete tab-separated
    lines so operators reading ``--format text`` see the amendment context."""

    from datetime import UTC, datetime

    from ....domain.modelos.codes import ModeloCode
    from ....domain.modelos.filing_record import (
        ExternalEvidence,
        ExternalEvidenceKind,
        ModeloRecord,
        ModeloRecordStatus,
        derive_filing_record_id,
    )
    from .._modelo_rendering import filing_record_lines as _filing_record_lines

    imported_at = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
    work_unit_id = "a" * 64
    revision_id = "c" * 64
    filed_at = datetime(2026, 4, 16, 12, 0, 0, tzinfo=UTC)
    amends_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id="d" * 64,
        filed_by="aeat-import",
    )
    record = ModeloRecord(
        filing_record_id=derive_filing_record_id(
            work_unit_id=work_unit_id,
            calculation_revision_id=revision_id,
            filed_by="operator-A",
        ),
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        bucket_id="default",
        modelo=ModeloCode("130"),
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        filed_at=filed_at,
        filed_by="operator-A",
        notes=None,
        aeat_accepted=True,
        status=ModeloRecordStatus.VIGENTE,
        external_evidence=ExternalEvidence(
            kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
            reference_id="CSV-303-2026-Q1",
            imported_at=imported_at,
        ),
        amends_filing_record_id=amends_id,
    )

    lines = _filing_record_lines(record)

    assert "external_evidence.kind\taeat_csv_register" in lines
    assert "external_evidence.reference_id\tCSV-303-2026-Q1" in lines
    assert f"external_evidence.imported_at\t{imported_at.isoformat()}" in lines
    assert f"amends_filing_record_id\t{amends_id}" in lines
