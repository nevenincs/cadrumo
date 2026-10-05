"""Public TUI partial handoff and independent quarterly export observations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .financial_lifecycle import _m130_expected, _parse_m130_artifact
from .financial_navigation import _open_destination, _work_ids_by_period, open_work
from .financial_transactions import _transaction_row_ids
from .installed_tui_child import (
    InstalledTuiChildError,
    query_public_selector,
    select_public_data_table_row,
    wait_for_public_selector,
)
from .scenario import build_scenario
from .tui_lifecycle_contract import installed_lifecycle_contract
from .tui_navigation import acknowledge_export_result, open_workbench_export
from .tui_operation_controls import activate_tui_operation


async def _assert_tui_partial_readback(*, pilot: Any, scenario: Any, year: int) -> dict[str, str]:
    """Require visible entries, resolved links, and a Q1 local filing history row."""
    from textual.widgets import DataTable

    rows = await _transaction_row_ids(pilot, scenario=scenario)
    works = await _work_ids_by_period(pilot, year=year)
    if len(rows) != 8 or set(works) != {"1T", "2T", "3T", "4T"}:
        raise InstalledTuiChildError("installed TUI did not publicly reproduce the four-unit partial workflow")

    await _open_destination(pilot, query="ledger", expected_selector="#ledger-navigation")
    await select_public_data_table_row(
        pilot=pilot,
        table_selector="#ledger-navigation",
        row_key="reconciliation",
    )
    await wait_for_public_selector(pilot, "#ledger-suggestions")
    suggestions = query_public_selector(pilot, "#ledger-suggestions", DataTable)
    inconsistencies = query_public_selector(pilot, "#ledger-inconsistencies", DataTable)
    if suggestions.row_count or inconsistencies.row_count:
        raise InstalledTuiChildError("installed TUI reconciliation publicly reports unresolved invoice links")

    await _open_destination(pilot, query="declarations", expected_selector="#declarations-list")
    await select_public_data_table_row(
        pilot=pilot,
        table_selector="#declarations-navigation",
        row_key="declarations.filing_history",
    )
    await wait_for_public_selector(pilot, "#declarations-filings")
    filings = query_public_selector(pilot, "#declarations-filings", DataTable)
    q1_filing = any(
        str(row_key.value).startswith("filing:")
        and f"Modelo 130 · {year} · 1T" in " ".join(str(cell) for cell in filings.get_row(row_key))
        for row_key in filings.rows
    )
    if not q1_filing:
        raise InstalledTuiChildError("installed TUI filing history did not publicly prove the Q1 local filing")
    return works


async def _export_visible_m130(
    *, pilot: Any, export_path: Path, work_unit_id: str, year: int, period: str
) -> dict[str, str]:
    """Export an already-filed quarterly work through its workbench's export dialog."""
    await open_work(pilot, work_unit_id=work_unit_id)
    await open_workbench_export(pilot, output_path=str(export_path))
    contract = installed_lifecycle_contract(
        profile_selection_id="#manager-status",
        ledger_capture_id="#ledger-import-confirm",
        invoice_link_id="#ledger-reconciliation-confirm",
        work_create_id="#declarations-calendar-agenda",
    )
    terminal = await activate_tui_operation(pilot, binding=contract.export)
    if terminal.outcome.value != "proven":
        raise InstalledTuiChildError("installed TUI did not export the public Q1 work artifact")
    await acknowledge_export_result(pilot)
    return _parse_m130_artifact(
        path=export_path,
        year=year,
        period=period,
        expected=_m130_expected(next(item for item in build_scenario(year).quarter_oracle if item.period == period)),
    )
