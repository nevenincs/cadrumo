"""Visible installed invoice capture and reciprocal transaction reconciliation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .financial_contracts import _SYNTHETIC_COUNTERPARTY_NIF
from .financial_navigation import _activate_button, _open_destination
from .installed_tui_child import (
    InstalledTuiChildError,
    query_public_selector,
    select_public_data_table_row,
    wait_for_public_selector,
)
from .scenario import ExpenseInvoice, IssuedInvoice

if TYPE_CHECKING:
    pass


async def _open_invoice_form(pilot: Any) -> None:
    """Open the normal invoice entry form from Ledger overview."""
    await _open_destination(pilot, query="ledger", expected_selector="#ledger-navigation")
    await select_public_data_table_row(pilot=pilot, table_selector="#ledger-navigation", row_key="overview")
    await wait_for_public_selector(pilot, "#ledger-add-invoice")
    await _activate_button(pilot, "#ledger-add-invoice")
    await wait_for_public_selector(pilot, "#ledger-invoice-review")


async def _capture_invoice(pilot: Any, *, item: IssuedInvoice | ExpenseInvoice) -> None:
    """Persist one invoice through its visible review/confirmation form."""
    from textual.widgets import Input, Select

    await _open_invoice_form(pilot)
    issued = isinstance(item, IssuedInvoice)
    query_public_selector(pilot, "#ledger-invoice-kind", Select).value = "issued" if issued else "received"
    query_public_selector(pilot, "#ledger-invoice-class", Select).value = "ordinaria"
    values = {
        "#ledger-invoice-counterparty-name": item.transaction_id,
        "#ledger-invoice-counterparty-nif": _SYNTHETIC_COUNTERPARTY_NIF,
        "#ledger-invoice-invoice-number": item.invoice_id,
        "#ledger-invoice-invoice-date": item.invoice_date.isoformat(),
        "#ledger-invoice-taxable-base": format(item.taxable_base, "f"),
        "#ledger-invoice-iva-rate": format(item.iva_rate * 100, "f"),
        "#ledger-invoice-iva-category": "domestic_general",
        "#ledger-invoice-currency": "EUR",
        "#ledger-invoice-retention-rate": format(item.withholding_rate, "f") if issued else "",
        "#ledger-invoice-retention-amount": format(item.withholding, "f") if issued else "",
    }
    for selector, value in values.items():
        query_public_selector(pilot, selector, Input).value = value
    await _activate_button(pilot, "#ledger-invoice-review")
    await wait_for_public_selector(pilot, "#ledger-invoice-confirm")
    await _activate_button(pilot, "#ledger-invoice-confirm")
    await pilot.app.workers.wait_for_complete()
    await wait_for_public_selector(pilot, "#ledger-invoice-again")
    from textual.widgets import Static

    refusal = str(query_public_selector(pilot, "#ledger-refusal", Static).render()).strip()
    if refusal:
        raise InstalledTuiChildError("installed invoice form reported a visible persistence refusal")
    await _activate_button(pilot, "#ledger-invoice-again")
    await pilot.app.workers.wait_for_complete()
    await wait_for_public_selector(pilot, "#ledger-invoice-review")


async def _reconcile_invoice(pilot: Any, *, transaction_id: str, invoice_id: str) -> None:
    """Create one persisted link from the visible row naming the synthetic counterparty."""
    from textual.widgets import DataTable, Static

    from cadrumo.core.i18n.render import tr

    await _open_destination(pilot, query="ledger", expected_selector="#ledger-navigation")
    await select_public_data_table_row(pilot=pilot, table_selector="#ledger-navigation", row_key="reconciliation")
    await wait_for_public_selector(pilot, "#ledger-suggestions")
    table = query_public_selector(pilot, "#ledger-suggestions", DataTable)
    matching = [
        row_key for row_key in table.rows if transaction_id in " ".join(str(cell) for cell in table.get_row(row_key))
    ]
    if len(matching) != 1:
        raise InstalledTuiChildError(
            "installed reconciliation did not expose exactly one visible match "
            f"for {invoice_id} (visible rows: {table.row_count}, matches: {len(matching)})"
        )
    table.focus()
    table.move_cursor(row=table.get_row_index(matching[0]))
    await pilot.press("enter")
    await wait_for_public_selector(pilot, "#ledger-reconciliation-confirm")
    await _activate_button(pilot, "#ledger-reconciliation-confirm")
    await pilot.app.workers.wait_for_complete()
    status = str(query_public_selector(pilot, "#ledger-flow-status", Static).render()).strip()
    if status != tr("tui.ledger.reconciliation.success"):
        raise InstalledTuiChildError("installed reconciliation did not confirm a persisted link")
