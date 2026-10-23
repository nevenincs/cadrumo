"""Ledger review queue read through the registered review operation, with exclusion.

The queue is the operation's own answer for the admitted profile, read off the
event loop each time the area opens. The operation has no paging, so the whole
answer is held and the table renders one page of it at a time.
"""

from __future__ import annotations

from typing import ClassVar, Final, Protocol, cast, override
from uuid import UUID

from pydantic import ValidationError
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Button, DataTable, Static

from ....application.ledger.review_operation import (
    LedgerReviewProjection,
    LedgerReviewRequest,
    LedgerReviewRowProjection,
)
from ....application.ledger.workspace import LedgerWorkspaceArea
from ....core.errors.hierarchy import CadrumoError
from ....core.i18n.render import tr
from ....core.identity.transaction_ids import TransactionId
from ..account import AccountSessionExpiredError
from ..components.language import localized, repaint_tables
from ..components.theme import tokenised
from ..components.widgets import ContentDataTable
from ..operations.outcome import OperationOutcomeUnknownError
from .controller import (
    LedgerRouteRequested,
    LedgerTransactionDetailRequested,
    LedgerWorkspaceController,
    LedgerWorkspaceScreen,
    review_status_label,
)
from .workspace_presentation import door_refusal_text, ledger_workspace_page

REVIEW_PAGE_SIZE: Final = 200
"""The most review rows the table renders at once."""


class LedgerReviewDoorV1(Protocol):
    """Injected door to ``ledger.review`` for one admitted profile."""

    @property
    def profile_id(self) -> UUID:
        """The profile every request through this door must name."""
        ...

    async def __call__(self, request: LedgerReviewRequest) -> LedgerReviewProjection:
        """Read the review queue the request selects, correlated with its terminal receipt."""
        ...


