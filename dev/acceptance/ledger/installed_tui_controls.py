"""Visible ledger TUI controls and semantic row navigation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dev.acceptance.income_tax.installed_tui_child import (
    query_public_selector,
    wait_for_public_selector,
)

from .installed_tui_contracts import _COUNTERPARTY_NIF, _INVOICE_BASE, _N26_HEADER, LedgerInstalledTuiError


async def _activate_button(pilot: Any, selector: str) -> None:
    """Use a focused public button, which also works in the compact test terminal."""
    from textual.widgets import Button

    button = query_public_selector(pilot, selector, Button)
    if button.disabled:
        raise LedgerInstalledTuiError(f"installed Ledger TUI exposed disabled action {selector}")
    button.focus()
    await pilot.press("enter")
    await pilot.pause()


async def _open_ledger_destination(pilot: Any) -> None:
    """Enter Ledger through the installed command palette and public destination label."""
    from textual.css.query import NoMatches
    from textual.widgets import Input, OptionList

    from cadrumo.core.i18n.render import tr

    label = tr("tui.search.destination.ledger")
    await pilot.press("ctrl+p")
    for _ in range(180):
        await pilot.pause()
        try:
            search = pilot.app.screen.query_one(Input)
            options = pilot.app.screen.query_one(OptionList)
        except NoMatches:
            continue
        search.value = "ledger"
        for index in range(options.option_count):
            hit = getattr(options.get_option_at_index(index), "hit", None)
            if getattr(hit, "text", None) == label:
                options.highlighted = index
                await pilot.press("enter")
                await wait_for_public_selector(pilot, "#ledger-navigation", polls=180)
                return
    raise LedgerInstalledTuiError("installed command palette did not offer Ledger")


async def _select_table_row_by_text(pilot: Any, *, selector: str, expected: str) -> None:
    """Open exactly one visible DataTable row identified by public rendered text."""
    from textual.widgets import DataTable

    await wait_for_public_selector(pilot, selector, polls=180)
    for _ in range(180):
        table = query_public_selector(pilot, selector, DataTable)
        matches = [
            row_key for row_key in table.rows if expected in " ".join(str(cell) for cell in table.get_row(row_key))
        ]
        if len(matches) == 1:
            table.focus()
            table.move_cursor(row=table.get_row_index(matches[0]))
            await pilot.press("enter")
            return
        if len(matches) > 1:
            raise LedgerInstalledTuiError(f"installed Ledger TUI exposed multiple public rows for {selector}")
        await pilot.pause()
    raise LedgerInstalledTuiError(f"installed Ledger TUI did not expose the required public row in {selector}")


async def _open_ledger_overview(pilot: Any) -> None:
    """Route to the public Ledger overview from the root palette."""
    from dev.acceptance.income_tax.installed_tui_child import select_public_data_table_row

    await _open_ledger_destination(pilot)
    await select_public_data_table_row(pilot=pilot, table_selector="#ledger-navigation", row_key="overview")
    await wait_for_public_selector(pilot, "#ledger-add-invoice", polls=180)


async def _capture_invoice_via_tui(
    pilot: Any,
    *,
    invoice_number: str,
    notes: str,
    year: int,
) -> None:
    """Persist one invoice through the normal review and confirmation controls."""
    from textual.widgets import Input, Select, Static

    await _open_ledger_overview(pilot)
    await _activate_button(pilot, "#ledger-add-invoice")
    await wait_for_public_selector(pilot, "#ledger-invoice-review", polls=180)
    query_public_selector(pilot, "#ledger-invoice-kind", Select).value = "issued"
    query_public_selector(pilot, "#ledger-invoice-class", Select).value = "ordinaria"
    fields = {
        "#ledger-invoice-counterparty-name": "Ledger acceptance customer",
        "#ledger-invoice-counterparty-nif": _COUNTERPARTY_NIF,
        "#ledger-invoice-country-code": "ES",
        "#ledger-invoice-invoice-number": invoice_number,
        "#ledger-invoice-invoice-date": f"{year}-03-15",
        "#ledger-invoice-taxable-base": format(_INVOICE_BASE, "f"),
        "#ledger-invoice-iva-rate": "21",
        "#ledger-invoice-iva-category": "domestic_general",
        "#ledger-invoice-currency": "EUR",
        "#ledger-invoice-notes": notes,
    }
    for selector, value in fields.items():
        query_public_selector(pilot, selector, Input).value = value
    await _activate_button(pilot, "#ledger-invoice-review")
    await wait_for_public_selector(pilot, "#ledger-invoice-confirm", polls=180)
    await _activate_button(pilot, "#ledger-invoice-confirm")
    await pilot.app.workers.wait_for_complete()
    await wait_for_public_selector(pilot, "#ledger-invoice-again", polls=180)
    refusal = str(query_public_selector(pilot, "#ledger-refusal", Static).render()).strip()
    if refusal:
        raise LedgerInstalledTuiError("installed invoice form visibly refused persistence")
    await _activate_button(pilot, "#ledger-invoice-again")
    await wait_for_public_selector(pilot, "#ledger-invoice-review", polls=180)
    await pilot.press("escape")
    await wait_for_public_selector(pilot, "#ledger-add-invoice", polls=180)


def _tui_only_transaction_descriptions(year: int) -> tuple[str, str]:
    """Return the distinct visible import label and its supported edited value."""
    return (f"ledger-tui-entry-{year}-initial", f"ledger-tui-entry-{year}-updated")


def _write_tui_only_statement(*, scratch: Path, year: int, description: str) -> Path:
    """Write one transient statement for the public Ledger import form.

    The file is an operator-selected input to the UI, never a persistence
    fixture.  A fresh receipt directory prevents an earlier acceptance run
    from being overwritten.
    """
    scratch.mkdir(parents=True, exist_ok=True)
    statement = scratch / "ledger-tui-only-entry.csv"
    if statement.exists():
        raise LedgerInstalledTuiError("TUI-only transaction input path must be fresh")
    statement.write_text(
        "\n".join(
            (
                _N26_HEADER,
                f"{year}-03-16,Ledger acceptance counterparty,{description},10.00,EUR,ledger-tui-entry-{year}",
                "",
            )
        ),
        encoding="utf-8",
        newline="\n",
    )
    return statement


async def _capture_transaction_via_tui(pilot: Any, *, statement: Path) -> None:
    """Persist one transaction through Ledger's visible import review and confirmation flow."""
    from textual.widgets import Button, Input, Select, Static

    from dev.acceptance.income_tax.installed_tui_child import select_public_data_table_row

    await _open_ledger_destination(pilot)
    await select_public_data_table_row(pilot=pilot, table_selector="#ledger-navigation", row_key="import")
    await wait_for_public_selector(pilot, "#ledger-import-path", polls=180)
    query_public_selector(pilot, "#ledger-import-kind", Select).value = "bank_statement"
    query_public_selector(pilot, "#ledger-import-provider", Select).value = "csv"
    query_public_selector(pilot, "#ledger-import-path", Input).value = str(statement)
    await _activate_button(pilot, "#ledger-import-preview-button")
    await pilot.app.workers.wait_for_complete()
    await wait_for_public_selector(pilot, "#ledger-import-confirm", polls=180)
    refusal = str(query_public_selector(pilot, "#ledger-refusal", Static).render()).strip()
    confirm = query_public_selector(pilot, "#ledger-import-confirm", Button)
    if refusal or confirm.disabled:
        raise LedgerInstalledTuiError("installed Ledger transaction import did not reach public confirmation")
    await _activate_button(pilot, "#ledger-import-confirm")
    await pilot.app.workers.wait_for_complete()
    if str(query_public_selector(pilot, "#ledger-refusal", Static).render()).strip():
        raise LedgerInstalledTuiError("installed Ledger transaction import visibly refused persistence")
    await _activate_button(pilot, "#ledger-import-again")
    await pilot.app.workers.wait_for_complete()
    await wait_for_public_selector(pilot, "#ledger-import-preview-button", polls=180)


