"""Redacted Ledger entry index over safe application references."""

from __future__ import annotations

from typing import cast, override

from textual.app import ComposeResult
from textual.widgets import DataTable, Static

from ....core.identity import TransactionId
from ..components.widgets import ContentDataTable
from .controller import (
    LedgerEntrySelected,
    LedgerWorkspaceController,
    LedgerWorkspaceScreen,
    ledger_copy,
    review_status_label,
)
from .workspace_presentation import ledger_workspace_page, restore_transaction_focus


class LedgerEntriesScreen(LedgerWorkspaceScreen):
    """Show safe identifiers and status only; never reconstruct financial payloads."""

    def __init__(self, controller: LedgerWorkspaceController) -> None:
        """Retain the injected read-only workspace controller."""
        super().__init__(controller, id="ledger-entries-screen")
        self.selected_transaction_id: TransactionId | None = None

    @override
    def compose(self) -> ComposeResult:
        yield Static(ledger_copy("tui.ledger.entries.title"), classes="cadrumo-banner")
        with ledger_workspace_page() as navigation:
            yield navigation
            yield Static(
                ledger_copy("tui.ledger.entries.redacted"),
                markup=False,
            )
            yield ContentDataTable[str](id="ledger-entries", cursor_type="row", zebra_stripes=True)
            yield Static(id="ledger-refusal", classes="ledger-refusal", markup=False)

    def on_mount(self) -> None:
        """Populate the safe entry index using semantic row identities."""
        self.populate_navigation()
        table = cast("DataTable[str]", self.query_one("#ledger-entries", DataTable))
        table.add_column(ledger_copy("tui.ledger.column.entry"), key="entry")
        table.add_column(ledger_copy("tui.ledger.column.review_status"), key="review_status")
        for row in self.controller.entry_rows():
            table.add_row(str(row.transaction_id)[:12], review_status_label(row.review_status), key=row.transaction_id)
        if not table.row_count:
            self.query_one("#ledger-refusal", Static).update(
                ledger_copy("tui.ledger.entries.empty")
            )
        navigation = cast("DataTable[str]", self.query_one("#ledger-navigation", DataTable))
        restore_transaction_focus(
            navigation=navigation,
            table=table,
            transaction_id=self.controller.restored_transaction_id(),
        )

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