class LedgerReviewScreen(LedgerWorkspaceScreen):
    """The review queue, one page at a time, with semantic transaction selection.

    Choosing a row opens that entry's detail. ``x`` asks to exclude the
    highlighted entry; nothing is written until the operator confirms the
    sentence naming it, and Escape or Cancel while asking withdraws the request.
    """

    WORKSPACE_AREA: ClassVar[LedgerWorkspaceArea | None] = LedgerWorkspaceArea.REVIEW

    BINDINGS: ClassVar = [
        *LedgerWorkspaceScreen.BINDINGS,
        Binding("x", "exclude", "", show=False),
    ]
    CSS = LedgerWorkspaceScreen.CSS + tokenised(
        """
        .ledger-review-paging { height: auto; }
        .ledger-review-paging Button { margin-right: $cadrumo-space-1; }
        """
    )

    def __init__(self, controller: LedgerWorkspaceController) -> None:
        """Retain the controller and initialize semantic selection state."""
        super().__init__(controller, id="ledger-review-screen")
        self.rows: tuple[LedgerReviewRowProjection, ...] = ()
        """The whole queue the last read returned; only one page of it is rendered."""
        self.page_offset = 0
        self.loaded = False
        self.requested_transaction_id: TransactionId | None = None
        self.pending_exclusion: TransactionId | None = None
        self.excluding = False

    @property
    @override
    def in_flight(self) -> bool:
        """An exclusion is out through its door."""
        return self.excluding

    @override
    def compose(self) -> ComposeResult:
        yield localized(Static(tr("tui.ledger.review.title"), classes="cadrumo-banner"), "tui.ledger.review.title")
        with ledger_workspace_page() as navigation:
            yield navigation
            yield localized(
                Static(
                    tr("tui.ledger.review.filter_all"),
                    markup=False,
                ),
                "tui.ledger.review.filter_all",
            )
            # The entry names itself with its date and description, and it is
            # the one cell here the operator cannot reconstruct from the
            # others. The spare width belongs to it, not to the last column.
            review_table = ContentDataTable[str](id="ledger-review", cursor_type="row", zebra_stripes=True)
            review_table.fill_column = 0
            yield review_table
            with Horizontal(id="ledger-review-paging", classes="ledger-review-paging"):
                yield localized(
                    Button(tr("tui.ledger.review.page.previous"), id="ledger-review-previous", disabled=True),
                    "tui.ledger.review.page.previous",
                )
                yield localized(
                    Button(tr("tui.ledger.review.page.next"), id="ledger-review-next", disabled=True),
                    "tui.ledger.review.page.next",
                )
            yield Static("", id="ledger-review-position", markup=False)
            yield Static(id="ledger-empty", classes="ledger-empty", markup=False)
            if self.controller.can_exclude():
                yield localized(
                    Static(tr("tui.ledger.review.exclude_hint"), classes="ledger-empty", markup=False),
                    "tui.ledger.review.exclude_hint",
                )
                yield Static("", id="ledger-exclusion-question", markup=False)
                yield localized(
                    Button(tr("tui.ledger.review.exclude_confirm"), id="ledger-exclusion-confirm"),
                    "tui.ledger.review.exclude_confirm",
                )
                yield localized(
                    Button(tr("tui.ledger.review.exclude_cancel"), id="ledger-exclusion-cancel"),
                    "tui.ledger.review.exclude_cancel",
                )
            yield Static("", id="ledger-flow-status", markup=False)
            yield Static(id="ledger-refusal", classes="ledger-refusal", markup=False)

    def on_mount(self) -> None:
        """Show the shell, then read the queue off the event loop."""
        self._populate_view()
        self._show_exclusion_controls(open_=False)
        self.query_one("#ledger-navigation", DataTable).focus()
        door = self.controller.review_door
        if door is None:
            self.query_one("#ledger-refusal", Static).update(tr("tui.ledger.refusal.submission_unavailable"))
            return
        self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.review.loading"))
        self.run_worker(self._load(door), group="ledger-review-read", exclusive=True)

    async def _load(self, door: LedgerReviewDoorV1, *, then_status: str = "") -> None:
        """Read the queue; once it lands, the status line says ``then_status``."""
        status = self.query_one("#ledger-flow-status", Static)
        refusal = self.query_one("#ledger-refusal", Static)
        try:
            result = await door(LedgerReviewRequest(profile_id=door.profile_id))
        except AccountSessionExpiredError as error:
            self._forget_rows()
            status.update(tr("tui.ledger.review.failed"))
            refusal.update(door_refusal_text(error))
            return
        except (CadrumoError, ValidationError) as error:
            status.update(tr("tui.ledger.review.failed"))
            refusal.update(door_refusal_text(error))
            return
        self.rows = result.rows
        self.loaded = True
        self._open_page_holding(self.controller.restored_transaction_id())
        status.update(then_status)
        self._populate_view()
        self._restore_focus()

    def _open_page_holding(self, transaction_id: TransactionId | None) -> None:
        """Open the page that holds ``transaction_id``, or the first page when it is not listed."""
        index = next((index for index, row in enumerate(self.rows) if row.id == transaction_id), 0)
        self.page_offset = index - index % REVIEW_PAGE_SIZE

    def _page(self) -> tuple[LedgerReviewRowProjection, ...]:
        return self.rows[self.page_offset : self.page_offset + REVIEW_PAGE_SIZE]

    @staticmethod
    def _row_label(row: LedgerReviewRowProjection) -> str:
        """Name an entry the way the operator recorded it: its date and description."""
        return tr("tui.ledger.entry_label", date=row.date, description=row.description)

    def _label(self, transaction_id: TransactionId) -> str:
        """Name a listed entry by its identity, or by its short identifier when the queue no longer lists it."""
        row = next((row for row in self.rows if row.id == transaction_id), None)
        return str(transaction_id)[:12] if row is None else self._row_label(row)

    def _populate_view(self) -> None:
        """Populate the navigation and the current page of review rows."""
        navigation = cast("DataTable[str]", self.query_one("#ledger-navigation", DataTable))
        if not navigation.columns:
            self.populate_navigation()
        table = cast("DataTable[str]", self.query_one("#ledger-review", DataTable))
        table.clear(columns=True)
        table.add_column(tr("tui.ledger.column.entry"), key="entry")
        table.add_column(tr("tui.ledger.column.amount"), key="amount")
        table.add_column(tr("tui.ledger.column.review_status"), key="review_status")
        table.add_column(tr("tui.ledger.column.next"), key="next")
        for row in self._page():
            table.add_row(
                self._row_label(row),
                row.amount,
                review_status_label(row.status.value),
                tr("tui.ledger.review.open"),
                key=row.id,
            )
        empty = tr("tui.ledger.review.empty") if self.loaded and not self.rows else ""
        self.query_one("#ledger-empty", Static).update(empty)
        self._paint_paging()

    def _paint_paging(self) -> None:
        self.query_one("#ledger-review-previous", Button).disabled = self.page_offset == 0
        self.query_one("#ledger-review-next", Button).disabled = self.page_offset + REVIEW_PAGE_SIZE >= len(self.rows)
        page = self._page()
        self.query_one("#ledger-review-position", Static).update(
            tr(
                "tui.ledger.review.page.position",
                first=self.page_offset + 1,
                last=self.page_offset + len(page),
                total=len(self.rows),
            )
            if page
            else ""
        )

    def _restore_focus(self) -> None:
        """Focus the chosen entry by identity when this page lists it, otherwise the navigation."""
        navigation = self.query_one("#ledger-navigation", DataTable)
        table = cast("DataTable[str]", self.query_one("#ledger-review", DataTable))
        chosen = self.controller.restored_transaction_id()
        index = next((index for index, row in enumerate(table.ordered_rows) if row.key.value == chosen), None)
        if chosen is None or index is None:
            navigation.focus()
            return
        table.move_cursor(row=index)
        table.focus()

    def _forget_rows(self) -> None:
        """Discard the queue once the admitted session is lost, or once it may no longer be current."""
        self.rows = ()
        self.loaded = False
        self.page_offset = 0
        self.pending_exclusion = None
        self._populate_view()
        self._show_exclusion_controls(open_=False)

    @override
    async def refresh_language(self) -> None:
        """Reword review rows while retaining an open exclusion confirmation."""
        await super().refresh_language()
        controls = {
            widget: widget.display
            for widget in self.query("#ledger-exclusion-question, #ledger-exclusion-confirm, #ledger-exclusion-cancel")
        }
        repaint_tables(self, self._populate_view)
        for widget, visible in controls.items():
            widget.display = visible

    def _show_exclusion_controls(self, *, open_: bool) -> None:
        if not self.controller.can_exclude():
            return
        for selector in ("#ledger-exclusion-question", "#ledger-exclusion-confirm", "#ledger-exclusion-cancel"):
            self.query_one(selector).display = open_

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Open the chosen entry's detail by its transaction identity."""
        if self.handle_navigation_selection(event):
            return
        if event.data_table.id != "ledger-review" or event.row_key.value is None:
            return
        transaction_id = event.row_key.value
        self.requested_transaction_id = transaction_id
        self.post_message(LedgerTransactionDetailRequested(transaction_id))

    def action_exclude(self) -> None:
        """Ask to exclude the highlighted entry, naming it, before anything is written."""
        notice = self.query_one("#ledger-refusal", Static)
        if not self.controller.can_exclude():
            notice.update(tr("tui.ledger.refusal.submission_unavailable"))
            return
        if self.excluding or self.refreshing or not self.loaded:
            return
        table = cast("DataTable[str]", self.query_one("#ledger-review", DataTable))
        if not table.row_count:
            notice.update(tr("tui.ledger.review.empty"))
            return
        key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
        if key is None:
            return
        self.pending_exclusion = key
        notice.update("")
        self.query_one("#ledger-exclusion-question", Static).update(
            tr("tui.ledger.review.exclude_question", entry=self._label(self.pending_exclusion))
        )
        self._show_exclusion_controls(open_=True)
        self.query_one("#ledger-exclusion-confirm", Button).focus()

    @override
    def action_back(self) -> None:
        """Withdraw an open exclusion question before leaving the area."""
        if self.refuse_leaving():
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
        """Page the queue, or confirm or withdraw the open exclusion question."""
        match event.button.id:
            case "ledger-review-previous":
                self.page_offset = max(0, self.page_offset - REVIEW_PAGE_SIZE)
                self._populate_view()
            case "ledger-review-next" if self.page_offset + REVIEW_PAGE_SIZE < len(self.rows):
                self.page_offset += REVIEW_PAGE_SIZE
                self._populate_view()
            case "ledger-exclusion-cancel" if not self.excluding:
                self._withdraw()
            case "ledger-exclusion-confirm" if not self.excluding and self.pending_exclusion is not None:
                self.excluding = True
                event.button.disabled = True
                self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.review.excluding"))
                listed = frozenset(row.id for row in self.rows)
                self.run_worker(self._exclude(self.pending_exclusion, listed), exclusive=True)
            case _:
                return

    async def _exclude(self, transaction_id: TransactionId, listed: frozenset[TransactionId]) -> None:
        status = self.query_one("#ledger-flow-status", Static)
        label = self._label(transaction_id)
        try:
            await self.controller.submit_exclusion(transaction_id, listed=listed)
        except (CadrumoError, ValidationError) as error:
            self.excluding = False
            self.query_one("#ledger-exclusion-confirm", Button).disabled = False
            outcome = self.failed_write_status(error, "tui.ledger.review.exclude_failed")
            status.update(outcome)
            self.query_one("#ledger-refusal", Static).update(door_refusal_text(error))
            if isinstance(error, OperationOutcomeUnknownError):
                # The entry may already be excluded: nothing is offered again until the queue is read again.
                self._forget_rows()
                self.refresh_then(lambda: self._reread_queue(outcome))
            return
        self.excluding = False
        self.pending_exclusion = None
        self._show_exclusion_controls(open_=False)
        status.update(tr("tui.ledger.review.excluded", entry=label))
        self.refresh_then(self._reopen)

    def _reread_queue(self, outcome: str) -> None:
        """Read the queue again after an exclusion whose outcome is unknown, keeping that outcome in view."""
        door = self.controller.review_door
        if door is None:
            return
        self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.review.loading"))
        self.run_worker(self._load(door, then_status=outcome), group="ledger-review-read", exclusive=True)

    def _reopen(self) -> None:
        """Show the re-read review queue, staying on the area the operator is working in."""
        self.post_message(LedgerRouteRequested(self.controller.route_target(LedgerWorkspaceArea.REVIEW)))


__all__ = ["REVIEW_PAGE_SIZE", "LedgerReviewDoorV1", "LedgerReviewScreen"]
