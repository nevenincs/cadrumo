"""Visible installed IVA statement import and transaction classification."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from dev.acceptance.income_tax.installed_tui_child import (
    InstalledTuiChildError,
    public_surface_diagnostic,
    query_public_selector,
    select_public_data_table_row,
    wait_for_public_selector,
)

from .iva_tui_controls import _activate, _open_ledger, _visible_text
from .iva_tui_scenario import _SyntheticIvaRow


async def _import_statement(pilot: Any, *, statement: Path) -> None:
    """Persist the transient statement through visible import preview/confirm controls."""
    from textual.widgets import Button, Input, Select, Static

    await _open_ledger(pilot)
    await select_public_data_table_row(pilot=pilot, table_selector="#ledger-navigation", row_key="import")
    await wait_for_public_selector(pilot, "#ledger-import-path", polls=180)
    cast(Select[str], query_public_selector(pilot, "#ledger-import-kind", Select)).value = "bank_statement"
    cast(Select[str], query_public_selector(pilot, "#ledger-import-provider", Select)).value = "csv"
    query_public_selector(pilot, "#ledger-import-path", Input).value = str(statement)
    await _activate(pilot, "#ledger-import-preview-button")
    await pilot.app.workers.wait_for_complete()
    await wait_for_public_selector(pilot, "#ledger-import-confirm", polls=180)
    refusal = _visible_text(query_public_selector(pilot, "#ledger-refusal", Static))
    confirm = query_public_selector(pilot, "#ledger-import-confirm", Button)
    if refusal or confirm.disabled:
        raise InstalledTuiChildError("installed Ledger import preview did not reach its visible confirmation state")
    await _activate(pilot, "#ledger-import-confirm")
    await pilot.app.workers.wait_for_complete()
    refusal = _visible_text(query_public_selector(pilot, "#ledger-refusal", Static))
    if refusal:
        raise InstalledTuiChildError("installed Ledger import exposed a persistence refusal")
    await _activate(pilot, "#ledger-import-again")
    await pilot.app.workers.wait_for_complete()
    await wait_for_public_selector(pilot, "#ledger-import-preview-button", polls=180)


async def _resolve_imported_transaction_ids(
    pilot: Any, synthetic_rows: tuple[_SyntheticIvaRow, ...]
) -> tuple[str, str]:
    """Resolve both opaque row identities from their unique visible synthetic labels."""
    from textual.widgets import DataTable

    await _open_ledger(pilot)
    await select_public_data_table_row(pilot=pilot, table_selector="#ledger-navigation", row_key="entries")
    await wait_for_public_selector(pilot, "#ledger-entries", polls=180)
    table = cast(DataTable[str], query_public_selector(pilot, "#ledger-entries", DataTable))
    if table.row_count == 0:
        raise InstalledTuiChildError(
            "installed Ledger Entries projection was empty after confirmed import",
            diagnostic=public_surface_diagnostic(pilot),
        )
    if table.row_count != len(synthetic_rows):
        raise InstalledTuiChildError(
            "installed Ledger Entries projection count differs from the confirmed import",
            diagnostic=public_surface_diagnostic(pilot),
        )
    resolved: list[str] = []
    for item in synthetic_rows:
        matches = [
            row_key
            for row_key in table.rows
            if item.entry_date in " ".join(str(cell) for cell in table.get_row(row_key))
        ]
        if len(matches) != 1:
            raise InstalledTuiChildError(
                "installed Ledger Entries did not expose one unambiguous imported scenario date",
                diagnostic=public_surface_diagnostic(pilot),
            )
        resolved.append(str(matches[0].value))
    if len(resolved) != 2:
        raise InstalledTuiChildError("installed Ledger Entries did not retain two imported row identities")
    return resolved[0], resolved[1]


async def _classify_transaction(
    pilot: Any,
    *,
    transaction_id: str,
    scenario_row: _SyntheticIvaRow,
) -> None:
    """Submit one combined IVA classification through the public TUI form."""
    from textual.widgets import DataTable, Input, Static

    from cadrumo.core.i18n.render import tr

    await _open_ledger(pilot)
    await select_public_data_table_row(pilot=pilot, table_selector="#ledger-navigation", row_key="entries")
    await wait_for_public_selector(pilot, "#ledger-entries", polls=180)
    table = cast(DataTable[str], query_public_selector(pilot, "#ledger-entries", DataTable))
    row_key = next((candidate for candidate in table.rows if str(candidate.value) == transaction_id), None)
    if row_key is None:
        raise InstalledTuiChildError("installed Ledger Entries lost an imported transaction before classification")
    table.focus()
    table.move_cursor(row=table.get_row_index(row_key))
    await pilot.press("enter")
    await pilot.pause()
    await select_public_data_table_row(
        pilot=pilot,
        table_selector="#ledger-navigation",
        row_key="classification",
    )
    await wait_for_public_selector(pilot, "#ledger-classifications", polls=180)
    values = {
        "#ledger-classification-taxable-base": scenario_row.taxable_base,
        "#ledger-classification-iva-rate": "0.21",
        "#ledger-classification-iva-amount": scenario_row.iva_amount,
        "#ledger-classification-iva-category": "domestic_general",
        "#ledger-classification-deduction-fact-kind": scenario_row.deduction_fact_kind,
    }
    for selector, value in values.items():
        query_public_selector(pilot, selector, Input).value = value
    await select_public_data_table_row(
        pilot=pilot,
        table_selector="#ledger-classifications",
        row_key="BUSINESS",
    )
    await _activate(pilot, "#ledger-classification-confirm")
    await pilot.app.workers.wait_for_complete()
    refusal = _visible_text(query_public_selector(pilot, "#ledger-refusal", Static))
    terminal = _visible_text(query_public_selector(pilot, "#ledger-flow-status", Static))
    if refusal or terminal != tr("tui.ledger.classification.success"):
        raise InstalledTuiChildError(
            "installed combined IVA classification did not reach its succeeded public terminal"
        )
    await pilot.press("escape")
    await pilot.app.workers.wait_for_complete()
