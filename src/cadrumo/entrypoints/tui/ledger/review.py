"""Ledger review queue over application-owned safe review identities."""

from __future__ import annotations

from typing import cast, override

from textual.app import ComposeResult
from textual.widgets import DataTable, Static

from ....core.identity import TransactionId
from ..components.widgets import ContentDataTable, ContentScroll
from .controller import (
    LedgerReviewRequested,
    LedgerWorkspaceController,
    LedgerWorkspaceScreen,
    ledger_copy,
    review_status_label,
)


class LedgerReviewScreen(LedgerWorkspaceScreen):
    """Filter disclosure and status rows with semantic transaction selection."""

    def __init__(self, controller: LedgerWorkspaceController) -> None:
        """Retain the controller and initialize semantic selection state."""
        super().__init__(controller, id="ledger-review-screen")
        self.requested_transaction_id: TransactionId | None = None

    @override
    def compose(self) -> ComposeResult:
        yield Static(ledger_copy("tui.ledger.review.title", default="Ledger review"), classes="cadrumo-banner")
        with ContentScroll(id="ledger-page", classes="cadrumo-scroll ledger-page"):
            yield ContentDataTable[str](id="ledger-navigation", cursor_type="row", zebra_stripes=True)
            yield Static(
                ledger_copy("tui.ledger.review.filter_all", default="Filter: all pending review rows"),
                markup=False,
            )
            yield ContentDataTable[str](id="ledger-review", cursor_type="row", zebra_stripes=True)
            yield Static(id="ledger-refusal", classes="ledger-refusal", markup=False)

    def on_mount(self) -> None:
        """Populate the filter disclosure and canonical review rows."""
        self.populate_navigation()
        table = cast("DataTable[str]", self.query_one("#ledger-review", DataTable))
        table.add_column(ledger_copy("tui.ledger.column.entry", default="Entry"), key="entry")
        table.add_column(ledger_copy("tui.ledger.column.review_status", default="Review status"), key="review_status")
        table.add_column(ledger_copy("tui.ledger.column.next", default="Next"), key="next")
        for row in self.controller.review_rows():
            table.add_row(
                str(row.transaction_id)[:12],
                review_status_label(row.review_status),
                ledger_copy("tui.ledger.review.open", default="Open review"),
                key=row.transaction_id,
            )
        if not table.row_count:
            self.query_one("#ledger-refusal", Static).update(
                ledger_copy("tui.ledger.review.empty", default="No entries currently need review.")
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