async def _open_invoice_detail(pilot: Any, *, invoice_number: str) -> None:
    """Reach a catalogue invoice using its visible number and stable row selection."""
    await _open_ledger_overview(pilot)
    await _activate_button(pilot, "#ledger-open-invoices")
    await _select_table_row_by_text(pilot, selector="#ledger-invoice-catalogue", expected=invoice_number)
    await wait_for_public_selector(pilot, "#ledger-invoice-notes", polls=180)


async def _inspect_invoice(pilot: Any, *, invoice_number: str, expected_notes: str) -> None:
    """Read the canonical detail and require the expected visible metadata."""
    from textual.widgets import Input, Static

    await _open_invoice_detail(pilot, invoice_number=invoice_number)
    details = str(query_public_selector(pilot, "#ledger-record-detail", Static).render())
    if invoice_number not in details:
        raise LedgerInstalledTuiError("installed invoice detail did not retain its visible identity")
    if query_public_selector(pilot, "#ledger-invoice-notes", Input).value != expected_notes:
        raise LedgerInstalledTuiError("installed invoice detail did not retain its visible notes")


async def _update_invoice_notes(
    pilot: Any,
    *,
    invoice_number: str,
    initial_notes: str,
    updated_notes: str,
) -> None:
    """Perform the supported notes-only update and refresh from committed state."""
    from textual.widgets import Button, Input, Static

    await _inspect_invoice(pilot, invoice_number=invoice_number, expected_notes=initial_notes)
    notes = query_public_selector(pilot, "#ledger-invoice-notes", Input)
    notes.value = updated_notes
    await _activate_button(pilot, "#ledger-invoice-edit-review")
    save = query_public_selector(pilot, "#ledger-invoice-edit-save", Button)
    if save.disabled:
        raise LedgerInstalledTuiError("installed invoice detail did not enable its reviewed save action")
    await _activate_button(pilot, "#ledger-invoice-edit-save")
    await pilot.app.workers.wait_for_complete()
    await wait_for_public_selector(pilot, "#ledger-invoice-notes", polls=180)
    if query_public_selector(pilot, "#ledger-invoice-notes", Input).value != updated_notes:
        raise LedgerInstalledTuiError("installed invoice detail did not refresh the committed notes")
    if str(query_public_selector(pilot, "#ledger-refusal", Static).render()).strip():
        raise LedgerInstalledTuiError("installed invoice detail visibly refused the supported notes update")


