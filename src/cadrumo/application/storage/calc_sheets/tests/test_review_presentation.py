"""Visible gaps, complete captured facts and explicit review navigation."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from ....export.review_snapshot import ReviewSnapshot, ReviewSnapshotContent, ReviewSourceKind, seal_review_snapshot
from ..records import SheetExportPlan, SheetReviewMetadata, TabName
from ..review_workbook import build_review_workbook
from .review_fixture import review_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _render(snapshot: ReviewSnapshot) -> SheetExportPlan[SheetReviewMetadata]:
    return build_review_workbook(
        snapshot,
        publication_id=UUID(int=2),
        exported_at=datetime(2026, 10, 5, tzinfo=UTC),
        label=lambda key: key,
    )


def _row(plan: SheetExportPlan[SheetReviewMetadata], tab: TabName, row: int) -> dict[str, object]:
    headers = {
        cell.address.column: str(cell.value)
        for cell in plan.value_cells
        if cell.address.tab is tab and cell.address.row == 4
    }
    return {
        headers[cell.address.column]: cell.value
        for cell in plan.value_cells
        if cell.address.tab is tab and cell.address.row == row
    }


def test_optional_uncaptured_facts_stay_distinct_from_zero_and_empty_text() -> None:
    snapshot = review_snapshot()
    original = snapshot.ledger_rows[0]
    ledger = type(original).model_validate(
        {**original.model_dump(), "value_in_eur": Decimal("0.00"), "recargo_amount": Decimal("0.000")}
    )
    content = ReviewSnapshotContent.model_validate(
        {**snapshot.model_dump(exclude={"snapshot_digest"}), "ledger_rows": (ledger,)}
    )
    plan = _render(seal_review_snapshot(content))
    row = _row(plan, TabName.DETALLE, 5)
    assert row["value_date"] == "not_captured"
    assert row["fx_rate"] == "not_captured"
    assert row["exact_fx_rate"] == "not_captured"
    assert row["eur_value"] == Decimal("0.00")
    assert row["exact_eur_value"] == "0.00"
    assert row["recargo_amount"] == Decimal("0.000")
    assert row["exact_recargo_amount"] == "0.000"
    assert row["description"] == ""
    assert all(cell.value is not None for cell in plan.value_cells if cell.address.tab is not TabName.ENTRADAS)
    assert all(
        cell.value is None
        for cell in plan.value_cells
        if cell.address.tab is TabName.ENTRADAS and cell.address.row >= 5
    )


def test_ledger_details_retain_captured_deduction_prorrata_and_exact_values() -> None:
    snapshot = review_snapshot()
    original = snapshot.ledger_rows[0]
    ledger = type(original).model_validate(
        {
            **original.model_dump(),
            "description": "=external text",
            "usage_ratio_id": "ratio-1",
            "deduction_fact_kind": "captured-deduction",
            "art_104_tres_exclusion": "captured-exclusion",
            "input_classification": "captured-input",
            "prorrata_sector_id": "sector-1",
            "prorrata_reference": "ref-1",
            "fx_rate": Decimal("1.12345678901234567890"),
            "business_pct": Decimal("0.6000"),
            "iva_rate": Decimal("0.2100"),
            "m210_official_tipo_renta_code": "01",
            "m210_gross_income_amount": Decimal("234.5678901234567890"),
            "m210_applicable_rate": Decimal("0.1900"),
            "m210_payer_mode": "captured-payer",
            "m210_payer_id": "payer-1",
            "m210_asset_or_right_id": "asset-1",
        }
    )
    content = ReviewSnapshotContent.model_validate(
        {**snapshot.model_dump(exclude={"snapshot_digest"}), "ledger_rows": (ledger,)}
    )
    plan = _render(seal_review_snapshot(content))
    row = _row(plan, TabName.DETALLE, 5)
    for name in (
        "description",
        "lifecycle_state",
        "usage_ratio_id",
        "deduction_fact_kind",
        "art_104_tres_exclusion",
        "input_classification",
        "prorrata_sector_id",
        "prorrata_reference",
        "m210_official_tipo_renta_code",
        "m210_payer_mode",
        "m210_payer_id",
        "m210_asset_or_right_id",
    ):
        assert row[name] == getattr(ledger, name)
    assert row["exact_fx_rate"] == "1.12345678901234567890"
    assert row["exact_business_pct"] == "0.6000"
    assert row["exact_iva_rate"] == "0.2100"
    assert row["exact_m210_gross_income_amount"] == "234.5678901234567890"
    assert row["exact_m210_applicable_rate"] == "0.1900"
    assert not plan.formula_cells


def test_exact_decimal_text_retains_saved_exponents_and_negative_zero() -> None:
    snapshot = review_snapshot(amount="1E+3")
    original = snapshot.ledger_rows[0]
    ledger = type(original).model_validate(
        {
            **original.model_dump(),
            "amount": Decimal("1E+2"),
            "fx_rate": Decimal("1E-20"),
            "taxable_base": Decimal("-0.00"),
        }
    )
    content = ReviewSnapshotContent.model_validate(
        {**snapshot.model_dump(exclude={"snapshot_digest"}), "ledger_rows": (ledger,)}
    )
    plan = _render(seal_review_snapshot(content))
    assert _row(plan, TabName.CALCULOS, 5)["exact_value"] == "1E+3"
    assert _row(plan, TabName.DETALLE, 5)["exact_amount"] == "1E+2"
    assert _row(plan, TabName.DETALLE, 5)["exact_fx_rate"] == "1E-20"
    assert _row(plan, TabName.DETALLE, 5)["exact_taxable_base"] == "-0.00"


def test_unreferenced_ledger_contribution_does_not_claim_result_support() -> None:
    snapshot = review_snapshot(ledger_only=True)
    plan = _render(snapshot)
    assert _row(plan, TabName.DETALLE, 5)["sources"] == "'Procedencia'!A5"
    assert _row(plan, TabName.DETALLE, 5)["results"] == "unattributed"
    assert _row(plan, TabName.PROVENANCE, 5)["results"] == "unattributed"
    assert TabName.CALCULOS not in plan.tabs


def test_navigation_connects_only_captured_source_result_and_inventory_ids() -> None:
    plan = _render(review_snapshot())
    assert _row(plan, TabName.DETALLE, 5)["results"] == "'Cálculos'!A5"
    assert _row(plan, TabName.DETALLE, 5)["evidence"] == "'Evidencia'!A5"
    inventory = _row(plan, TabName.EVIDENCIA, 5)
    assert inventory["sources"] == "'Procedencia'!A5"
    assert inventory["disposition"] == "missing"
    assert inventory["availability"] == "evidence_missing"
    assert _row(plan, TabName.PROVENANCE, 5)["source_kind"] == "source_kind_ledger_row"


def test_ledger_evidence_navigation_follows_captured_contribution_inventory_refs() -> None:
    snapshot = review_snapshot()
    original = snapshot.ledger_rows[0]
    ledger = type(original).model_validate({**original.model_dump(), "attachment_ids": (), "document_link_ids": ()})
    content = ReviewSnapshotContent.model_validate(
        {**snapshot.model_dump(exclude={"snapshot_digest"}), "ledger_rows": (ledger,)}
    )
    plan = _render(seal_review_snapshot(content))
    assert _row(plan, TabName.DETALLE, 5)["attachments"] == ""
    assert _row(plan, TabName.DETALLE, 5)["evidence"] == "'Evidencia'!A5"
    assert _row(plan, TabName.PROVENANCE, 5)["evidence"] == "'Evidencia'!A5"
    assert _row(plan, TabName.EVIDENCIA, 5)["sources"] == "'Procedencia'!A5"


def test_invoice_identifier_is_not_interpreted_as_an_evidence_identifier() -> None:
    snapshot = review_snapshot()
    original = snapshot.ledger_rows[0]
    ledger = type(original).model_validate(
        {**original.model_dump(), "attachment_ids": (), "document_link_ids": (), "invoice_id": "invoice-1"}
    )
    source = type(snapshot.contributions[0]).model_validate(
        {**snapshot.contributions[0].model_dump(), "evidence_ids": ()}
    )
    content = ReviewSnapshotContent.model_validate(
        {**snapshot.model_dump(exclude={"snapshot_digest"}), "ledger_rows": (ledger,), "contributions": (source,)}
    )
    plan = _render(seal_review_snapshot(content))
    assert _row(plan, TabName.DETALLE, 5)["invoice"] == "invoice-1"
    assert _row(plan, TabName.DETALLE, 5)["evidence"] == "no_inventory_reference"


def test_linked_invoice_navigates_through_its_explicit_captured_evidence_refs() -> None:
    snapshot = review_snapshot()
    original = snapshot.ledger_rows[0]
    ledger = type(original).model_validate(
        {**original.model_dump(), "attachment_ids": (), "document_link_ids": (), "invoice_id": "linked-invoice"}
    )
    source = type(snapshot.contributions[0]).model_validate(
        {**snapshot.contributions[0].model_dump(), "kind": ReviewSourceKind.INVOICE, "source_id": "linked-invoice"}
    )
    content = ReviewSnapshotContent.model_validate(
        {**snapshot.model_dump(exclude={"snapshot_digest"}), "ledger_rows": (ledger,), "contributions": (source,)}
    )
    plan = _render(seal_review_snapshot(content))
    assert _row(plan, TabName.DETALLE, 5)["invoice"] == "linked-invoice"
    assert _row(plan, TabName.DETALLE, 5)["evidence"] == "'Evidencia'!A5"
    assert _row(plan, TabName.PROVENANCE, 5)["ledger"] == "not_ledger_source"


@pytest.mark.parametrize("kind", (ReviewSourceKind.MANUAL_INPUT, ReviewSourceKind.ADJUSTMENT, ReviewSourceKind.INVOICE))
def test_non_ledger_sources_keep_their_own_identity_and_saved_value(kind: ReviewSourceKind) -> None:
    snapshot = review_snapshot()
    original = snapshot.contributions[0]
    contribution = type(original).model_validate(
        {**original.model_dump(), "kind": kind, "source_id": "captured-non-ledger", "source_revision": None}
    )
    content = ReviewSnapshotContent.model_validate(
        {**snapshot.model_dump(exclude={"snapshot_digest"}), "contributions": (contribution,)}
    )
    plan = _render(seal_review_snapshot(content))
    source = _row(plan, TabName.PROVENANCE, 5)
    assert source["kind"] == kind.value
    assert source["source_id"] == "captured-non-ledger"
    assert source["source_revision"] == "not_captured"
    assert source["ledger"] == "not_ledger_source"
    assert source["results"] == "'Cálculos'!A5"
    assert source["source_kind"] == "source_kind_" + kind.value
    assert _row(plan, TabName.DETALLE, 5)["results"] == "unattributed"
    assert _row(plan, TabName.CALCULOS, 5)["value"] == Decimal("25.20")


def test_empty_sections_disclose_empty_snapshot_without_dummy_data_rows() -> None:
    original = review_snapshot(ledger_only=True)
    plan = _render(seal_review_snapshot(ReviewSnapshotContent(selection=original.selection, status=original.status)))
    for tab in (TabName.DETALLE, TabName.PROVENANCE, TabName.EVIDENCIA):
        notice = next(cell.value for cell in plan.value_cells if cell.address.tab is tab and cell.address.row == 2)
        assert isinstance(notice, str) and "no_captured_rows" in notice
        assert not [cell for cell in plan.value_cells if cell.address.tab is tab and cell.address.row >= 5]
    assert _row(plan, TabName.ENTRADAS, 5)["finding"] is None


def test_dense_output_refuses_instead_of_dropping_captured_rows() -> None:
    snapshot = review_snapshot(ledger_only=True)
    original = snapshot.ledger_rows[0]
    rows = tuple(
        type(original)(**{**original.model_dump(), "transaction_id": f"{index:064x}"}) for index in range(5_000)
    )
    content = ReviewSnapshotContent(selection=snapshot.selection, status=snapshot.status, ledger_rows=rows)
    with pytest.raises(ValueError, match="output limits"):
        _render(seal_review_snapshot(content))
