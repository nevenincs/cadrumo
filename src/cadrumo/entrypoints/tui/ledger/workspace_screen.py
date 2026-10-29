"""Shared interaction shell and messages for Ledger destinations."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import ClassVar, cast, override

from textual import events, on
from textual.binding import Binding
from textual.message import Message
from textual.widget import Widget
from textual.widgets import DataTable, Static

from ....application.ledger.workspace import (
    LedgerWorkspaceArea,
)
from ....application.operator_actions.models import ActionReference
from ....core.errors.hierarchy import CadrumoError
from ....core.i18n.render import tr
from ....core.identity.transaction_ids import TransactionId
from ..components.account_chrome import AccountChromeScreen
from ..components.language import localized, reword_navigation
from ..components.theme import BASE_CSS, tokenised
from ..components.widgets import ContentDataTable
from ..components.workspace_host import replace_workspace_body
from ..operations.outcome import unknown_outcome_of
from .controller import (
    LedgerWorkspaceController,
    area_label,
    availability_label,
    item_count_label,
)
from .models import (
    LedgerRouteRefusalV1,
    LedgerRouteTargetV1,
)


class LedgerRouteRequested(Message):
    """Host-facing request to replace the active Ledger destination body."""

    def __init__(self, target: LedgerRouteTargetV1) -> None:
        """Store the internal semantic target for the owning host."""
        super().__init__()
        self.target = target


class LedgerEvidenceReviewRequested(Message):
    """Host-facing request carrying the canonical evidence-review query."""

    def __init__(self, *, attachment_id: str, action: ActionReference) -> None:
        """Store one visible attachment identity and its admitted action."""
        super().__init__()
        self.attachment_id = attachment_id
        self.action = action


class LedgerEntrySelected(Message):
    """Host-facing semantic selection of one safe Ledger entry reference."""

    def __init__(self, transaction_id: TransactionId) -> None:
        """Store only the application projection's safe transaction identity."""
        super().__init__()
        self.transaction_id = transaction_id


class LedgerBackRequested(Message):
    """Request that the owning host return to the parent destination."""


class LedgerInvoiceEntryRequested(Message):
    """Request the invoice entry form as the workspace body."""


class LedgerInvoiceCatalogueRequested(Message):
    """Request canonical invoice readback from the bucket-bound door."""


class LedgerTransactionDetailRequested(Message):
    """Request detail for one selected transaction identity."""

    def __init__(self, transaction_id: TransactionId) -> None:
        """Retain the selected transaction rather than a mutable table position."""
        super().__init__()
        self.transaction_id = transaction_id


