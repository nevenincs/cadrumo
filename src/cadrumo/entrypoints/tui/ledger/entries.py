"""Redacted Ledger entry index over safe application references."""

from __future__ import annotations

from typing import cast, override

from textual.app import ComposeResult
from textual.widgets import DataTable, Static

from ....core.identity import TransactionId
from ..components.widgets import ContentDataTable, ContentScroll
from .controller import (
    LedgerEntrySelected,
    LedgerWorkspaceController,
    LedgerWorkspaceScreen,
    ledger_copy,
    review_status_label,
)


class LedgerEntriesScreen(LedgerWorkspaceScreen):
    """Show safe identifiers and status only; never reconstruct financial payloads."""

    def __init__(self, controller: LedgerWorkspaceController) -> None:
        """Retain the injected read-only workspace controller."""
        super().__init__(controller, id="ledger-entries-screen")
        self.selected_transaction_id: TransactionId | None = None

    @override
    def compose(self) -> ComposeResult:
        yield Static(ledger_copy("tui.ledger.entries.title", default="Ledger entries"), classes="cadrumo-banner")
        with ContentScroll(id="ledger-page", classes="cadrumo-scroll ledger-page"):
            yield ContentDataTable[str](id="ledger-navigation", cursor_type="row", zebra_stripes=True)
            yield Static(
                ledger_copy(
                    "tui.ledger.entries.redacted",
                    default="Safe entry index; financial details stay protected.",
                ),
                markup=False,
            )
            yield ContentDataTable[str](id="ledger-entries", cursor_type="row", zebra_stripes=True)
            yield Static(id="ledger-refusal", classes="ledger-refusal", markup=False)

    def on_mount(self) -> None:
        """Populate the safe entry index using semantic row identities."""
        self.populate_navigation()
        table = cast("DataTable[str]", self.query_one("#ledger-entries", DataTable))
        table.add_column(ledger_copy("tui.ledger.column.entry", default="Entry"), key="entry")
        table.add_column(ledger_copy("tui.ledger.column.review_status", default="Review status"), key="review_status")
        for row in self.controller.entry_rows():
            table.add_row(str(row.transaction_id)[:12], review_status_label(row.review_status), key=row.transaction_id)
        if not table.row_count:
            self.query_one("#ledger-refusal", Static).update(
                ledger_copy("tui.ledger.entries.empty", default="No entries are present in this snapshot.")
            )
        restored = self.controller.restored_transaction_id()
        if restored is None:
            self.query_one("#ledger-navigation", DataTable).focus()
            return
        row_index = next(
            (index for index, row in enumerate(table.ordered_rows) if row.key.value == restored),
            None,
        )
        if row_index is not None:
            table.move_cursor(row=row_index)
            table.focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Route navigation or retain a safe semantic entry selection."""
        if self.handle_navigation_selection(event):
            return
        event_table = cast("DataTable[str]", event.data_table)
        transaction_id = event.row_key.value
        if event_table.id != "ledger-entries" or transaction_id is None:
            return
        self.selected_transaction_id = transaction_id
        self.post_message(LedgerEntrySelected(transaction_id))


__all__ = ["LedgerEntriesScreen"]
