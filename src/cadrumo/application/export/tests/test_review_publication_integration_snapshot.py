"""Real saved-baseline rehydration and workbook preparation, without Google transport.

These checks establish local projection integration only. They do not replace
saved canonical revision loading, admitted provider publication or user review.
"""

import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest
from pydantic import ValidationError

from ...storage.calc_sheets.records import SheetExportPlan, SheetReviewMetadata, TabName
from ...storage.calc_sheets.workbook_cells import SheetCellValue, plan_value_blocks
from .. import google_operation
from ..google_operation import prepare_google_review_plan
from ..publication_receipt import PublicationReceipt
from ..review_snapshot import ReviewSnapshot
from .review_publication_fixture import (
    EXPECTED_SELECTED_AMOUNTS,
    EXPORTED_AT,
    LITERAL_COUNTERPARTY,
    PROFILE_ID,
    acceptance_authorization,
    acceptance_label,
    acceptance_publication,
    completed_acceptance_receipt,
    save_acceptance_snapshot,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


@pytest.fixture(autouse=True)
def admitted_local_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate active-profile policy; keep snapshot parsing and projection real."""
    monkeypatch.setattr(google_operation, "require_active_bucket_id", lambda: str(PROFILE_ID))
    monkeypatch.setattr(google_operation, "resolve_active_capability", lambda _: SimpleNamespace(enabled=True))


def _prepare(snapshot: ReviewSnapshot, publication: PublicationReceipt) -> SheetExportPlan[SheetReviewMetadata]:
    return prepare_google_review_plan(
        snapshot,
        selection=snapshot.selection,
        publication=publication,
        authorization=acceptance_authorization(publication, ledger_only=snapshot.selection.kind == "ledger"),
        exported_at=EXPORTED_AT,
        label=acceptance_label,
    )


def _table(plan: SheetExportPlan[SheetReviewMetadata], tab: TabName) -> list[dict[str, SheetCellValue]]:
    """Read semantic headers from the actual shared addressed value stream."""
    cells = {
        (address.row, address.column): value
        for block in plan_value_blocks(plan)
        for address, value in block.addressed_values()
        if address.tab is tab
    }
    headers = {column: str(value) for (row, column), value in cells.items() if row == 4}
    return [
        {header: cells.get((row, column)) for column, header in headers.items()}
        for row in sorted({row for row, _ in cells if row >= 5})
    ]


def test_selected_saved_baseline_survives_newer_local_record_and_projects_independent_values(tmp_path: Path) -> None:
    selected_path = save_acceptance_snapshot(tmp_path)
    newer_path = save_acceptance_snapshot(tmp_path, newer_revision=True)
    selected_bytes, newer_bytes = selected_path.read_bytes(), newer_path.read_bytes()
    selected = ReviewSnapshot.model_validate_json(selected_bytes)
    newer = ReviewSnapshot.model_validate_json(newer_bytes)

    plan = _prepare(selected, acceptance_publication(selected))
    results = _table(plan, TabName.CALCULOS)
    expected = EXPECTED_SELECTED_AMOUNTS
    assert {row["amount_id"]: row["exact_value"] for row in results} == expected
    assert {row["amount_id"]: row["value"] for row in results} == {
        "recorded-iva": Decimal("99.75"),
        "proven-zero": Decimal("0.00"),
        "adjustment": Decimal("-3.50"),
    }
    assert selected.selection != newer.selection
    assert newer.amounts[0].value == Decimal("888.88")
    assert _table(plan, TabName.DETALLE)[0]["iva_amount"] == Decimal("25.20")
    assert plan.metadata.snapshot_digest == selected.snapshot_digest
    assert selected_path.read_bytes() == selected_bytes
    assert newer_path.read_bytes() == newer_bytes


def test_capture_attribution_missing_payload_and_manual_basis_remain_explicit(tmp_path: Path) -> None:
    snapshot = ReviewSnapshot.model_validate_json(save_acceptance_snapshot(tmp_path).read_bytes())
    plan = _prepare(snapshot, acceptance_publication(snapshot))
    results = _table(plan, TabName.CALCULOS)
    sources = _table(plan, TabName.PROVENANCE)
    ledger = _table(plan, TabName.DETALLE)
    inventory = _table(plan, TabName.EVIDENCIA)

    assert results[0]["sources"] == "'Procedencia'!A5\n'Procedencia'!A7"
    assert results[1]["sources"] == "'Procedencia'!A6"
    assert sources[0]["ledger"] == "'Detalle'!A5"
    assert sources[0]["evidence"] == "'Evidencia'!A5"
    assert sources[1]["kind"] == "manual_input"
    assert sources[1]["ledger"] == "not_ledger_source"
    assert sources[2]["kind"] == "adjustment"
    assert sources[2]["results"] == "'Cálculos'!A5\n'Cálculos'!A7"
    assert ledger[1]["sources"] == "No captured calculation attribution"
    assert inventory[0]["disposition"] == "missing"
    assert inventory[0]["digest"] == "not_captured"
    assert inventory[0]["reason"] == "Historical payload was not captured"
    assert snapshot.status.value == "provisional"
    assert any("do not substitute current evidence" in str(cell.value) for cell in plan.value_cells)


def test_saved_literal_values_do_not_enter_intentional_formula_stream(tmp_path: Path) -> None:
    snapshot = ReviewSnapshot.model_validate_json(save_acceptance_snapshot(tmp_path).read_bytes())
    plan = _prepare(snapshot, acceptance_publication(snapshot))
    values = tuple(value for block in plan_value_blocks(plan) for _, value in block.addressed_values())
    for literal in (
        LITERAL_COUNTERPARTY,
        "+unattributed-literal",
        "+manual-literal",
        "@manual-note-literal",
        "-adjustment-literal",
        "=adjustment-note-literal",
        "=literal-recorded-reference",
        "=invoice-literal",
    ):
        assert literal in values
    assert plan.formula_cells == ()


def test_standalone_ledger_has_its_own_selection_and_no_calculation_authority(tmp_path: Path) -> None:
    snapshot = ReviewSnapshot.model_validate_json(save_acceptance_snapshot(tmp_path, ledger_only=True).read_bytes())
    plan = _prepare(snapshot, acceptance_publication(snapshot))
    overview = _table(plan, TabName.GUIDE)
    metadata = {row["field"]: row["value"] for row in overview}
    assert plan.metadata.kind == "ledger"
    assert TabName.CALCULOS not in plan.tabs
    assert snapshot.amounts == ()
    assert snapshot.contributions == ()
    assert "calculation_revision_id" not in snapshot.selection.model_dump()
    assert "calculation_revision" not in metadata
    assert "modelo" not in metadata
    assert metadata["ledger_snapshot"] == "a" * 64
    assert len(_table(plan, TabName.DETALLE)) == 2
    assert all(row["sources"] == "No captured calculation attribution" for row in _table(plan, TabName.DETALLE))


def test_fresh_publication_plan_keeps_completed_receipt_and_saved_baseline_bytes(tmp_path: Path) -> None:
    """Local version contract only; remote document preservation awaits the live route."""
    source_path = save_acceptance_snapshot(tmp_path)
    source_bytes = source_path.read_bytes()
    snapshot = ReviewSnapshot.model_validate_json(source_bytes)
    first = acceptance_publication(snapshot)
    first_plan = _prepare(snapshot, first)
    completed = completed_acceptance_receipt(first)
    receipt_path = tmp_path / "completed-publication.json"
    receipt_path.write_text(completed.model_dump_json(), encoding="utf-8")
    completed_bytes = receipt_path.read_bytes()
    second = acceptance_publication(snapshot, publication_id=UUID(int=202), predecessor=first.publication_id)

    second_plan = _prepare(snapshot, second)
    assert first_plan.metadata.publication_id != second_plan.metadata.publication_id
    assert second.predecessor_publication_id == first.publication_id
    assert first_plan.metadata.snapshot_digest == second_plan.metadata.snapshot_digest
    assert _table(first_plan, TabName.CALCULOS) == _table(second_plan, TabName.CALCULOS)
    assert source_path.read_bytes() == source_bytes
    assert receipt_path.read_bytes() == completed_bytes
    assert PublicationReceipt.model_validate_json(completed_bytes) == completed


def test_saved_snapshot_tamper_is_detected_before_preparation(tmp_path: Path) -> None:
    source_path = save_acceptance_snapshot(tmp_path)
    changed = json.loads(source_path.read_text(encoding="utf-8"))
    changed["amounts"][0]["value"] = "25.20"
    with pytest.raises(ValidationError, match="digest"):
        ReviewSnapshot.model_validate_json(json.dumps(changed))
