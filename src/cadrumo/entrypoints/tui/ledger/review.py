"""Ledger review queue over application-owned safe review identities, with exclusion."""

from __future__ import annotations

from typing import ClassVar, cast, override

from pydantic import ValidationError
from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import Button, DataTable, Static

from ....application.ledger.workspace import LedgerWorkspaceArea
from ....core.errors.hierarchy import CadrumoError
from ....core.identity.transaction_ids import TransactionId
from ..components.widgets import ContentDataTable
from .controller import (
    LedgerReviewRequested,
    LedgerRouteRequested,
    LedgerWorkspaceController,
    LedgerWorkspaceScreen,
    ledger_copy,
    review_status_label,
)
from .workspace_presentation import door_refusal_text, ledger_workspace_page, restore_transaction_focus


class LedgerReviewScreen(LedgerWorkspaceScreen):
    """Filter disclosure and status rows with semantic transaction selection.

    ``x`` asks to exclude the highlighted entry. Nothing is written until the
    operator confirms the sentence naming that entry; Escape or Cancel while
    asking withdraws the request.
    """

    BINDINGS: ClassVar = [
        *LedgerWorkspaceScreen.BINDINGS,
        Binding("x", "exclude", "", show=False),
    ]

    def __init__(self, controller: LedgerWorkspaceController) -> None:
        """Retain the controller and initialize semantic selection state."""
        super().__init__(controller, id="ledger-review-screen")
        self.requested_transaction_id: TransactionId | None = None
        self.pending_exclusion: TransactionId | None = None
        self.excluding = False

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
            yield Static(id="ledger-empty", classes="ledger-empty", markup=False)
            if self.controller.can_exclude():
                yield Static(ledger_copy("tui.ledger.review.exclude_hint"), classes="ledger-empty", markup=False)
                yield Static("", id="ledger-exclusion-question", markup=False)
                yield Button(ledger_copy("tui.ledger.review.exclude_confirm"), id="ledger-exclusion-confirm")
                yield Button(ledger_copy("tui.ledger.review.exclude_cancel"), id="ledger-exclusion-cancel")
                yield Static("", id="ledger-flow-status", markup=False)
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
                self.controller.entry_label(row.transaction_id),
                review_status_label(row.review_status),
                ledger_copy("tui.ledger.review.open"),
                key=row.transaction_id,
            )
        if not table.row_count:
            self.query_one("#ledger-empty", Static).update(ledger_copy("tui.ledger.review.empty"))
        self._show_exclusion_controls(open_=False)
        navigation = cast("DataTable[str]", self.query_one("#ledger-navigation", DataTable))
        restore_transaction_focus(
            navigation=navigation,
            table=table,
            transaction_id=self.controller.restored_transaction_id(),
        )

    def _show_exclusion_controls(self, *, open_: bool) -> None:
        if not self.controller.can_exclude():
            return
        for selector in ("#ledger-exclusion-question", "#ledger-exclusion-confirm", "#ledger-exclusion-cancel"):
            self.query_one(selector).display = open_

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

    def action_exclude(self) -> None:
        """Ask to exclude the highlighted entry, naming it, before anything is written."""
        notice = self.query_one("#ledger-refusal", Static)
        if not self.controller.can_exclude():
            notice.update(ledger_copy("tui.ledger.refusal.submission_unavailable"))
            return
        if self.excluding or self.refreshing:
            return
        table = cast("DataTable[str]", self.query_one("#ledger-review", DataTable))
        if not table.row_count:
            notice.update(ledger_copy("tui.ledger.review.empty"))
            return
        key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
        if key is None:
            return
        self.pending_exclusion = key
        notice.update("")
        self.query_one("#ledger-exclusion-question", Static).update(
            ledger_copy("tui.ledger.review.exclude_question", entry=self.controller.entry_label(key))
        )
        self._show_exclusion_controls(open_=True)
        self.query_one("#ledger-exclusion-confirm", Button).focus()

    @override
    def action_back(self) -> None:
        """Withdraw an open exclusion question before leaving the area."""
        if self.excluding:
            self.query_one("#ledger-flow-status", Static).update(ledger_copy("tui.ledger.flow.in_flight_refusal"))
            return
        if self.pending_exclusion is not None:
            self._withdraw()
            return
        super().action_back()

    def _withdraw(self) -> None:
        self.pending_exclusion = None
        self._show_exclusion_controls(open_=False)
        self.query_one("#ledger-review", DataTable).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Confirm or withdraw the open exclusion question."""
        if self.excluding:
            return
        if event.button.id == "ledger-exclusion-cancel":
            self._withdraw()
        elif event.button.id == "ledger-exclusion-confirm" and self.pending_exclusion is not None:
            self.excluding = True
            event.button.disabled = True
            self.query_one("#ledger-flow-status", Static).update(ledger_copy("tui.ledger.review.excluding"))
            self.run_worker(self._exclude(self.pending_exclusion), exclusive=True)

    async def _exclude(self, transaction_id: TransactionId) -> None:
        status = self.query_one("#ledger-flow-status", Static)
        label = self.controller.entry_label(transaction_id)
        try:
            await self.controller.submit_exclusion(transaction_id)
        except (CadrumoError, ValidationError) as error:
            self.excluding = False
            self.query_one("#ledger-exclusion-confirm", Button).disabled = False
            status.update(ledger_copy("tui.ledger.review.exclude_failed"))
            self.query_one("#ledger-refusal", Static).update(door_refusal_text(error))
            return
        self.excluding = False
        self.pending_exclusion = None
        self._show_exclusion_controls(open_=False)
        status.update(ledger_copy("tui.ledger.review.excluded", entry=label))
        self.refresh_then(self._reopen)

    def _reopen(self) -> None:
        """Show the re-read review list, staying on the area the operator is working in."""
        self.post_message(LedgerRouteRequested(self.controller.route_target(LedgerWorkspaceArea.REVIEW)))


__all__ = ["LedgerReviewScreen"]
