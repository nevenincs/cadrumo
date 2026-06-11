"""Record-shape coverage for calc-sheets evidence facets."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from .....core import Period
from .._records import (
    SheetEvidenceContributorRow,
    SheetEvidenceFacet,
    SheetEvidenceManualEntry,
    SheetExportMetadata,
    SheetExportPlan,
    SheetGuideContent,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _metadata() -> SheetExportMetadata:
    return SheetExportMetadata(
        modelo_id="303",
        revision_id="2009-y-siguientes",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        engine_version="test",
        registry_sha="abcd1234",
        exported_at=datetime(2026, 6, 3, 15, 0, tzinfo=UTC),
    )


def test_sheet_export_plan_carries_typed_evidence_facet() -> None:
    contributor = SheetEvidenceContributorRow(
        casilla_id="iva.devengado.cuota",
        transaction_id="c" * 64,
        amount=Decimal("-121.00"),
        currency="EUR",
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("0.21"),
        iva_amount=Decimal("21.00"),
        counterparty="Proveedor SL",
        attachment_ids=("attachment-1",),
        document_link_ids=("drive-doc-1",),
        legal_refs=("liva-art-99",),
        source_refs=("boe-a-2026-1",),
    )
    manual = SheetEvidenceManualEntry(
        casilla_id="resultado.contable",
        value="140000.00",
        kind="casilla_input",
        note="resultado contable",
        legal_refs=("lis-art-10",),
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