class LedgerWorkspaceScreen(AccountChromeScreen):
    """Shared one-scroll shell and semantic navigation behavior."""

    BINDINGS: ClassVar = [Binding("escape", "back", "", show=False)]
    IS_WORKSPACE_OVERVIEW: ClassVar[bool] = False
    """Whether Back from this body leaves the workspace rather than returning to its overview."""
    WORKSPACE_AREA: ClassVar[LedgerWorkspaceArea | None] = None
    """The area this body is, whose tools it lists; ``None`` for a body that is not an area."""
    CSS = BASE_CSS + tokenised(
        """
        .ledger-page { width: 100%; height: 1fr; }
        .ledger-section { width: 100%; height: auto; margin-bottom: $cadrumo-stack; }
        .ledger-refusal { color: $warning; text-style: bold; height: auto; }
        .ledger-empty { color: $text-muted; height: auto; }
        """
    )

    def __init__(self, controller: LedgerWorkspaceController, *, id: str | None = None) -> None:
        """Retain the read-only controller and interaction observations."""
        super().__init__(id=id)
        self.controller = controller
        self.requested_target: LedgerRouteTargetV1 | None = None
        self.refusal: LedgerRouteRefusalV1 | None = None
        self.back_requested = False
        self.refreshing = False
        """Whether a re-read of the workspace is running off the event loop."""
        self._refreshes_started = 0
        """How many re-reads have started; each is numbered by this count when it starts."""
        self._refreshes_finished = 0
        """The number of the re-read that finished last."""
        self._refreshes_returned = 0
        """The number of the last re-read that returned the workspace, or ``0`` before any did."""
        self._after_refresh: Callable[[], object] | None = None
        """The operator's next step once the running re-read lands; a later request replaces it."""
        self._kept_after_refresh: list[Callable[[], object]] = []
        """Continuations every landing re-read runs, in the order they were asked for; none is replaced."""
        self.refresh_seconds: list[float] = []
        """How long each completed re-read took, newest last."""
        self.back_area: LedgerWorkspaceArea | None = None
        """The area Back returns to when this body was opened as one of its tools."""
        self._write_outcome_unknown = False
        self._unknown_after_refresh = 0
        """How many re-reads had started when the last unknown outcome arrived; only a later one can show it."""

    @property
    def write_outcome_unknown(self) -> bool:
        """Whether a write this body submitted ended without a known outcome, so the workspace must be re-read."""
        return self._write_outcome_unknown

    @write_outcome_unknown.setter
    def write_outcome_unknown(self, unknown: bool) -> None:
        self._write_outcome_unknown = unknown
        self._unknown_after_refresh = self._refreshes_started

    @property
    def unknown_outcome_unread(self) -> bool:
        """Whether a write's outcome is unknown and no workspace re-read started after it has returned.

        Such a re-read shows whether the write landed, so a later failed
        re-read, after a write that was saved, is worded as saved. A re-read
        that started before the outcome arrived shows nothing about it.
        """
        return self._write_outcome_unknown and self._refreshes_returned <= self._unknown_after_refresh

    @property
    def in_flight(self) -> bool:
        """Whether this body awaits a door call it must not abandon.

        Leaving a body unmounts it, and unmounting cancels its workers: a write
        cancelled after submission still settles, but nobody sees how, and a
        retry may repeat it. Back, area changes and tool choices are all
        refused while this holds, and so is every way the root has of removing
        the body: palette navigation, the account controls that
        replace the page or end the session, and quitting. A body that submits
        work overrides it with the state its own Back guard already keeps.
        """
        return False

    def refuse_leaving(self) -> bool:
        """Say that this body cannot be left yet and return ``True``, or return ``False`` when it can.

        The workspace asks this before it swaps its own body, and the root asks
        it, as the destination's leave guard, before it removes the destination.
        """
        if not self.in_flight:
            return False
        message = tr("tui.ledger.flow.in_flight_refusal")
        self._status_line().update(message)
        self.notify(message, severity="warning")
        return True

    def failed_write_status(self, error: BaseException, failed_key: str) -> str:
        """Word a write that did not succeed: unknown when its outcome is, otherwise ``failed_key``.

        A write whose outcome is unknown may have been saved, so it is never
        worded as refused, and the workspace is read again before it is offered
        once more. A session lost with the outcome unknown is worded the same;
        signing in composes the workspace again, so this body does not try to
        re-read it over the lost session.
        """
        unknown = unknown_outcome_of(error)
        if unknown is None:
            return tr(failed_key)
        if unknown is error:
            self.write_outcome_unknown = True
        return tr("tui.ledger.flow.outcome_unknown")

    def refresh_then(self, then: Callable[[], object], *, kept: bool = False) -> None:
        """Re-read the workspace off the event loop, then continue with ``then``.

        A capture reads every catalogue the workspace projects, which takes
        seconds on a real ledger; on the loop that froze every key. Only one
        read runs at a time: a request made while one is running joins it.

        ``then`` is the operator's next step by default. One step is held, and
        a later request replaces it, so the operator's last intent wins: Back
        pressed twice leaves once. A ``kept`` continuation is bookkeeping that
        must run whatever the operator asks for next. Each one is run, in the
        order it was asked for, when the read lands, and before the operator's
        step, which may leave this body.
        """
        if not self.controller.can_refresh():
            then()
            return
        if kept:
            self._kept_after_refresh.append(then)
        else:
            self._after_refresh = then
        if self.refreshing:
            return
        self.refreshing = True
        self._status_line().update(tr("tui.ledger.flow.refreshing"))
        self.run_worker(self._refresh(), group="ledger-refresh")

    def reread_then(self, then: Callable[[bool], object]) -> None:
        """Re-read the workspace with a read started from now on, then continue with whether it returned.

        Unlike :meth:`refresh_then`, a re-read already running does not count:
        it may have started before the change the workspace must now show, so
        once it lands another one is started. ``then`` is told ``False`` when
        the re-read failed or the workspace cannot be re-read at all. It is a
        kept continuation, so a step the operator asks for meanwhile, a saved
        write's own re-read included, cannot drop it.
        """
        if not self.controller.can_refresh():
            then(False)
            return
        after = self._refreshes_started

        def landed() -> None:
            if self._refreshes_finished <= after:
                self.refresh_then(landed, kept=True)
                return
            then(self._refreshes_returned > after)

        self.refresh_then(landed, kept=True)

    async def _refresh(self) -> None:
        started = asyncio.get_running_loop().time()
        self._refreshes_started += 1
        number = self._refreshes_started
        try:
            self.controller = await asyncio.to_thread(self.controller.refreshed)
        except CadrumoError:
            # After an unknown outcome not yet read back the change is not known to be saved, so the failure
            # must not say it was.
            failed = (
                "tui.ledger.flow.refresh_failed_unknown"
                if self.unknown_outcome_unread
                else "tui.ledger.flow.refresh_failed"
            )
            self._status_line().update(tr(failed))
        else:
            self._refreshes_returned = number
            self._status_line().update("")
        finally:
            self._refreshes_finished = number
            self.refreshing = False
            self.refresh_seconds.append(asyncio.get_running_loop().time() - started)
        kept, self._kept_after_refresh = self._kept_after_refresh, []
        then, self._after_refresh = self._after_refresh, None
        for each in kept:
            each()
        if then is not None:
            then()

    def _status_line(self) -> Static:
        """The body's flow status line, or its notice line when it has none."""
        found = self.query("#ledger-flow-status")
        return cast(Static, found.first()) if found else self.query_one("#ledger-refusal", Static)

    @override
    async def refresh_language(self) -> None:
        """Reword navigation without replacing forms or restarting their workers."""
        await super().refresh_language()
        reword_navigation(self, "#ledger-navigation", self.populate_navigation)
        # After the body's own repaint, which clears every table on the screen.
        self.call_after_refresh(reword_navigation, self, "#ledger-tools", self._populate_tools)

    @on(events.Mount)
    def _mount_tools(self) -> None:
        """List this area's tools beneath the area navigation, when it has any.

        Mounted rather than composed so every area body gets the list without
        each one composing it, beside whatever ``on_mount`` the body defines.
        """
        area = self.WORKSPACE_AREA
        pages = self.query("#ledger-page")
        if area is None or not self.controller.tools_for(area) or not pages or not self.is_attached:
            return
        # The page shell composes the navigation as the page's first child.
        page = pages.first(Widget)
        heading = localized(
            Static(tr("tui.ledger.tools.heading"), id="ledger-tools-heading", classes="cadrumo-heading", markup=False),
            "tui.ledger.tools.heading",
        )
        table = ContentDataTable[str](id="ledger-tools", cursor_type="row", show_header=False)
        page.mount(heading, table, after=cast("DataTable[str]", page.query_one("#ledger-navigation", DataTable)))
        self.call_after_refresh(self._populate_tools)

    def _populate_tools(self) -> None:
        found = self.query("#ledger-tools")
        if not found or self.WORKSPACE_AREA is None:
            return
        table = cast("DataTable[str]", found.first())
        if not table.columns:
            table.add_column("", key="tool")
        for tool in self.controller.tools_for(self.WORKSPACE_AREA):
            table.add_row(tr(tool.label_key), key=tool.key)

    @on(DataTable.RowSelected, "#ledger-tools")
    def _open_tool(self, event: DataTable.RowSelected) -> None:
        """Open the chosen tool in place of this body; Back returns to this area."""
        tool = self.controller.tool(str(event.row_key.value))
        if tool is None or self.refuse_leaving():
            return
        screen = tool.build(self.controller)
        screen.back_area = tool.area
        replace_workspace_body(self.app, screen)

    def populate_navigation(self) -> None:
        """Populate the complete seven-area catalogue in canonical order."""
        table = cast("DataTable[str]", self.query_one("#ledger-navigation", DataTable))
        table.add_column(tr("tui.ledger.column.destination"), key="destination")
        table.add_column(tr("tui.ledger.column.availability"), key="availability")
        table.add_column(tr("tui.ledger.column.items"), key="items")
        for area in LedgerWorkspaceArea:
            state = self.controller.state_for(area)
            refusal = self.controller.refusal_for(area)
            availability = state.availability if refusal is None else refusal.availability
            # An area waiting only for the operator to pick an entry is not
            # unavailable; saying so would send them away from the fix.
            availability_cell = (
                tr("tui.ledger.availability.choose_entry")
                if refusal is not None and refusal.reason_key == "tui.ledger.refusal.selection_required"
                else availability_label(availability)
            )
            table.add_row(area_label(area), availability_cell, item_count_label(state), key=area.value)

    def handle_navigation_selection(self, event: DataTable.RowSelected) -> bool:
        """Return whether ``event`` came from a table the shell answers itself: the areas or the tools.

        A body calls this first in its own row handler so it never reads an
        area or a tool as one of its own rows. The shell's handlers answer both
        whether or not the body has a row handler at all.
        """
        return cast("DataTable[str]", event.data_table).id in {"ledger-navigation", "ledger-tools"}

    @on(DataTable.RowSelected, "#ledger-navigation")
    def _choose_area(self, event: DataTable.RowSelected) -> None:
        """Open the chosen area, or say on screen why it cannot open.

        Answered here rather than by each body, so every body that shows the
        area navigation answers it, and refuses it alike while a write is out.
        """
        if self.refuse_leaving():
            return
        area = LedgerWorkspaceArea(str(event.row_key.value))
        refusal = self.controller.refusal_for(area)
        notice = self.query_one("#ledger-refusal", Static)
        if refusal is not None:
            self.refusal = refusal
            notice.update(tr(refusal.reason_key))
            return
        target = self.controller.route_target(area)
        self.requested_target = target
        notice.update("")
        self.post_message(LedgerRouteRequested(target))

    def action_back(self) -> None:
        """Ask the host to return, unless a write is in flight; never terminate the application."""
        if self.refuse_leaving():
            return
        self.back_requested = True
        self.post_message(LedgerBackRequested())

    def on_ledger_entry_selected(self, event: LedgerEntrySelected) -> None:
        """Re-address the workspace at the chosen entry and repaint navigation.

        Lives on the shared base rather than on the entries screen because the
        controller is shared: review and reconciliation restore their cursor
        from the same focus, so a selection made anywhere is the selection
        everywhere.

        The controller is REBOUND, not mutated — ``with_transaction_focus``
        returns a new one — so the next area move, which resolves its screen
        against ``self.controller``, carries the selection across the body swap
        without any extra push. The navigation table is rebuilt because
        classification's reachability has just changed, and a stale row would
        keep offering the old refusal.
        """
        self.controller = self.controller.with_transaction_focus(event.transaction_id)
        table = cast("DataTable[str]", self.query_one("#ledger-navigation", DataTable))
        table.clear(columns=True)
        self.populate_navigation()

    def on_ledger_route_requested(self, event: LedgerRouteRequested) -> None:
        """Resolve the requested area here and hand the finished body to the host.

        Textual delivers a screen's own posted message to it before bubbling,
        so the workspace answers its own navigation: it owns the controller and
        the route catalogue, and the host owns only the screen stack.
        """
        # Imported at call time because the route catalogue imports this module
        # for the shared shell; at module scope the two would form a cycle.
        from .routes import resolve_ledger_screen

        if self.refuse_leaving():
            return
        replace_workspace_body(self.app, resolve_ledger_screen(self.controller, event.target))

    def on_ledger_invoice_entry_requested(self, _: LedgerInvoiceEntryRequested) -> None:
        """Open the invoice entry form, or say why it cannot open in this session."""
        from .invoice_entry import LedgerInvoiceEntryScreen

        if self.refuse_leaving():
            return
        if not self.controller.can_add_invoices():
            self.query_one("#ledger-refusal", Static).update(tr("tui.ledger.refusal.submission_unavailable"))
            return
        replace_workspace_body(self.app, LedgerInvoiceEntryScreen(self.controller))

    def on_ledger_invoice_catalogue_requested(self, _: LedgerInvoiceCatalogueRequested) -> None:
        """Open canonical invoice readback through the injected record door."""
        from .record_views import LedgerInvoiceCatalogueScreen

        if self.refuse_leaving():
            return
        doors = self.controller.record_doors
        if doors is None:
            self.query_one("#ledger-refusal", Static).update(tr("tui.ledger.refusal.submission_unavailable"))
            return
        replace_workspace_body(self.app, LedgerInvoiceCatalogueScreen(self.controller, doors))

    def on_ledger_transaction_detail_requested(self, event: LedgerTransactionDetailRequested) -> None:
        """Open the selected transaction without resolving a row position."""
        from .transaction_views import LedgerTransactionDetailScreen

        if self.refuse_leaving():
            return
        doors = self.controller.record_doors
        if doors is None:
            self.query_one("#ledger-refusal", Static).update(tr("tui.ledger.refusal.submission_unavailable"))
            return
        replace_workspace_body(
            self.app,
            LedgerTransactionDetailScreen(self.controller, doors, str(event.transaction_id)),
        )

    def on_ledger_back_requested(self, _: LedgerBackRequested) -> None:
        """Return a tool to its area and an area to the overview; leave the workspace only from the overview."""
        if self.back_area is not None and self.controller.refusal_for(self.back_area) is None:
            self.post_message(LedgerRouteRequested(self.controller.route_target(self.back_area)))
            return
        # An overview that cannot open would bounce Back straight back here.
        if self.IS_WORKSPACE_OVERVIEW or self.controller.refusal_for(LedgerWorkspaceArea.OVERVIEW) is not None:
            self.dismiss(None)
            return
        self.post_message(LedgerRouteRequested(self.controller.route_target(LedgerWorkspaceArea.OVERVIEW)))

    def on_ledger_evidence_review_requested(self, _: LedgerEvidenceReviewRequested) -> None:
        """Say that an attachment-row selection leads nowhere yet, rather than appearing to work.

        Selecting an attachment row names a real query action, but no consumer
        executes it. Answering with the pending-area copy is the honest state:
        an unhandled message is indistinguishable from a dead keypress.
        """
        self.query_one("#ledger-refusal", Static).update(tr("tui.ledger.refusal.destination_pending"))
