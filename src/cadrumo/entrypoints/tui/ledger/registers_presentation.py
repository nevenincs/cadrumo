"""Shared mechanics of the Ledger register screens: paging, staging and typed input.

Each register screen reads its register through its own registered operation,
shows one page of it keyed by record identity, stages one typed request for
review and submits only the reviewed request. The registered operations own
every tax rule; these screens collect typed inputs and show the operation's
own result and refusals, and never compute a percentage or a valuation.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import ClassVar, Final, cast, override

from pydantic import BaseModel, ValidationError
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Input, Select, Static

from ....core.errors.hierarchy import CadrumoError
from ....core.i18n.render import tr
from ..account import AccountSessionExpiredError
from ..components.language import localized, repaint_tables
from ..components.theme import tokenised
from ..components.widgets import ContentDataTable
from ..operations.outcome import OperationOutcomeUnknownError
from .controller import LedgerWorkspaceController
from .workspace_presentation import door_refusal_text, ledger_workspace_page
from .workspace_screen import LedgerWorkspaceScreen

REGISTER_PAGE_SIZE: Final = 100
"""The most rows one register table shows at once."""

type RegisterRow = tuple[str, tuple[str, ...]]
"""One register record: its semantic key and its cells in column order."""


@dataclass(frozen=True, slots=True)
class RegisterColumnV1:
    """One register column: its key, locale key and declared width."""

    key: str
    label_key: str
    width: int


@dataclass(frozen=True, slots=True)
class RegisterListV1:
    """One paged register table a screen shows."""

    table_id: str
    """DOM id of the table; its pager controls take this id as their prefix."""
    heading_key: str
    columns: tuple[RegisterColumnV1, ...]
    rows: Callable[[], Sequence[RegisterRow]]
    """Every record in the register's own order; only one page is ever rendered."""


@dataclass(frozen=True, slots=True)
class RegisterOutcomeV1:
    """What one submitted request settled as, in the operator's language."""

    lines: tuple[str, ...] = ()
    refusal: str | None = None
    """The operation's own refusal; ``None`` when the request was applied."""


