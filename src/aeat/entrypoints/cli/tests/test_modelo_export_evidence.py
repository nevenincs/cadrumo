"""Offline modelo export evidence roundtrip coverage."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from io import BytesIO

import pytest
from openpyxl import load_workbook

from ....application.storage.calc_sheets import (
    OfflineWorkbookEvidenceSidecar,
    SheetEvidenceFacet,
    SheetExportMetadata,
    SheetExportPlan,
    SheetGuideContent,
    TabName,
    serialize_offline_export,
    sheet_evidence_from_ledger_filing,
)
from ....application.storage.calc_sheets._errors import CalcSheetsEngineError
from ....core import Period
from ....domain.modelos._ledger_filing_snapshot import LedgerEvidenceRow, LedgerFilingEvidence, ManualFactBasisEntry

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_NOW = datetime(2026, 6, 3, 16, 0, tzinfo=UTC)
_FINGERPRINT = "a" * 64
_SNAPSHOT = "b" * 64


def _ledger_evidence() -> LedgerFilingEvidence:
    return LedgerFilingEvidence(
        snapshot_fingerprint=_SNAPSHOT,
        rows=(
            LedgerEvidenceRow(
                transaction_id="tx-roundtrip-001",
                fingerprint=_FINGERPRINT,
                booked_date="2026-03-31",
                value_date="2026-04-01",
                amount=Decimal("121.00"),
                currency="EUR",
                direction="OUTGOING",
                business_classification="BUSINESS",
                business_pct=Decimal("1"),
                taxable_base=Decimal("100.00"),
                iva_rate=Decimal("0.21"),
                iva_amount=Decimal("21.00"),
                iva_category="domestic_general_21",
                category_id="material_oficina",
                irpf_category="actividad_economica",
                counterparty_eu_member_state="de",
                fx_rate=Decimal("1"),
                value_in_eur=Decimal("121.00"),
                lifecycle_state="ACTIVE",
                counterparty="Proveedor SL",
                description="Compra material oficina",
                purchase_invoice_evidence_id="invoice-evidence-1",
                attachment_ids=("attachment-1",),
                document_link_ids=("drive-doc-1",),
                legal_refs=("liva-art-99",),
                source_refs=("boe-a-2026-1",),
            ),
        ),
        manual_entries=(
            ManualFactBasisEntry(
                casilla="resultado.contable",
                value="140000.00",
                kind="casilla_input",
                note="operator supplied accounting result",
            ),
        ),
        captured_at=_NOW,
    )


def _plan(evidence: SheetEvidenceFacet) -> SheetExportPlan:
    return SheetExportPlan(
        metadata=SheetExportMetadata(
            modelo_id="303",
            revision_id="2009-y-siguientes",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            engine_version="test",
            registry_sha="abcd1234",
            exported_at=_NOW,
        ),
        guide=SheetGuideContent(title="Modelo 303", paragraphs=("Use Entradas.",)),
        evidence=evidence,
    )


def test_offline_export_sidecar_reconstitutes_evidence_casilla_basis() -> None:
    evidence = sheet_evidence_from_ledger_filing(
        _ledger_evidence(),
        contributor_casillas={"tx-roundtrip-001": ("iva.devengado.base", "iva.devengado.cuota")},
    )
    export = serialize_offline_export(_plan(evidence))

    sidecar = OfflineWorkbookEvidenceSidecar.model_validate_json(export.evidence_sidecar_payload)
    workbook = load_workbook(BytesIO(export.workbook_payload), read_only=True)
    try:
        evidencia = workbook[TabName.EVIDENCIA.value]
        assert evidencia["B1"].value == _SNAPSHOT
        assert evidencia["B4"].value == "iva.devengado.base"
        assert evidencia["B5"].value == "iva.devengado.cuota"
        assert evidencia["B6"].value == "resultado.contable"
    finally:
        workbook.close()

    assert sidecar.workbook_sha256 == hashlib.sha256(export.workbook_payload).hexdigest()
    assert sidecar.evidence == evidence
    assert tuple(row.casilla_id for row in sidecar.evidence.contributor_rows) == (
        "iva.devengado.base",
        "iva.devengado.cuota",
    )
    assert sidecar.evidence.manual_entries[0].casilla_id == "resultado.contable"
    assert sidecar.evidence.contributor_rows[0].transaction_id == "tx-roundtrip-001"
    assert sidecar.evidence.contributor_rows[0].legal_refs == ("liva-art-99",)


def test_ledger_evidence_projection_refuses_unattributed_contributor() -> None:
    with pytest.raises(CalcSheetsEngineError, match="casilla attribution"):
        sheet_evidence_from_ledger_filing(_ledger_evidence(), contributor_casillas={})