async def _open_transaction_detail(pilot: Any, *, description: str) -> None:
    """Reach a transaction through visible Entries selection and its public action button."""
    from dev.acceptance.income_tax.installed_tui_child import select_public_data_table_row

    await _open_ledger_destination(pilot)
    await select_public_data_table_row(pilot=pilot, table_selector="#ledger-navigation", row_key="entries")
    await _select_table_row_by_text(pilot, selector="#ledger-entries", expected=description)
    await _activate_button(pilot, "#ledger-open-transaction")
    await wait_for_public_selector(pilot, "#ledger-transaction-description", polls=180)


async def _inspect_transaction(pilot: Any, *, description: str) -> None:
    """Require a public detail readback before testing continuation or refusal stability."""
    from textual.widgets import Input

    await _open_transaction_detail(pilot, description=description)
    if query_public_selector(pilot, "#ledger-transaction-description", Input).value != description:
        raise LedgerInstalledTuiError("installed transaction detail did not retain its visible description")


async def _edit_unlinked_transaction(
    pilot: Any,
    *,
    description: str,
    updated_description: str,
) -> None:
    """Edit one unlinked transaction only through review, save, and refreshed detail."""
    from textual.widgets import Button, Input, Static

    await _inspect_transaction(pilot, description=description)
    query_public_selector(pilot, "#ledger-transaction-description", Input).value = updated_description
    await _activate_button(pilot, "#ledger-transaction-edit-review")
    save = query_public_selector(pilot, "#ledger-transaction-edit-save", Button)
    if save.disabled:
        raise LedgerInstalledTuiError("installed transaction detail did not enable its reviewed save action")
    await _activate_button(pilot, "#ledger-transaction-edit-save")
    await pilot.app.workers.wait_for_complete()
    if query_public_selector(pilot, "#ledger-transaction-description", Input).value != updated_description:
        raise LedgerInstalledTuiError("installed transaction detail did not refresh the committed description")
    if str(query_public_selector(pilot, "#ledger-refusal", Static).render()).strip():
        raise LedgerInstalledTuiError("installed transaction detail visibly refused the supported edit")


async def _refuse_linked_transaction_edit(pilot: Any, *, description: str) -> None:
    """Exercise the public review/save refusal before rereading committed detail."""
    from textual.widgets import Button, Input, Static

    await _inspect_transaction(pilot, description=description)
    query_public_selector(pilot, "#ledger-transaction-description", Input).value = f"{description}-attempted-edit"
    await _activate_button(pilot, "#ledger-transaction-edit-review")
    save = query_public_selector(pilot, "#ledger-transaction-edit-save", Button)
    if save.disabled:
        raise LedgerInstalledTuiError("installed linked transaction detail did not enable its reviewed save action")
    await _activate_button(pilot, "#ledger-transaction-edit-save")
    await pilot.app.workers.wait_for_complete()
    refusal = str(query_public_selector(pilot, "#ledger-refusal", Static).render()).strip().casefold()
    if not all(marker in refusal for marker in ("linked transaction identity", "invoice link")):
        raise LedgerInstalledTuiError("installed linked transaction detail did not show the linked-identity refusal")
    await _inspect_transaction(pilot, description=description)