class RegisterPager:
    """The page of one register table currently shown."""

    def __init__(self) -> None:
        """Start on the first page of an empty register."""
        self.page = 0
        self.total = 0

    @property
    def page_count(self) -> int:
        """How many pages the register needs; an empty register still has one."""
        return max(1, -(-self.total // REGISTER_PAGE_SIZE))

    def window[T](self, rows: Sequence[T]) -> Sequence[T]:
        """The rows of the current page, after clamping it to the register's size."""
        self.total = len(rows)
        self.page = min(max(self.page, 0), self.page_count - 1)
        start = self.page * REGISTER_PAGE_SIZE
        return rows[start : start + REGISTER_PAGE_SIZE]

    def reveal(self, index: int) -> None:
        """Move to the page holding the record at ``index``."""
        self.page = index // REGISTER_PAGE_SIZE

    def label(self) -> str:
        """The page position in words."""
        return tr("tui.ledger.registers.page", page=self.page + 1, pages=self.page_count, total=self.total)


class LedgerRegisterScreen(LedgerWorkspaceScreen):
    """One register: paged tables, a typed form, a reviewed request and the operation's own outcome."""

    TITLE_LOCALE_KEY: ClassVar[str]
    PROMPT_LOCALE_KEY: ClassVar[str]
    EMPTY_LOCALE_KEY: ClassVar[str]

    DEFAULT_CSS = tokenised(
        """
        .register-actions { height: auto; margin-bottom: $cadrumo-stack; }
        .register-actions Button { margin-right: $cadrumo-space-1; }
        .register-field { height: auto; }
        #register-staged { height: auto; text-style: bold; }
        #register-result { height: auto; }
        """
    )

    def __init__(self, controller: LedgerWorkspaceController, *, id: str) -> None:
        """Start with nothing read, selected or staged."""
        super().__init__(controller, id=id)
        self.staged: BaseModel | None = None
        self.selected_key: str | None = None
        self.pagers: dict[str, RegisterPager] = {}
        self._busy = False

    @property
    @override
    def in_flight(self) -> bool:
        """A register read, a review or a write is out through a door."""
        return self._busy

    def register_lists(self) -> tuple[RegisterListV1, ...]:
        """The paged tables this register shows."""
        raise NotImplementedError

    def compose_form(self) -> ComposeResult:
        """The typed form the reviewed request is built from."""
        raise NotImplementedError

    def form_controls(self) -> tuple[str, ...]:
        """Selectors of every form control frozen while a request is staged."""
        raise NotImplementedError

    async def read_register(self) -> None:
        """Read the register through its registered list operation and keep its rows."""
        raise NotImplementedError

    async def stage(self) -> tuple[BaseModel, str]:
        """Build the request the form describes and its review summary."""
        raise NotImplementedError

    async def send(self, request: BaseModel) -> RegisterOutcomeV1:
        """Submit one reviewed request through the door and describe its outcome."""
        raise NotImplementedError

    def choose_row(self, table_id: str, key: str) -> None:
        """Show the chosen record and prefill the form from it."""
        raise NotImplementedError

    def clear_register(self) -> None:
        """Discard every record the screen holds."""
        raise NotImplementedError

    def has_records(self) -> bool:
        """Whether the register read holds any record."""
        return any(spec.rows() for spec in self.register_lists())

    @override
    def compose(self) -> ComposeResult:
        yield localized(
            Static(tr(self.TITLE_LOCALE_KEY), classes="cadrumo-banner", markup=False), self.TITLE_LOCALE_KEY
        )
        with ledger_workspace_page() as navigation:
            yield navigation
            yield localized(Static(tr(self.PROMPT_LOCALE_KEY), markup=False), self.PROMPT_LOCALE_KEY)
            for spec in self.register_lists():
                yield localized(Static(tr(spec.heading_key), classes="cadrumo-heading", markup=False), spec.heading_key)
                yield ContentDataTable[str](id=spec.table_id, cursor_type="row", zebra_stripes=True)
                with Horizontal(classes="register-actions"):
                    yield localized(
                        Button(tr("tui.ledger.registers.previous"), id=f"{spec.table_id}-previous"),
                        "tui.ledger.registers.previous",
                    )
                    yield localized(
                        Button(tr("tui.ledger.registers.next"), id=f"{spec.table_id}-next"),
                        "tui.ledger.registers.next",
                    )
                yield Static("", id=f"{spec.table_id}-page", markup=False)
            yield Static("", id="register-detail", markup=False)
            # The reviewed request, its decision and its outcome sit above the
            # form, so the operator never scrolls to see what will be sent.
            yield Static("", id="register-staged", markup=False)
            with Horizontal(id="register-decision", classes="register-actions"):
                yield localized(
                    Button(tr("tui.ledger.registers.confirm"), id="register-confirm", variant="primary", disabled=True),
                    "tui.ledger.registers.confirm",
                )
                yield localized(
                    Button(tr("tui.ledger.registers.cancel"), id="register-cancel", disabled=True),
                    "tui.ledger.registers.cancel",
                )
            yield Static("", id="ledger-flow-status", markup=False)
            yield Static("", id="ledger-refusal", classes="ledger-refusal", markup=False)
            yield Static("", id="register-result", markup=False)
            yield from self.compose_form()
            yield localized(
                Button(tr("tui.ledger.registers.review"), id="register-review"), "tui.ledger.registers.review"
            )

    def on_mount(self) -> None:
        """Show headings, then read the register without blocking the UI."""
        self.pagers = {spec.table_id: RegisterPager() for spec in self.register_lists()}
        self._paint()
        self._set_staged_controls(staged=False)
        self.form_mounted()
        self._busy = True
        self.run_worker(self._load(), exclusive=True)

    @override
    async def refresh_language(self) -> None:
        """Reword the tables in place, keeping the chosen record and any staged request."""
        await super().refresh_language()
        repaint_tables(self, self._paint)
        for select_id, options in self.choice_options().items():
            select = cast("Select[str]", self.query_one(f"#{select_id}", Select))
            chosen = select.value
            select.set_options(options)
            select.value = chosen

    def choice_options(self) -> dict[str, tuple[tuple[str, str], ...]]:
        """Every closed choice on the form, labelled in the current language."""
        return {}

    def form_mounted(self) -> None:
        """Adjust the mounted form before the register is read; nothing by default."""

    def _paint(self) -> None:
        self.populate_navigation()
        for spec in self.register_lists():
            table = cast("DataTable[str]", self.query_one(f"#{spec.table_id}", DataTable))
            for column in spec.columns:
                table.add_column(tr(column.label_key), key=column.key, width=column.width)
            self._fill(spec)

    def _fill(self, spec: RegisterListV1) -> None:
        """Render only the current page of one register table."""
        table = cast("DataTable[str]", self.query_one(f"#{spec.table_id}", DataTable))
        table.clear()
        pager = self.pagers[spec.table_id]
        rows = spec.rows()
        for key, cells in pager.window(rows):
            table.add_row(*cells, key=key)
        self.query_one(f"#{spec.table_id}-page", Static).update(pager.label())
        self.query_one(f"#{spec.table_id}-previous", Button).disabled = pager.page == 0
        self.query_one(f"#{spec.table_id}-next", Button).disabled = pager.page >= pager.page_count - 1
        self._restore_cursor(table)

    def _restore_cursor(self, table: DataTable[str]) -> None:
        if self.selected_key is None:
            return
        index = next((i for i, row in enumerate(table.ordered_rows) if row.key.value == self.selected_key), None)
        if index is not None:
            table.move_cursor(row=index, animate=False)

    def _render_lists(self) -> None:
        """Re-render every table on the page that holds the chosen record."""
        for spec in self.register_lists():
            keys = [key for key, _cells in spec.rows()]
            if self.selected_key in keys:
                self.pagers[spec.table_id].reveal(keys.index(self.selected_key))
            self._fill(spec)

    async def _load(self) -> None:
        status = self.query_one("#ledger-flow-status", Static)
        status.update(tr("tui.ledger.records.loading"))
        if not await self._read():
            return
        status.update("" if self.has_records() else tr(self.EMPTY_LOCALE_KEY))

    async def _read(self) -> bool:
        """Re-read the register; report the refusal on screen rather than raising it."""
        refusal = self.query_one("#ledger-refusal", Static)
        try:
            await self.read_register()
        except AccountSessionExpiredError as error:
            self._clear_private_view()
            refusal.update(door_refusal_text(error))
            self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.records.failed"))
            return False
        except CadrumoError as error:
            refusal.update(door_refusal_text(error))
            self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.records.failed"))
            return False
        finally:
            self._busy = False
        self._render_lists()
        return True

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Page, stage a reviewed request, or submit exactly the reviewed request."""
        button_id = event.button.id or ""
        if self._busy:
            self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.flow.in_flight_refusal"))
            return
        for spec in self.register_lists():
            if button_id in {f"{spec.table_id}-previous", f"{spec.table_id}-next"}:
                self.pagers[spec.table_id].page += 1 if button_id.endswith("-next") else -1
                self._fill(spec)
                return
        if button_id == "register-review":
            self._busy = True
            self.run_worker(self._stage(), exclusive=True)
        elif button_id == "register-cancel":
            self._unstage()
        elif button_id == "register-confirm" and self.staged is not None:
            self._busy = True
            self.query_one("#register-confirm", Button).disabled = True
            self.run_worker(self._submit(self.staged), exclusive=True)

    async def _stage(self) -> None:
        refusal = self.query_one("#ledger-refusal", Static)
        refusal.update("")
        self.query_one("#register-result", Static).update("")
        try:
            self.staged, summary = await self.stage()
        except AccountSessionExpiredError as error:
            self._clear_private_view()
            refusal.update(door_refusal_text(error))
            return
        except (CadrumoError, ValidationError) as error:
            refusal.update(door_refusal_text(error))
            return
        except ValueError as error:
            refusal.update(str(error))
            return
        finally:
            self._busy = False
        self.query_one("#register-staged", Static).update(summary)
        self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.records.reviewed"))
        self._set_staged_controls(staged=True)

    async def _submit(self, request: BaseModel) -> None:
        """Send one reviewed request, show its outcome, and re-read the register after a change."""
        status = self.query_one("#ledger-flow-status", Static)
        refusal = self.query_one("#ledger-refusal", Static)
        status.update(tr("tui.ledger.records.saving"))
        try:
            outcome = await self.send(request)
        except AccountSessionExpiredError as error:
            self._busy = False
            self._clear_private_view()
            refusal.update(door_refusal_text(error))
            status.update(self.failed_write_status(error, "tui.ledger.records.failed"))
            return
        except CadrumoError as error:
            refusal.update(door_refusal_text(error))
            if isinstance(error, OperationOutcomeUnknownError):
                # The change may be saved: drop it and show the register as it now stands.
                self._unstage()
                unknown = self.failed_write_status(error, "tui.ledger.records.failed")
                await self._read()
                status.update(unknown)
                return
            self._busy = False
            status.update(tr("tui.ledger.records.failed"))
            self._set_staged_controls(staged=True)
            return
        if outcome.refusal is not None:
            # The reviewed request stays staged so the operator can cancel it or correct and retry.
            self._busy = False
            refusal.update(outcome.refusal)
            status.update(tr("tui.ledger.records.failed"))
            self._set_staged_controls(staged=True)
            return
        self.query_one("#register-result", Static).update("\n".join(outcome.lines))
        self._unstage()
        if await self._read():
            status.update(tr("tui.ledger.records.saved"))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Choose a record by its identity; the form is refilled from it."""
        if self.handle_navigation_selection(event):
            return
        table_id = event.data_table.id or ""
        if self._busy or self.staged is not None or event.row_key.value is None:
            return
        if table_id not in self.pagers:
            return
        self.selected_key = str(event.row_key.value)
        self.query_one("#ledger-refusal", Static).update("")
        self.choose_row(table_id, self.selected_key)

    def _set_staged_controls(self, *, staged: bool) -> None:
        """Freeze the form while a request is staged, so only the reviewed request is sent."""
        for selector in (*self.form_controls(), "#register-review"):
            self.query_one(selector).disabled = staged
        self.query_one("#register-confirm", Button).disabled = not staged
        self.query_one("#register-cancel", Button).disabled = not staged
        # The decision row exists only while there is a reviewed request to decide on.
        self.query_one("#register-decision", Horizontal).display = staged

    def _unstage(self) -> None:
        self.staged = None
        self.query_one("#register-staged", Static).update("")
        self._set_staged_controls(staged=False)

    def _clear_private_view(self) -> None:
        """Discard every register fact the screen holds once the admitted session is lost."""
        self.staged = None
        self.selected_key = None
        self.clear_register()
        for selector in self.form_controls():
            control = self.query_one(selector)
            if isinstance(control, Input):
                control.value = ""
        for selector in ("#register-staged", "#register-detail", "#register-result"):
            self.query_one(selector, Static).update("")
        for spec in self.register_lists():
            self.pagers[spec.table_id] = RegisterPager()
            self._fill(spec)
        self._set_staged_controls(staged=False)

    def select_value(self, selector: str) -> str:
        """The chosen value of one select control."""
        return str(cast("Select[str]", self.query_one(selector, Select)).value)

    def input_value(self, selector: str) -> str:
        """The typed text of one input."""
        return self.query_one(selector, Input).value

    def set_input(self, selector: str, value: str) -> None:
        """Prefill one input from a chosen record."""
        self.query_one(selector, Input).value = value


def labelled_input(field_key: str, input_id: str, *, placeholder: str = "") -> ComposeResult:
    """One named input inside its own field, so the label and the input hide together."""
    with Vertical(id=f"{input_id}-field", classes="register-field"):
        yield localized(Static(tr(field_key), markup=False), field_key)
        yield Input(placeholder=placeholder, id=input_id)


def labelled_select(field_key: str, select_id: str, options: tuple[tuple[str, str], ...]) -> ComposeResult:
    """One named closed choice inside its own field; the first option is chosen."""
    with Vertical(id=f"{select_id}-field", classes="register-field"):
        yield localized(Static(tr(field_key), markup=False), field_key)
        yield Select[str](options, value=options[0][1], allow_blank=False, id=select_id)


def show_fields(screen: LedgerWorkspaceScreen, all_ids: tuple[str, ...], shown: frozenset[str]) -> None:
    """Show only the fields one action takes; the others are hidden, not cleared."""
    for control_id in all_ids:
        screen.query_one(f"#{control_id}-field").display = control_id in shown


__all__ = [
    "REGISTER_PAGE_SIZE",
    "LedgerRegisterScreen",
    "RegisterColumnV1",
    "RegisterListV1",
    "RegisterOutcomeV1",
    "RegisterPager",
    "RegisterRow",
    "labelled_input",
    "labelled_select",
    "show_fields",
]
