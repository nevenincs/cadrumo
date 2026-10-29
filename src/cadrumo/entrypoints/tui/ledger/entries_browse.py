"""Browse entries: the paged entry list and the actions an operator takes on one entry.

The list reads one page at a time through ``ledger.list`` with the request's
own filters, group, sort and paging, so the screen never holds more than one
page. Every row is keyed by its transaction identity, and the selection is
restored by that identity after a page is re-read. Archive, stash, restore,
exclude, remove and merge are reviewed in a confirmation dialog that names
what will change, and only the reviewed request is submitted.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import ClassVar, cast, override

from pydantic import ValidationError
from textual.app import ComposeResult
from textual.widgets import Button, Checkbox, DataTable, Input, Select, Static

from ....application.ledger.lifecycle_contracts import (
    LedgerLifecycleMutationRequest,
    LedgerLifecycleOperationResult,
)
from ....application.ledger.list_operation import LedgerListProjection, LedgerListRequest
from ....application.ledger.merge_operation import LedgerMergeRequest
from ....application.ledger.remove_operation import LedgerRemoveRequest
from ....application.ledger.transaction_projection import LedgerTransactionReviewProjection
from ....core.errors.hierarchy import CadrumoError
from ....core.i18n.render import tr
from ..account import AccountSessionExpiredError
from ..components.dialogs import ConfirmScreen
from ..components.language import repaint_tables
from ..components.theme import tokenised
from ..components.widgets import ContentDataTable
from ..components.workspace_host import replace_workspace_body
from ..operations.outcome import OperationOutcomeUnknownError
from .controller import LedgerWorkspaceController
from .entries_browse_form import form_request, show_request
from .entries_browse_layout import (
    classification_options,
    compose_browse,
    direction_options,
    issue_options,
    order_options,
    row_cells,
    set_browse_controls,
    show_browse_window,
    sort_options,
    status_options,
    visible_columns,
)
from .entries_browse_model import (
    BROWSE_PAGE_SIZE,
    LedgerBrowseStateV1,
    lifecycle_action,
    lifecycle_consequence,
    lifecycle_done,
    removal_preview_text,
)
from .entries_common import (
    entry_label,
    joined,
    lifecycle_label,
    short_id,
)
from .entries_doors import LedgerEntriesDoorsV1, LedgerLifecycleDoorV1
from .workspace_presentation import door_refusal_text
from .workspace_screen import LedgerTransactionDetailRequested, LedgerWorkspaceScreen


class LedgerEntriesBrowseScreen(LedgerWorkspaceScreen):
    """List one page of entries with the operation's filters, and act on the chosen entry."""

    CSS: ClassVar[str] = LedgerWorkspaceScreen.CSS + tokenised(
        """
        .entries-browse-row { height: auto; width: 100%; }
        .entries-browse-row > * { width: 1fr; min-width: 0; }
        #entries-browse-selected { height: auto; text-style: bold; }
        """
    )

    def __init__(
        self,
        controller: LedgerWorkspaceController,
        doors: LedgerEntriesDoorsV1,
        *,
        state: LedgerBrowseStateV1 | None = None,
    ) -> None:
        """Keep the injected doors and the state to open at."""
        super().__init__(controller, id="ledger-entries-browse-screen")
        self.doors = doors
        initial = state or LedgerBrowseStateV1()
        self.request = initial.request or LedgerListRequest(profile_id=doors.profile_id, limit=BROWSE_PAGE_SIZE)
        if self.request.profile_id != doors.profile_id or self.request.limit != BROWSE_PAGE_SIZE:
            raise ValueError("Browse entries reads one bounded page for its own profile")
        self.page: LedgerListProjection | None = None
        self.selected_id: str | None = initial.selected_id
        self.marked: dict[str, str] = dict(initial.marked)
        self.busy = False

    @property
    @override
    def in_flight(self) -> bool:
        """A page read or an entry write is out through a door."""
        return self.busy

    @override
    def compose(self) -> ComposeResult:
        yield from compose_browse(mark_label=self._mark_label, merge_label=self._merge_label)

    def on_mount(self) -> None:
        """Show the filters the request already holds, then read its page off the loop."""
        self._show_request_in_form()
        self._repaint()
        self._read(self.request)

    @override
    async def refresh_language(self) -> None:
        """Reword choices, checkboxes and the page in place, keeping the selection."""
        await super().refresh_language()
        for selector, options in (
            ("#entries-browse-status", status_options()),
            ("#entries-browse-direction", direction_options()),
            ("#entries-browse-classification", classification_options()),
            ("#entries-browse-issue", issue_options()),
            ("#entries-browse-sort", sort_options()),
            ("#entries-browse-order", order_options()),
        ):
            select = cast("Select[str]", self.query_one(selector, Select))
            value = select.value
            select.set_options(options)
            select.value = value
        self.query_one("#entries-browse-by-group", Checkbox).label = tr("tui.ledger.entry_tools.browse.by_group")
        self.query_one("#entries-browse-hide-rejected", Checkbox).label = tr(
            "tui.ledger.entry_tools.browse.hide_rejected"
        )
        self._show_marks()
        repaint_tables(self, self._repaint)

    # -- request ---------------------------------------------------------

    def _select(self, selector: str) -> Select[str]:
        return self.query_one(selector, Select)

    def _text(self, selector: str) -> str:
        return self.query_one(selector, Input).value.strip()

    def _form_request(self) -> LedgerListRequest:
        """Build the list request from the typed filters; paging starts again at the first page."""
        return form_request(
            profile_id=self.doors.profile_id,
            select=self._select,
            text=self._text,
            checkbox=lambda selector: self.query_one(selector, Checkbox).value,
        )

    def _show_request_in_form(self) -> None:
        """Fill the filter controls from the request this screen opened with."""
        show_request(
            self.request,
            select=self._select,
            input_field=lambda selector: self.query_one(selector, Input),
            checkbox=lambda selector: self.query_one(selector, Checkbox),
        )

    # -- reading ---------------------------------------------------------

    def _read(self, request: LedgerListRequest) -> None:
        self._set_busy(True)
        self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.entry_tools.browse.reading"))
        self.run_worker(self._load(request), exclusive=True, group="entries-browse")

    async def _load(self, request: LedgerListRequest, *, then: str = "") -> None:
        """Read exactly one page and show it; ``then`` is a settled write's outcome to keep on screen."""
        status = self.query_one("#ledger-flow-status", Static)
        refusal = self.query_one("#ledger-refusal", Static)
        try:
            page = await self.doors.list_entries(request)
        except AccountSessionExpiredError as error:
            self._clear_private_view()
            refusal.update(door_refusal_text(error))
            status.update(then)
            return
        except CadrumoError as error:
            refusal.update(door_refusal_text(error))
            status.update(then)
            return
        finally:
            self._set_busy(False)
        self.request = request
        self.page = page
        self._paint()
        status.update(then or ("" if page.rows else tr("tui.ledger.entry_tools.browse.empty")))

    def _repaint(self) -> None:
        """Redraw every table after a language change cleared them."""
        self.populate_navigation()
        self._paint()

    def _paint(self) -> None:
        """Draw the page and its window, and restore the selection by identity."""
        table = cast("ContentDataTable[str]", self.query_one("#entries-browse", ContentDataTable))
        rows = self._draw_page_rows(table)
        # Before the first page lands there is nothing to judge the selection against.
        if (
            self.page is not None
            and self.selected_id is not None
            and all(row.transaction.transaction_id != self.selected_id for row in rows)
        ):
            self.selected_id = None
        index = next(
            (position for position, row in enumerate(rows) if row.transaction.transaction_id == self.selected_id),
            None,
        )
        if index is not None:
            table.move_cursor(row=index, animate=False)
        self._show_window()
        self._show_selection()
        self._show_marks()

    def _draw_page_rows(self, table: ContentDataTable[str]) -> tuple[LedgerTransactionReviewProjection, ...]:
        columns = visible_columns(self.app.size.width)
        names = [name for name, _, _ in columns]
        table.fill_column = names.index("description") if "description" in names else -1
        table.clear(columns=True)
        for name, key, size in columns:
            header = tr(key)
            table.add_column(header, key=name, width=max(size, len(header)))
        rows = () if self.page is None else self.page.rows
        for row in rows:
            cells = row_cells(row, self.marked)
            table.add_row(*(cells[name] for name in names), key=row.transaction.transaction_id)
        table.absorb_surplus_width()
        return rows

    def _show_window(self) -> None:
        window = self.query_one("#entries-browse-window", Static)
        page = self.page
        previous = self.query_one("#entries-browse-previous", Button)
        following = self.query_one("#entries-browse-next", Button)
        show_browse_window(window, previous, following, page, self.busy)

    def on_resize(self) -> None:
        """Re-take the column set for the new width, keeping the selection."""
        if self.is_mounted:
            self._paint()

    # -- selection -------------------------------------------------------

    def _selected_row(self) -> LedgerTransactionReviewProjection | None:
        rows = () if self.page is None else self.page.rows
        return next((row for row in rows if row.transaction.transaction_id == self.selected_id), None)

    def _show_selection(self) -> None:
        row = self._selected_row()
        self.query_one("#entries-browse-selected", Static).update(
            tr("tui.ledger.entry_tools.browse.choose")
            if row is None
            else tr(
                "tui.ledger.entry_tools.browse.selected",
                entry=entry_label(row.transaction),
                state=lifecycle_label(row.transaction.lifecycle_state),
            )
        )
        self._set_busy(self.busy)

    def _mark_label(self) -> str:
        if self.selected_id is not None and self.selected_id in self.marked:
            return tr("tui.ledger.entry_tools.browse.unmark")
        return tr("tui.ledger.entry_tools.browse.mark")

    def _merge_label(self) -> str:
        return tr("tui.ledger.entry_tools.browse.action.merge", count=len(self.marked))

    def _show_marks(self) -> None:
        self.query_one("#entries-browse-mark", Button).label = self._mark_label()
        self.query_one("#entries-browse-merge", Button).label = self._merge_label()
        self._set_busy(self.busy)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Choose the entry under the cursor by its transaction identity."""
        if self.handle_navigation_selection(event):
            return
        if cast("DataTable[str]", event.data_table).id != "entries-browse" or event.row_key.value is None:
            return
        self.selected_id = str(event.row_key.value)
        self.query_one("#ledger-refusal", Static).update("")
        self._show_selection()
        self._show_marks()

    def _set_busy(self, busy: bool) -> None:
        """Hold every control while a read or a write is in flight."""
        self.busy = busy
        chosen = self._selected_row() is not None
        set_browse_controls(
            lambda selector: self.query_one(selector, Button),
            busy=busy,
            chosen=chosen,
            marked_count=len(self.marked),
            page=self.page,
        )

    # -- actions ---------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Route paging, filtering and the actions on the chosen entry."""
        if self.busy:
            self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.flow.in_flight_refusal"))
            return
        refusal = self.query_one("#ledger-refusal", Static)
        refusal.update("")
        button_id = event.button.id or ""
        if button_id == "entries-browse-apply":
            try:
                request = self._form_request()
            except ValueError as error:
                refusal.update(str(error))
                return
            self._read(request)
        elif button_id in {"entries-browse-previous", "entries-browse-next"}:
            step = BROWSE_PAGE_SIZE if button_id == "entries-browse-next" else -BROWSE_PAGE_SIZE
            self._read(self.request.model_copy(update={"offset": max(self.request.offset + step, 0)}))
        else:
            self._act(button_id)

    def _act(self, button_id: str) -> None:
        if button_id == "entries-browse-merge":
            self._review_merge()
            return
        row = self._selected_row()
        if row is None:
            self.query_one("#ledger-refusal", Static).update(tr("tui.ledger.entry_tools.browse.choose"))
            return
        transaction_id = row.transaction.transaction_id
        lifecycle_doors: dict[str, LedgerLifecycleDoorV1] = {
            "entries-browse-archive": self.doors.archive,
            "entries-browse-stash": self.doors.stash,
            "entries-browse-restore": self.doors.restore,
            "entries-browse-exclude": self.doors.exclude,
        }
        if button_id == "entries-browse-open":
            self.post_message(LedgerTransactionDetailRequested(transaction_id))
        elif button_id == "entries-browse-trace":
            self._open_trace(row)
        elif button_id == "entries-browse-mark":
            if transaction_id in self.marked:
                del self.marked[transaction_id]
            else:
                self.marked[transaction_id] = entry_label(row.transaction)
            self._paint()
        elif button_id in lifecycle_doors:
            self._review_lifecycle(lifecycle_doors[button_id], row)
        elif button_id == "entries-browse-remove":
            self._preview_removal(row)

    def _reason(self) -> str:
        return self._text("#entries-browse-reason")

    def _confirm(self, *, title: str, message: str, confirm: str, then: Callable[[], None]) -> None:
        """Show exactly what will change; submit only when the operator confirms."""

        def decided(accepted: bool | None) -> None:
            if accepted is True:
                then()
            else:
                self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.entry_tools.browse.cancelled"))

        self.app.push_screen(
            ConfirmScreen(
                title=title,
                message=message,
                confirm_label=confirm,
                cancel_label=tr("tui.ledger.entry_tools.cancel"),
            ),
            decided,
        )

    def _review_lifecycle(self, door: LedgerLifecycleDoorV1, row: LedgerTransactionReviewProjection) -> None:
        request = LedgerLifecycleMutationRequest(
            profile_id=self.doors.profile_id,
            transaction_id=row.transaction.transaction_id,
            reason=self._reason(),
        )
        operation = door.operation_id
        self._confirm(
            title=lifecycle_action(operation),
            message=lifecycle_consequence(operation, entry_label(row.transaction), request.reason),
            confirm=lifecycle_action(operation),
            then=lambda: self._start(self._submit_lifecycle(door, request, entry_label(row.transaction))),
        )

    def _start(self, work: Awaitable[None]) -> None:
        self._set_busy(True)
        self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.records.saving"))
        self.run_worker(work, exclusive=True, group="entries-browse")

    async def _submit_lifecycle(
        self, door: LedgerLifecycleDoorV1, request: LedgerLifecycleMutationRequest, label: str
    ) -> None:
        refusal = self.query_one("#ledger-refusal", Static)
        try:
            result: LedgerLifecycleOperationResult = await door(request)
        except AccountSessionExpiredError as error:
            self._settle_failure(error, private=True)
            return
        except CadrumoError as error:
            self._settle_failure(error)
            return
        if result.outcome == "validation_error" or result.validation is not None:
            messages = () if result.validation is None else result.validation.messages
            refusal.update(joined((tr("tui.ledger.entry_tools.browse.refused"), *messages)))
            self._settle_without_write()
            return
        self._reread(lifecycle_done(door.operation_id, label))

    def _preview_removal(self, row: LedgerTransactionReviewProjection) -> None:
        request = LedgerRemoveRequest(
            profile_id=self.doors.profile_id,
            transaction_id=row.transaction.transaction_id,
            reason=self._reason(),
            dry_run=True,
        )
        self._set_busy(True)
        self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.entry_tools.browse.previewing"))
        self.run_worker(self._removal_preview(request, entry_label(row.transaction)), exclusive=True)

    async def _removal_preview(self, request: LedgerRemoveRequest, label: str) -> None:
        try:
            preview = await self.doors.remove(request)
        except AccountSessionExpiredError as error:
            self._settle_failure(error, private=True)
            return
        except CadrumoError as error:
            self._settle_failure(error)
            return
        self._settle_without_write()
        self.query_one("#ledger-flow-status", Static).update("")
        report = preview.report
        if report.blocking_modelo_references:
            self.query_one("#ledger-refusal", Static).update(
                joined(
                    (
                        tr("tui.ledger.entry_tools.browse.remove_blocked", entry=label),
                        *(
                            tr(
                                "tui.ledger.entry_tools.blocker",
                                modelo=item.modelo,
                                year=item.filing_year,
                                period=item.period,
                                state=item.revision_state,
                            )
                            for item in report.blocking_modelo_references
                        ),
                    )
                )
            )
            return
        confirmed = request.model_copy(update={"dry_run": False})
        self._confirm(
            title=tr("tui.ledger.entry_tools.browse.action.remove"),
            message=removal_preview_text(preview, label),
            confirm=tr("tui.ledger.entry_tools.browse.remove_confirm"),
            then=lambda: self._start(self._submit_removal(confirmed, label)),
        )

    async def _submit_removal(self, request: LedgerRemoveRequest, label: str) -> None:
        try:
            result = await self.doors.remove(request)
        except AccountSessionExpiredError as error:
            self._settle_failure(error, private=True)
            return
        except CadrumoError as error:
            self._settle_failure(error)
            return
        if not result.report.removed:
            self.query_one("#ledger-refusal", Static).update(tr("tui.ledger.entry_tools.browse.remove_not_done"))
            self._settle_without_write()
            return
        self.marked.pop(request.transaction_id, None)
        self._reread(tr("tui.ledger.entry_tools.browse.done.remove", entry=label))

    def _review_merge(self) -> None:
        if len(self.marked) < 2:
            self.query_one("#ledger-refusal", Static).update(tr("tui.ledger.entry_tools.browse.merge_needs_two"))
            return
        try:
            request = LedgerMergeRequest(
                profile_id=self.doors.profile_id, child_ids=tuple(self.marked), reason=self._reason()
            )
        except ValidationError as error:
            self.query_one("#ledger-refusal", Static).update(door_refusal_text(error))
            return
        self._confirm(
            title=tr("tui.ledger.entry_tools.browse.merge_title"),
            message=joined(
                (tr("tui.ledger.entry_tools.browse.merge_consequence", count=len(self.marked)), *self.marked.values())
            ),
            confirm=tr("tui.ledger.entry_tools.browse.merge_confirm"),
            then=lambda: self._start(self._submit_merge(request)),
        )

    async def _submit_merge(self, request: LedgerMergeRequest) -> None:
        try:
            result = await self.doors.merge(request)
        except AccountSessionExpiredError as error:
            self._settle_failure(error, private=True)
            return
        except CadrumoError as error:
            self._settle_failure(error)
            return
        self.marked.clear()
        self.selected_id = result.merged_transaction_id
        self._reread(tr("tui.ledger.entry_tools.browse.done.merge", entry=short_id(result.merged_transaction_id)))

    def _reread(self, outcome: str) -> None:
        """Re-read the page a write changed, keeping the chosen entry by its identity."""
        self.run_worker(self._load(self.request, then=outcome), exclusive=True, group="entries-browse")

    def _settle_without_write(self) -> None:
        self._set_busy(False)
        self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.records.failed"))

    def _settle_failure(self, error: CadrumoError, *, private: bool = False) -> None:
        if private:
            self._clear_private_view()
        self.query_one("#ledger-refusal", Static).update(door_refusal_text(error))
        if isinstance(error, OperationOutcomeUnknownError):
            # The write may be saved: show the page as it now stands before anything is offered again.
            self.marked.clear()
            self._reread(self.failed_write_status(error, "tui.ledger.records.failed"))
            return
        self._set_busy(False)
        self.query_one("#ledger-flow-status", Static).update(
            self.failed_write_status(error, "tui.ledger.records.failed")
        )

    def _clear_private_view(self) -> None:
        """Discard every entry fact the screen holds once the admitted session is lost."""
        self.page = None
        self.selected_id = None
        self.marked.clear()
        self._paint()

    def _open_trace(self, row: LedgerTransactionReviewProjection) -> None:
        from .entries_trace import LedgerEntryTraceScreen

        state = LedgerBrowseStateV1(
            request=self.request, selected_id=self.selected_id, marked=tuple(self.marked.items())
        )
        doors = self.doors

        def back(controller: LedgerWorkspaceController) -> LedgerWorkspaceScreen:
            return LedgerEntriesBrowseScreen(controller, doors, state=state)

        screen = LedgerEntryTraceScreen(
            self.controller,
            doors,
            transaction_id=row.transaction.transaction_id,
            label=entry_label(row.transaction),
            back_to=back,
        )
        screen.back_area = self.back_area
        replace_workspace_body(self.app, screen)


__all__ = ["LedgerEntriesBrowseScreen"]
