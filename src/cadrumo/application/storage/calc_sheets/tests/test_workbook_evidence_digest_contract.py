"""Real-behavior tests: workbook evidence digests are digests, not 64 characters.

The sidecar and export-result models constrained their SHA-256 fields by
length alone, so ``"z" * 64`` validated. Worse, the sidecar builder took the
digest as an argument without ever seeing the workbook bytes: it asked the
caller to assert the single fact the sidecar exists to carry, and nothing on
the receiving side could check it. A sidecar claiming to bind bytes it had
never seen validated exactly as well as a correct one.

These tests pin both halves -- the canonical digest shape at the model
boundary, and the builder deriving the digest from the bytes it is given, so
the binding a reviewer relies on is true by construction.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from .....core import CasillaId, Period, validated_casilla_id
from .....core.hashing import sha256_hex
from .._records import (
    SheetCellAddress,
    SheetEvidenceContributorRow,
    SheetEvidenceFacet,
    SheetEvidenceManualEntry,
    SheetExportMetadata,
    SheetExportPlan,
    SheetFormulaCell,
    SheetGuideContent,
    SheetValueCell,
    TabName,
)
from .._workbook_export import (
    OfflineWorkbookEvidenceSidecar,
    build_evidence_sidecar,
    serialize_offline_export,
    serialize_offline_workbook,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BASE_CASILLA: CasillaId = validated_casilla_id("base", surface="_BASE_CASILLA")
_CUOTA_CASILLA: CasillaId = validated_casilla_id("cuota", surface="_CUOTA_CASILLA")
_RESULTADO_CONTABLE_CASILLA: CasillaId = validated_casilla_id(
    "resultado.contable",
    surface="_RESULTADO_CONTABLE_CASILLA",
)


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


def _evidence_plan() -> SheetExportPlan:
    return SheetExportPlan(
        metadata=_metadata(),
        value_cells=(
            SheetValueCell(
                address=SheetCellAddress.at(TabName.ENTRADAS, 2, 4),
                value=Decimal("100.00"),
                role="operator_input",
                casilla_id=_BASE_CASILLA,
            ),
        ),
        formula_cells=(
            SheetFormulaCell(
                address=SheetCellAddress.at(TabName.CALCULOS, 2, 4),
                formula="'Entradas'!D2*0.21",
                casilla_id=_CUOTA_CASILLA,
                rounding_rule="money",
                rounding_scale=2,
            ),
        ),
        guide=SheetGuideContent(title="Modelo 303", paragraphs=("Use Entradas.",)),
        evidence=SheetEvidenceFacet(
            snapshot_fingerprint="f" * 64,
            contributor_rows=(
                SheetEvidenceContributorRow(
                    casilla_id=_CUOTA_CASILLA,
                    transaction_id="c" * 64,
                    amount=Decimal("-121.00"),
                    currency="EUR",
                    taxable_base=Decimal("100.00"),
                    iva_rate=Decimal("0.21"),
                    iva_amount=Decimal("21.00"),
                    counterparty="Proveedor SL",
                    attachment_ids=("attachment-1",),
                    document_link_ids=("drive-doc-1",),
                    legal_refs=("ley-37-1992:art-99",),
                    source_refs=("boe-a-2026-1",),
                ),
            ),
            manual_entries=(
                SheetEvidenceManualEntry(
                    casilla_id=_RESULTADO_CONTABLE_CASILLA,
                    value="140000.00",
                    kind="casilla_input",
                    note="operator supplied accounting result",
                    legal_refs=("ley-27-2014:art-10",),
                    source_refs=("operator-manual-evidence",),
                ),
            ),
        ),
    )


_MALFORMED_DIGESTS = (
    "z" * 64,  # non-hex characters
    "A" * 64,  # uppercase: hex, but not the canonical lowercase form
    "0" * 63,  # too short
    "0" * 65,  # too long
)


@pytest.mark.parametrize("digest", _MALFORMED_DIGESTS)
def test_sidecar_refuses_a_non_canonical_digest(digest: str) -> None:
    plan = _evidence_plan()

    with pytest.raises(ValidationError):
        OfflineWorkbookEvidenceSidecar(
            metadata=plan.metadata,
            workbook_sha256=digest,
            evidence=plan.evidence,
        )


def test_the_builder_derives_the_digest_from_the_bytes_it_is_given() -> None:
    plan = _evidence_plan()
    payload = serialize_offline_workbook(plan)

    sidecar = build_evidence_sidecar(plan, workbook_payload=payload)

    assert sidecar.workbook_sha256 == sha256_hex(payload)


def test_a_different_workbook_yields_a_different_binding() -> None:
    """A digest that cannot change with the bytes would bind nothing."""
    plan = _evidence_plan()
    payload = serialize_offline_workbook(plan)

    bound = build_evidence_sidecar(plan, workbook_payload=payload)
    other = build_evidence_sidecar(plan, workbook_payload=payload + b"\x00")

    assert bound.workbook_sha256 != other.workbook_sha256


def test_the_export_result_digests_match_the_payloads_they_name() -> None:
    result = serialize_offline_export(_evidence_plan())

    assert result.workbook_sha256 == sha256_hex(result.workbook_payload)
    assert result.evidence_sidecar_sha256 == sha256_hex(result.evidence_sidecar_payload)
