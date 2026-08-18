"""Record-shape coverage for calc-sheets evidence facets."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from .....core import CasillaId, Period, validated_casilla_id
from .._records import (
    SheetCellAddress,
    SheetEvidenceContributorRow,
    SheetEvidenceFacet,
    SheetEvidenceManualEntry,
    SheetExportMetadata,
    SheetExportPlan,
    SheetGuideContent,
    SheetProvenanceRow,
    SheetRowSet,
    SheetRowSetColumn,
    TabName,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_IVA_DEVENGADO_CUOTA_CASILLA: CasillaId = validated_casilla_id("iva.devengado.cuota")
_RESULTADO_CONTABLE_CASILLA: CasillaId = validated_casilla_id("resultado.contable")
_LEGAL_REFS = ("ley-37-1992:art-99",)
_SOURCE_REFS = ("boe-modelo-303-2025-form",)


def _metadata() -> SheetExportMetadata:
    return SheetExportMetadata(
        modelo_id="303",
        revision_id="2022",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        engine_version="test",
        registry_sha="abcd1234",
        exported_at=datetime(2026, 6, 3, 15, 0, tzinfo=UTC),
    )


def test_sheet_export_plan_carries_typed_evidence_facet() -> None:
    contributor = SheetEvidenceContributorRow(
        casilla_id=_IVA_DEVENGADO_CUOTA_CASILLA,
        transaction_id="c" * 64,
        amount=Decimal("-121.00"),
        currency="EUR",
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("0.21"),
        iva_amount=Decimal("21.00"),
        counterparty="Proveedor SL",
        attachment_ids=("attachment-1",),
        document_link_ids=("drive-doc-1",),
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
    )
    manual = SheetEvidenceManualEntry(
        casilla_id=_RESULTADO_CONTABLE_CASILLA,
        value="140000.00",
        kind="casilla_input",
        note="resultado contable",
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
    )

    plan = SheetExportPlan(
        metadata=_metadata(),
        guide=SheetGuideContent(title="Modelo 303", paragraphs=("Use Entradas.",)),
        evidence=SheetEvidenceFacet(
            snapshot_fingerprint="b" * 64,
            contributor_rows=(contributor,),
            manual_entries=(manual,),
        ),
    )
    restored = SheetExportPlan.model_validate_json(plan.model_dump_json())

    assert restored == plan
    assert restored.evidence.snapshot_fingerprint == "b" * 64
    assert restored.evidence.contributor_rows[0].document_link_ids == ("drive-doc-1",)
    assert restored.evidence.manual_entries[0].note == "resultado contable"


def test_sheet_export_plan_defaults_to_empty_evidence_facet() -> None:
    plan = SheetExportPlan(
        metadata=_metadata(),
        guide=SheetGuideContent(title="Modelo 303", paragraphs=("Use Entradas.",)),
    )

    assert plan.evidence == SheetEvidenceFacet()


def test_sheet_evidence_rejects_short_snapshot_fingerprint() -> None:
    with pytest.raises(ValidationError):
        SheetEvidenceFacet(snapshot_fingerprint="short")


def test_sheet_evidence_rows_require_grounding() -> None:
    with pytest.raises(ValidationError, match="legal_refs"):
        SheetEvidenceContributorRow(
            casilla_id=_IVA_DEVENGADO_CUOTA_CASILLA,
            transaction_id="c" * 64,
            amount=Decimal("121.00"),
            currency="EUR",
            legal_refs=(),
            source_refs=_SOURCE_REFS,
        )

    with pytest.raises(ValidationError, match="source_refs"):
        SheetEvidenceManualEntry(
            casilla_id=_RESULTADO_CONTABLE_CASILLA,
            value="140000.00",
            kind="casilla_input",
            legal_refs=_LEGAL_REFS,
            source_refs=(),
        )


def test_sheet_grounding_rows_reject_blank_ref_entries() -> None:
    with pytest.raises(ValidationError, match="legal_refs"):
        SheetEvidenceContributorRow(
            casilla_id=_IVA_DEVENGADO_CUOTA_CASILLA,
            transaction_id="c" * 64,
            amount=Decimal("121.00"),
            currency="EUR",
            legal_refs=(" ",),
            source_refs=_SOURCE_REFS,
        )

    with pytest.raises(ValidationError, match="source_refs"):
        SheetEvidenceManualEntry(
            casilla_id=_RESULTADO_CONTABLE_CASILLA,
            value="140000.00",
            kind="casilla_input",
            legal_refs=_LEGAL_REFS,
            source_refs=(" ",),
        )

    with pytest.raises(ValidationError, match="legal_refs"):
        SheetProvenanceRow(
            casilla_id=_IVA_DEVENGADO_CUOTA_CASILLA,
            display_number="01",
            casilla_label="IVA devengado",
            formula_id="modelo-303-test-formula",
            rounding_rule="money",
            legal_refs=(" ",),
            source_refs=_SOURCE_REFS,
            target_address=SheetCellAddress.at(TabName.CALCULOS, row=2, column=3),
        )

    row_set_column = SheetRowSetColumn(
        binding="modelo-349-vies-row",
        header_address=SheetCellAddress.at(TabName.DETALLE, row=1, column=1),
        header_label="NIF IVA",
        legal_refs=_LEGAL_REFS,
    )
    with pytest.raises(ValidationError, match="source_refs"):
        SheetRowSet(
            grouping="vies",
            tab=TabName.DETALLE,
            header_row=1,
            first_data_row=2,
            columns=(row_set_column,),
            legal_refs=_LEGAL_REFS,
            source_refs=(" ",),
        )
