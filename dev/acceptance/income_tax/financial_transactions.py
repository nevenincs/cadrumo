"""Visible installed transaction import, row discovery and classification stages."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from .financial_contracts import _N26_HEADER
from .financial_navigation import _activate_button, _open_destination
from .installed_tui_child import (
    InstalledTuiChildError,
    query_public_selector,
    select_public_data_table_row,
    wait_for_public_selector,
)
from .scenario import ExpenseInvoice, IncomeTaxScenario, IssuedInvoice

if TYPE_CHECKING:
    pass


def _transaction_csv(*, scenario: IncomeTaxScenario, directory: Path) -> Path:
    """Build one transient N26-compatible statement from the independent scenario."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "income-m130-transactions.csv"
    rows = [_N26_HEADER]
    for item in (*scenario.income, *scenario.expenses):
        amount = item.net_receipt if isinstance(item, IssuedInvoice) else -item.bank_payment
        rows.append(
            ",".join(
                (
                    item.transaction_date.isoformat(),
                    item.transaction_id,
                    item.invoice_id,
                    format(amount, "f"),
                    "EUR",
                    item.transaction_id,
                )
            )
        )
    path.write_text("\n".join(rows) + "\n", encoding="utf-8", newline="\n")
    return path


async def _import_transactions(pilot: Any, *, csv_path: Path) -> None:
    """Use the visible bank-statement import preview and confirmation flow."""
    from textual.widgets import Input, Select

    await _open_destination(pilot, query="ledger", expected_selector="#ledger-navigation")
    await select_public_data_table_row(pilot=pilot, table_selector="#ledger-navigation", row_key="import")
    await wait_for_public_selector(pilot, "#ledger-import-path")
    query_public_selector(pilot, "#ledger-import-kind", Select).value = "bank_statement"
    query_public_selector(pilot, "#ledger-import-provider", Select).value = "csv"
    query_public_selector(pilot, "#ledger-import-path", Input).value = str(csv_path)
    await _activate_button(pilot, "#ledger-import-preview-button")
    await pilot.app.workers.wait_for_complete()
    await wait_for_public_selector(pilot, "#ledger-import-confirm")
    from textual.widgets import Button, Static

    refusal = str(query_public_selector(pilot, "#ledger-refusal", Static).render()).strip()
    confirm = query_public_selector(pilot, "#ledger-import-confirm", Button)
    if refusal or confirm.disabled:
        raise InstalledTuiChildError("installed transaction import preview did not reach confirmation")
    await _activate_button(pilot, "#ledger-import-confirm")
    await pilot.app.workers.wait_for_complete()
    refusal = str(query_public_selector(pilot, "#ledger-refusal", Static).render()).strip()
    if refusal:
        raise InstalledTuiChildError("installed transaction import reported a visible persistence refusal")
    await _activate_button(pilot, "#ledger-import-again")
    await pilot.app.workers.wait_for_complete()
    await wait_for_public_selector(pilot, "#ledger-import-preview-button")


async def _transaction_row_ids(
    pilot: Any,
    *,
    scenario: IncomeTaxScenario,
) -> dict[str, str]:
    """Resolve imported rows by the scenario's unique visible transaction dates."""
    from textual.widgets import DataTable

    await _open_destination(pilot, query="ledger", expected_selector="#ledger-navigation")
    await select_public_data_table_row(pilot=pilot, table_selector="#ledger-navigation", row_key="entries")
    await wait_for_public_selector(pilot, "#ledger-entries")
    table = query_public_selector(pilot, "#ledger-entries", DataTable)
    resolved: dict[str, str] = {}
    for item in (*scenario.income, *scenario.expenses):
        matches = [
            row_key
            for row_key in table.rows
            if item.transaction_date.isoformat() in " ".join(str(cell) for cell in table.get_row(row_key))
        ]
        if len(matches) != 1:
            date_hits = sum(
                item.transaction_date.isoformat() in " ".join(str(cell) for cell in table.get_row(row_key))
                for row_key in table.rows
            )
            raise InstalledTuiChildError(
                "installed Entries did not expose one unambiguous scenario row "
                f"(date_matches={date_hits}, combined={len(matches)})"
            )
        resolved[item.transaction_id] = str(matches[0].value)
    return resolved


async def _classify_transaction(
    pilot: Any,
    *,
    transaction_id: str,
    item: IssuedInvoice | ExpenseInvoice,
) -> None:
    """Classify one visible row and capture the tax facts needed by Renta."""
    from textual.widgets import Input, Static

    await _open_destination(pilot, query="ledger", expected_selector="#ledger-navigation")
    await select_public_data_table_row(pilot=pilot, table_selector="#ledger-navigation", row_key="entries")
    await wait_for_public_selector(pilot, "#ledger-entries")
    from textual.widgets import DataTable

    table = query_public_selector(pilot, "#ledger-entries", DataTable)
    row_key = next((candidate for candidate in table.rows if str(candidate.value) == transaction_id), None)
    if row_key is None:
        raise InstalledTuiChildError("installed entries lost a transaction before classification")
    table.focus()
    table.move_cursor(row=table.get_row_index(row_key))
    await pilot.press("enter")
    await pilot.pause()
    await select_public_data_table_row(
        pilot=pilot,
        table_selector="#ledger-navigation",
        row_key="classification",
    )
    await wait_for_public_selector(pilot, "#ledger-classifications")
    values = {
        "#ledger-classification-taxable-base": format(item.taxable_base, "f"),
        "#ledger-classification-iva-rate": format(item.iva_rate, "f"),
        "#ledger-classification-iva-amount": format(item.iva, "f"),
        "#ledger-classification-iva-category": "domestic_general",
        "#ledger-classification-irpf-category": ("actividad_economica" if isinstance(item, IssuedInvoice) else ""),
    }
    for selector, value in values.items():
        query_public_selector(pilot, selector, Input).value = value
    await select_public_data_table_row(
        pilot=pilot,
        table_selector="#ledger-classifications",
        row_key="BUSINESS",
    )
    await _activate_button(pilot, "#ledger-classification-confirm")
    await pilot.app.workers.wait_for_complete()
    status = str(query_public_selector(pilot, "#ledger-flow-status", Static).render()).strip()
    if not status:
        raise InstalledTuiChildError("installed classification did not expose a terminal status")
    await pilot.press("escape")
    await pilot.app.workers.wait_for_complete()
