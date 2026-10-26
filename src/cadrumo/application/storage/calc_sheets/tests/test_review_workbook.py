"""Saved baselines, honest gaps and bounded review layouts."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from ....export.review_snapshot import ReviewSnapshotContent, seal_review_snapshot
from ..records import TabName
from ..review_workbook import build_review_workbook
from ..workbook_cells import plan_value_blocks
from .review_fixture import review_label, review_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_recorded_amount_is_not_recalculated_from_ledger() -> None:
    snapshot = review_snapshot(amount="99.75")
    plan = build_review_workbook(
        snapshot, publication_id=UUID(int=2), exported_at=datetime(2026, 10, 5, tzinfo=UTC), label=review_label
    )
    cells = {
        address.qualified(): value for block in plan_value_blocks(plan) for address, value in block.addressed_values()
    }
    assert cells["'Cálculos'!D5"] == Decimal("99.75")
    assert cells["'Cálculos'!E5"] == "99.75"
    assert cells["'Cálculos'!I5"] == "'Procedencia'!A5"
    assert cells["'Procedencia'!F5"] == "'Detalle'!A5"
    assert cells["'Procedencia'!H5"] == "'Evidencia'!A5"
    assert cells["'Detalle'!J5"] == Decimal("25.20")
    assert cells["'Evidencia'!C5"] == "missing"
    assert "provisional" in cells.values()
    assert not plan.formula_cells
    assert not plan.protected_ranges
    assert len(cells) == len(plan.value_cells)
    assert len(plan.tabs) == 6


def test_ledger_review_never_invents_a_calculation() -> None:
    plan = build_review_workbook(
        review_snapshot(ledger_only=True),
        publication_id=UUID(int=2),
        exported_at=datetime(2026, 10, 5, tzinfo=UTC),
        label=review_label,
    )
    assert TabName.CALCULOS not in plan.tabs
    assert TabName.TARIFFS not in plan.tabs
    assert plan.metadata.kind == "ledger"
    assert "modelo" not in plan.metadata.model_dump()
    assert all(cell.casilla_id is None for cell in plan.value_cells)
    assert len(plan.tabs) == 5


def test_empty_ledger_has_headers_and_editable_review_rows() -> None:
    snapshot = review_snapshot(ledger_only=True)
    content = ReviewSnapshotContent(selection=snapshot.selection, status=snapshot.status)
    plan = build_review_workbook(
        seal_review_snapshot(content),
        publication_id=UUID(int=2),
        exported_at=datetime(2026, 10, 5, tzinfo=UTC),
        label=review_label,
    )
    assert next(item for item in plan.auto_filters if item.tab is TabName.DETALLE).end_row == 4
    assert next(item for item in plan.auto_filters if item.tab is TabName.ENTRADAS).end_row == 34
    assert all(view.frozen_rows == 4 for view in plan.frozen_views)


def test_formula_looking_source_text_remains_a_literal_plan_value() -> None:
    plan = build_review_workbook(
        review_snapshot(), publication_id=UUID(int=2), exported_at=datetime(2026, 10, 5, tzinfo=UTC), label=review_label
    )
    text = next(cell for cell in plan.value_cells if cell.address.qualified() == "'Detalle'!K5")
    assert text.value == '=IMPORTXML("https://example.invalid", "x")'
    assert not plan.formula_cells


def test_text_output_limit_refuses_instead_of_truncating() -> None:
    with pytest.raises(ValueError, match="cell limit"):
        build_review_workbook(
            review_snapshot(),
            publication_id=UUID(int=2),
            exported_at=datetime(2026, 10, 5, tzinfo=UTC),
            label=lambda _: "x" * 40_001,
        )


def test_large_ledger_is_bounded_and_contains_last_captured_row() -> None:
    snapshot = review_snapshot(ledger_only=True)
    original = snapshot.ledger_rows[0]
    rows = tuple(
        type(original)(**{**original.model_dump(), "transaction_id": f"{index:064x}"}) for index in range(1_000)
    )
    content = ReviewSnapshotContent(selection=snapshot.selection, status=snapshot.status, ledger_rows=rows)
    plan = build_review_workbook(
        seal_review_snapshot(content),
        publication_id=UUID(int=2),
        exported_at=datetime(2026, 10, 5, tzinfo=UTC),
        label=review_label,
    )
    assert (
        next(cell.value for cell in plan.value_cells if cell.address.qualified() == "'Detalle'!A1004") == f"{999:064x}"
    )
    assert len(plan.value_cells) < 60_000


def test_proven_zero_keeps_numeric_zero_and_exact_decimal_text() -> None:
    plan = build_review_workbook(
        review_snapshot(amount="0.00"),
        publication_id=UUID(int=2),
        exported_at=datetime(2026, 10, 5, tzinfo=UTC),
        label=review_label,
    )
    cells = {cell.address.qualified(): cell.value for cell in plan.value_cells}
    assert cells["'Cálculos'!D5"] == Decimal("0")
    assert cells["'Cálculos'!E5"] == "0.00"
