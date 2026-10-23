"""Browse entries: the paged entry list and the actions an operator takes on one entry.

The list reads one page at a time through ``ledger.list`` with the request's
own filters, group, sort and paging, so the screen never holds more than one
page. Every row is keyed by its transaction identity, and the selection is
restored by that identity after a page is re-read. Archive, stash, restore,
exclude, remove and merge are reviewed in a confirmation dialog that names
what will change, and only the reviewed request is submitted.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import ClassVar, Final, cast, override

from pydantic import ValidationError
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Checkbox, DataTable, Input, Select, Static

from ....application.ledger.lifecycle_contracts import (
    LedgerLifecycleMutationRequest,
    LedgerLifecycleOperationId,
    LedgerLifecycleOperationResult,
)
from ....application.ledger.list_operation import LedgerListProjection, LedgerListRequest
from ....application.ledger.merge_operation import LedgerMergeRequest
from ....application.ledger.remove_operation import LedgerRemoveOperationResult, LedgerRemoveRequest
from ....application.ledger.transaction_projection import LedgerTransactionReviewProjection
from ....application.review.filter import LedgerReviewStatus
from ....application.transactions.diagnostics import LedgerImportDiagnosticKind
from ....core.errors.hierarchy import CadrumoError
from ....core.i18n.render import tr
from ....core.ledger_sort import LedgerSortField, LedgerSortOrder
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ..account import AccountSessionExpiredError
from ..components.dialogs import ConfirmScreen
from ..components.language import localized, repaint_tables
from ..components.theme import tokenised
from ..components.widgets import ContentDataTable
from ..components.workspace_host import replace_workspace_body
from ..operations.outcome import OperationOutcomeUnknownError
from .controller import (
    LedgerTransactionDetailRequested,
    LedgerWorkspaceController,
    LedgerWorkspaceScreen,
    review_status_label,
)
from .entries_common import (
    CLASSIFICATION_LOCALE_KEYS,
    DIRECTION_LOCALE_KEYS,
    classification_label,
    direction_label,
    entry_label,
    joined,
    lifecycle_label,
    period_options,
    read_period,
    selected_value,
    short_id,
)
from .entries_doors import LedgerEntriesDoorsV1, LedgerLifecycleDoorV1
from .workspace_presentation import door_refusal_text, ledger_workspace_page

#: The most rows one page holds; the list never reads more than this at once.
BROWSE_PAGE_SIZE: Final = 200

_ISSUE_LOCALE_KEYS: Final[dict[LedgerImportDiagnosticKind, str]] = {
    LedgerImportDiagnosticKind.ORIGINAL_FILE: "tui.ledger.entry_tools.issue.original_file",
    LedgerImportDiagnosticKind.GAP: "tui.ledger.entry_tools.issue.gap",
    LedgerImportDiagnosticKind.DUPLICATE: "tui.ledger.entry_tools.issue.duplicate",
    LedgerImportDiagnosticKind.PARSER: "tui.ledger.entry_tools.issue.parser",
}
_SORT_LOCALE_KEYS: Final[dict[LedgerSortField, str]] = {
    LedgerSortField.DATE: "tui.ledger.entry_tools.sort.date",
    LedgerSortField.VALUE_DATE: "tui.ledger.entry_tools.sort.value_date",
    LedgerSortField.AMOUNT: "tui.ledger.entry_tools.sort.amount",
    LedgerSortField.DESCRIPTION: "tui.ledger.entry_tools.sort.description",
    LedgerSortField.CREATED_AT: "tui.ledger.entry_tools.sort.created_at",
    LedgerSortField.MODIFIED_AT: "tui.ledger.entry_tools.sort.modified_at",
    LedgerSortField.CLASSIFIED_AT: "tui.ledger.entry_tools.sort.classified_at",
    LedgerSortField.LIFECYCLE_STATE: "tui.ledger.entry_tools.sort.lifecycle_state",
    LedgerSortField.CLASSIFICATION: "tui.ledger.entry_tools.sort.classification",
}
_ORDER_LOCALE_KEYS: Final[dict[LedgerSortOrder, str]] = {
    LedgerSortOrder.ASC: "tui.ledger.entry_tools.order.asc",
    LedgerSortOrder.DESC: "tui.ledger.entry_tools.order.desc",
}
_LIFECYCLE_ACTION_LOCALE_KEYS: Final[dict[LedgerLifecycleOperationId, str]] = {
    "ledger.archive": "tui.ledger.entry_tools.browse.action.archive",
    "ledger.stash": "tui.ledger.entry_tools.browse.action.stash",
    "ledger.restore": "tui.ledger.entry_tools.browse.action.restore",
    "ledger.exclude": "tui.ledger.entry_tools.browse.action.exclude",
}
_LIFECYCLE_CONSEQUENCE_LOCALE_KEYS: Final[dict[LedgerLifecycleOperationId, str]] = {
    "ledger.archive": "tui.ledger.entry_tools.browse.consequence.archive",
    "ledger.stash": "tui.ledger.entry_tools.browse.consequence.stash",
    "ledger.restore": "tui.ledger.entry_tools.browse.consequence.restore",
    "ledger.exclude": "tui.ledger.entry_tools.browse.consequence.exclude",
}
_LIFECYCLE_DONE_LOCALE_KEYS: Final[dict[LedgerLifecycleOperationId, str]] = {
    "ledger.archive": "tui.ledger.entry_tools.browse.done.archive",
    "ledger.stash": "tui.ledger.entry_tools.browse.done.stash",
    "ledger.restore": "tui.ledger.entry_tools.browse.done.restore",
    "ledger.exclude": "tui.ledger.entry_tools.browse.done.exclude",
}
#: Table columns in priority order; narrow terminals drop from the end rather than overflow.
_COLUMNS: Final[tuple[tuple[str, str, int], ...]] = (
    ("date", "tui.ledger.column.date", 10),
    ("description", "tui.ledger.column.description", 16),
    ("amount", "tui.ledger.column.amount", 12),
    ("review_status", "tui.ledger.column.review_status", 9),
    ("lifecycle", "tui.ledger.entry_tools.column.lifecycle", 9),
    ("marked", "tui.ledger.entry_tools.column.marked", 7),
    ("classification", "tui.ledger.column.classification", 12),
    ("direction", "tui.ledger.column.direction", 10),
)
_ACTION_BUTTONS: Final[tuple[str, ...]] = (
    "entries-browse-open",
    "entries-browse-trace",
    "entries-browse-mark",
    "entries-browse-archive",
    "entries-browse-stash",
    "entries-browse-restore",
    "entries-browse-exclude",
    "entries-browse-remove",
)


@dataclass(frozen=True, slots=True)
class LedgerBrowseStateV1:
    """Where Browse entries stands: the request it reads, the chosen entry and the marked ones."""

    request: LedgerListRequest | None = None
    selected_id: str | None = None
    marked: tuple[tuple[str, str], ...] = field(default=())
    """Marked entries as ``(transaction id, label)``, in the order they were marked."""


def _options[TokenT: str](keys: Mapping[TokenT, str]) -> list[tuple[str, str]]:
    return [(tr(key), str(token)) for token, key in keys.items()]


def _status_options() -> list[tuple[str, str]]:
    return [(review_status_label(status.value), status.value) for status in LedgerReviewStatus]


def _direction_options() -> list[tuple[str, str]]:
    return [(tr(DIRECTION_LOCALE_KEYS[member]), member.value.lower()) for member in TransactionDirection]


def _classification_options() -> list[tuple[str, str]]:
    return [(tr(CLASSIFICATION_LOCALE_KEYS[member]), member.value) for member in BusinessClassification]


def _issue_options() -> list[tuple[str, str]]:
    return [(tr(key), member.value) for member, key in _ISSUE_LOCALE_KEYS.items()]


def _visible_columns(width: int) -> tuple[tuple[str, str, int], ...]:
    """Take columns in priority order while their headers and floors still fit the terminal."""
    taken: list[tuple[str, str, int]] = []
    used = 0
    for column in _COLUMNS:
        cost = max(column[2], len(tr(column[1]))) + 2
        if used + cost > width - 1:
            break
        taken.append(column)
        used += cost
    return tuple(taken)


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
        yield localized(
            Static(tr("tui.ledger.entry_tools.browse.title"), classes="cadrumo-banner"),
            "tui.ledger.entry_tools.browse.title",
        )
        with ledger_workspace_page() as navigation:
            yield navigation
            yield localized(
                Static(tr("tui.ledger.entry_tools.browse.prompt"), markup=False),
                "tui.ledger.entry_tools.browse.prompt",
            )
            with Horizontal(classes="entries-browse-row"):
                yield Select[str](
                    _status_options(), prompt=tr("tui.ledger.entry_tools.browse.any_status"), id="entries-browse-status"
                )
                yield Select[str](
                    _direction_options(),
                    prompt=tr("tui.ledger.entry_tools.browse.any_direction"),
                    id="entries-browse-direction",
                )
                yield Select[str](
                    _classification_options(),
                    prompt=tr("tui.ledger.entry_tools.browse.any_classification"),
                    id="entries-browse-classification",
                )
            with Horizontal(classes="entries-browse-row"):
                yield Select[str](
                    _issue_options(), prompt=tr("tui.ledger.entry_tools.browse.any_issue"), id="entries-browse-issue"
                )
                yield localized(
                    Input(placeholder=tr("tui.ledger.entry_tools.field.year"), max_length=4, id="entries-browse-year"),
                    "tui.ledger.entry_tools.field.year",
                )
                yield Select[str](
                    period_options(), prompt=tr("tui.ledger.entry_tools.period.any"), id="entries-browse-period"
                )
            with Horizontal(classes="entries-browse-row"):
                yield localized(
                    Input(placeholder=tr("tui.ledger.entry_tools.browse.text"), id="entries-browse-text"),
                    "tui.ledger.entry_tools.browse.text",
                )
                yield localized(
                    Input(placeholder=tr("tui.ledger.entry_tools.browse.import"), id="entries-browse-import"),
                    "tui.ledger.entry_tools.browse.import",
                )
                yield localized(
                    Input(placeholder=tr("tui.ledger.entry_tools.browse.account"), id="entries-browse-account"),
                    "tui.ledger.entry_tools.browse.account",
                )
            with Horizontal(classes="entries-browse-row"):
                yield localized(
                    Input(placeholder=tr("tui.ledger.entry_tools.browse.group"), id="entries-browse-group"),
                    "tui.ledger.entry_tools.browse.group",
                )
                yield Select[str](
                    _options(_SORT_LOCALE_KEYS),
                    prompt=tr("tui.ledger.entry_tools.browse.ledger_order"),
                    id="entries-browse-sort",
                )
                yield Select[str](
                    _options(_ORDER_LOCALE_KEYS),
                    value=LedgerSortOrder.ASC.value,
                    allow_blank=False,
                    id="entries-browse-order",
                )
            with Horizontal(classes="entries-browse-row"):
                yield Checkbox(tr("tui.ledger.entry_tools.browse.by_group"), id="entries-browse-by-group")
                yield Checkbox(tr("tui.ledger.entry_tools.browse.hide_rejected"), id="entries-browse-hide-rejected")
                yield localized(
                    Button(tr("tui.ledger.entry_tools.browse.apply"), id="entries-browse-apply", variant="primary"),
                    "tui.ledger.entry_tools.browse.apply",
                )
            yield Static("", id="entries-browse-window", markup=False)
            yield ContentDataTable[str](id="entries-browse", cursor_type="row", zebra_stripes=True)
            with Horizontal(classes="entries-browse-row"):
                yield localized(
                    Button(tr("tui.ledger.entry_tools.browse.previous"), id="entries-browse-previous", disabled=True),
                    "tui.ledger.entry_tools.browse.previous",
                )
                yield localized(
                    Button(tr("tui.ledger.entry_tools.browse.next"), id="entries-browse-next", disabled=True),
                    "tui.ledger.entry_tools.browse.next",
                )
            yield Static("", id="entries-browse-selected", markup=False)
            yield localized(
                Input(
                    placeholder=tr("tui.ledger.entry_tools.field.reason"), max_length=500, id="entries-browse-reason"
                ),
                "tui.ledger.entry_tools.field.reason",
            )
            with Horizontal(classes="entries-browse-row"):
                yield localized(
                    Button(tr("tui.ledger.entry_tools.browse.open"), id="entries-browse-open"),
                    "tui.ledger.entry_tools.browse.open",
                )
                yield localized(
                    Button(tr("tui.ledger.entry_tools.browse.trace"), id="entries-browse-trace"),
                    "tui.ledger.entry_tools.browse.trace",
                )
                yield Button(self._mark_label(), id="entries-browse-mark")
            with Horizontal(classes="entries-browse-row"):
                yield localized(
                    Button(tr("tui.ledger.entry_tools.browse.action.archive"), id="entries-browse-archive"),
                    "tui.ledger.entry_tools.browse.action.archive",
                )
                yield localized(
                    Button(tr("tui.ledger.entry_tools.browse.action.stash"), id="entries-browse-stash"),
                    "tui.ledger.entry_tools.browse.action.stash",
                )
                yield localized(
                    Button(tr("tui.ledger.entry_tools.browse.action.restore"), id="entries-browse-restore"),
                    "tui.ledger.entry_tools.browse.action.restore",
                )
            with Horizontal(classes="entries-browse-row"):
                yield localized(
                    Button(tr("tui.ledger.entry_tools.browse.action.exclude"), id="entries-browse-exclude"),
                    "tui.ledger.entry_tools.browse.action.exclude",
                )
                yield localized(
                    Button(tr("tui.ledger.entry_tools.browse.action.remove"), id="entries-browse-remove"),
                    "tui.ledger.entry_tools.browse.action.remove",
                )
                yield Button(self._merge_label(), id="entries-browse-merge")
            yield Static("", id="ledger-flow-status", markup=False)
            yield Static("", id="ledger-refusal", classes="ledger-refusal", markup=False)

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
            ("#entries-browse-status", _status_options()),
            ("#entries-browse-direction", _direction_options()),
            ("#entries-browse-classification", _classification_options()),
            ("#entries-browse-issue", _issue_options()),
            ("#entries-browse-sort", _options(_SORT_LOCALE_KEYS)),
            ("#entries-browse-order", _options(_ORDER_LOCALE_KEYS)),
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
        filters: list[str] = []
        for key, selector in (
            ("status", "#entries-browse-status"),
            ("direction", "#entries-browse-direction"),
            ("classification", "#entries-browse-classification"),
            ("issue", "#entries-browse-issue"),
        ):
            value = selected_value(self._select(selector))
            if value is not None:
                filters.append(f"{key}={value}")
        period = read_period(self._text("#entries-browse-year"), selected_value(self._select("#entries-browse-period")))
        if period is not None:
            filters.extend((f"period={period.code}", f"year={period.filing_year}"))
        for key, selector in (
            ("text", "#entries-browse-text"),
            ("import", "#entries-browse-import"),
            ("account", "#entries-browse-account"),
        ):
            value = self._text(selector)
            if value:
                filters.append(f"{key}={value}")
        sort = selected_value(self._select("#entries-browse-sort"))
        try:
            return LedgerListRequest(
                profile_id=self.doors.profile_id,
                filters=tuple(filters),
                group=self._text("#entries-browse-group") or None,
                by_group=self.query_one("#entries-browse-by-group", Checkbox).value,
                limit=BROWSE_PAGE_SIZE,
                offset=0,
                sort_by=None if sort is None else LedgerSortField(sort),
                sort_order=LedgerSortOrder(str(self._select("#entries-browse-order").value)),
                exclude_llm_rejected=self.query_one("#entries-browse-hide-rejected", Checkbox).value,
            )
        except ValidationError:
            # The request's own grammar refused a clause; its message would echo the typed value.
            raise ValueError(tr("tui.ledger.entry_tools.browse.filters_invalid")) from None

    def _show_request_in_form(self) -> None:
        """Fill the filter controls from the request this screen opened with."""
        clauses: dict[str, str] = {}
        for clause in self.request.filters:
            key, _, value = clause.partition("=")
            clauses[key] = value
        for key, selector in (
            ("status", "#entries-browse-status"),
            ("direction", "#entries-browse-direction"),
            ("classification", "#entries-browse-classification"),
            ("issue", "#entries-browse-issue"),
            ("period", "#entries-browse-period"),
        ):
            if key in clauses:
                self._select(selector).value = clauses[key]
        for key, selector in (
            ("year", "#entries-browse-year"),
            ("text", "#entries-browse-text"),
            ("import", "#entries-browse-import"),
            ("account", "#entries-browse-account"),
        ):
            self.query_one(selector, Input).value = clauses.get(key, "")
        self.query_one("#entries-browse-group", Input).value = self.request.group or ""
        if self.request.sort_by is not None:
            self._select("#entries-browse-sort").value = self.request.sort_by.value
        self._select("#entries-browse-order").value = self.request.sort_order.value
        self.query_one("#entries-browse-by-group", Checkbox).value = self.request.by_group
        self.query_one("#entries-browse-hide-rejected", Checkbox).value = self.request.exclude_llm_rejected

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
        columns = _visible_columns(self.app.size.width)
        names = [name for name, _, _ in columns]
        table.fill_column = names.index("description") if "description" in names else -1
        table.clear(columns=True)
        for name, key, size in columns:
            header = tr(key)
            table.add_column(header, key=name, width=max(size, len(header)))
        rows = () if self.page is None else self.page.rows
        for row in rows:
            cells = self._cells(row)
            table.add_row(*(cells[name] for name in names), key=row.transaction.transaction_id)
        table.absorb_surplus_width()
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

    def _cells(self, row: LedgerTransactionReviewProjection) -> dict[str, str]:
        transaction = row.transaction
        return {
            "date": transaction.date,
            "description": transaction.description,
            "amount": f"{transaction.amount} {transaction.currency}",
            "review_status": review_status_label(row.review_status.value),
            "lifecycle": lifecycle_label(transaction.lifecycle_state),
            "marked": tr("tui.ledger.entry_tools.browse.marked") if transaction.transaction_id in self.marked else "",
            "classification": classification_label(transaction.business_classification),
            "direction": direction_label(transaction.direction),
        }

    def _show_window(self) -> None:
        window = self.query_one("#entries-browse-window", Static)
        page = self.page
        previous = self.query_one("#entries-browse-previous", Button)
        following = self.query_one("#entries-browse-next", Button)
        if page is None:
            window.update("")
            previous.disabled = following.disabled = True
            return
        if not page.rows:
            window.update(tr("tui.ledger.entry_tools.browse.window_empty", total=page.total))
        else:
            window.update(
                tr(
                    "tui.ledger.entry_tools.browse.window",
                    first=page.offset + 1,
                    last=page.offset + len(page.rows),
                    total=page.total,
                )
            )
        previous.disabled = self.busy or page.offset == 0
        following.disabled = self.busy or page.offset + len(page.rows) >= page.total

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
        if event.data_table.id != "entries-browse" or event.row_key.value is None:
            return
        self.selected_id = str(event.row_key.value)
        self.query_one("#ledger-refusal", Static).update("")
        self._show_selection()
        self._show_marks()

    def _set_busy(self, busy: bool) -> None:
        """Hold every control while a read or a write is in flight."""
        self.busy = busy
        chosen = self._selected_row() is not None
        for button_id in _ACTION_BUTTONS:
            self.query_one(f"#{button_id}", Button).disabled = busy or not chosen
        self.query_one("#entries-browse-merge", Button).disabled = busy or len(self.marked) < 2
        self.query_one("#entries-browse-apply", Button).disabled = busy
        page = self.page
        self.query_one("#entries-browse-previous", Button).disabled = busy or page is None or page.offset == 0
        self.query_one("#entries-browse-next", Button).disabled = (
            busy or page is None or page.offset + len(page.rows) >= page.total
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
            title=tr(_LIFECYCLE_ACTION_LOCALE_KEYS[operation]),
            message=joined(
                (
                    tr(_LIFECYCLE_CONSEQUENCE_LOCALE_KEYS[operation], entry=entry_label(row.transaction)),
                    tr("tui.ledger.entry_tools.browse.reason_line", reason=request.reason) if request.reason else "",
                )
            ),
            confirm=tr(_LIFECYCLE_ACTION_LOCALE_KEYS[operation]),
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
        self._reread(tr(_LIFECYCLE_DONE_LOCALE_KEYS[door.operation_id], entry=label))

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


def removal_preview_text(preview: LedgerRemoveOperationResult, label: str) -> str:
    """Say what removing one entry would do, as its dry run reported it."""
    report = preview.report
    return joined(
        (
            tr("tui.ledger.entry_tools.browse.remove_consequence", entry=label),
            tr(
                "tui.ledger.entry_tools.browse.remove_cascade",
                evidence=len(report.cascaded_purchase_invoice_evidence_ids),
                attachments=len(report.cascaded_attachment_ids),
            ),
            tr("tui.ledger.entry_tools.stale_drafts", count=len(report.stale_draft_revision_references))
            if report.stale_draft_revision_references
            else "",
        )
    )


__all__ = ["BROWSE_PAGE_SIZE", "LedgerBrowseStateV1", "LedgerEntriesBrowseScreen", "removal_preview_text"]
