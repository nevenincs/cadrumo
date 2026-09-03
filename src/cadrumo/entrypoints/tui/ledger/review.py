"""Ledger review queue over application-owned safe review identities."""

from __future__ import annotations

from typing import cast, override

from textual.app import ComposeResult
from textual.widgets import DataTable, Static

from ....core.identity import TransactionId
from ..components.widgets import ContentDataTable
from .controller import (
    LedgerReviewRequested,
    LedgerWorkspaceController,
    LedgerWorkspaceScreen,
    ledger_copy,
    review_status_label,
)
from .workspace_presentation import ledger_workspace_page, restore_transaction_focus


class LedgerReviewScreen(LedgerWorkspaceScreen):
    """Filter disclosure and status rows with semantic transaction selection."""

    def __init__(self, controller: LedgerWorkspaceController) -> None:
        """Retain the controller and initialize semantic selection state."""
        super().__init__(controller, id="ledger-review-screen")
        self.requested_transaction_id: TransactionId | None = None

    @override
    def compose(self) -> ComposeResult:
        yield Static(ledger_copy("tui.ledger.review.title"), classes="cadrumo-banner")
        with ledger_workspace_page() as navigation:
            yield navigation
            yield Static(
                ledger_copy("tui.ledger.review.filter_all"),
                markup=False,
            )
            yield ContentDataTable[str](id="ledger-review", cursor_type="row", zebra_stripes=True)
            yield Static(id="ledger-refusal", classes="ledger-refusal", markup=False)

    def on_mount(self) -> None:
        """Populate the filter disclosure and canonical review rows."""
        self.populate_navigation()
        table = cast("DataTable[str]", self.query_one("#ledger-review", DataTable))
        table.add_column(ledger_copy("tui.ledger.column.entry"), key="entry")
        table.add_column(ledger_copy("tui.ledger.column.review_status"), key="review_status")
        table.add_column(ledger_copy("tui.ledger.column.next"), key="next")
        for row in self.controller.review_rows():
            table.add_row(
                str(row.transaction_id)[:12],
                review_status_label(row.review_status),
                ledger_copy("tui.ledger.review.open"),
                key=row.transaction_id,
            )
        if not table.row_count:
            self.query_one("#ledger-refusal", Static).update(ledger_copy("tui.ledger.review.empty"))
        navigation = cast("DataTable[str]", self.query_one("#ledger-navigation", DataTable))
        restore_transaction_focus(
            navigation=navigation,
            table=table,
            transaction_id=self.controller.restored_transaction_id(),
        )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Route navigation rows or emit the canonical review query request."""
        if self.handle_navigation_selection(event):
            return
        event_table = cast("DataTable[str]", event.data_table)
        if event_table.id != "ledger-review":
            return
        transaction_id = event.row_key.value
        if transaction_id is None:
            return
        row = next(item for item in self.controller.review_rows() if item.transaction_id == transaction_id)
        self.requested_transaction_id = transaction_id
        self.post_message(LedgerReviewRequested(transaction_id=transaction_id, action=row.action))


__all__ = ["LedgerReviewScreen"]
