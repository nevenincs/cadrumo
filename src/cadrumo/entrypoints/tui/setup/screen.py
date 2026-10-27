"""Profile-bound component status and browser setup through registered operations."""

from __future__ import annotations

from typing import ClassVar, Protocol, cast, override

from pydantic import TypeAdapter, ValidationError
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Button, DataTable, Input, Static

from cadrumo_client.contracts.contracts import RefusalError
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

from ....application.components_operations import ProvisionResult
from ....application.dependency_contracts import (
    DEPENDENCY_SETUP_RECOVERIES,
    DependencyBlockedReason,
    DependencyItemDeclaration,
    DependencyItemKind,
    DependencyRecoveryAction,
    DependencyStatusRow,
)
from ....application.dependency_registry import dependency_item_declarations
from ....application.dependency_wording import (
    dependency_desktop_pointer,
    dependency_failure_key,
    dependency_row_wording,
)
from ....application.operations.models import OperationId
from ....core.errors.hierarchy import CadrumoError
from ....core.i18n.render import tr
from ..components.account_chrome import AccountChromeScreen
from ..components.language import repaint_tables
from ..components.theme import BASE_CSS, tokenised
from ..components.widgets import ContentDataTable, ContentScroll
from ..operations.controller_port import OperationControllerPort
from ..operations.modal import OperationModal


class SetupStatusReaderPort(Protocol):
    """Read the signed-in profile's registered component status."""

    async def read_status(self) -> ProvisionResult:
        """Read typed local component rows."""
        ...


class SetupOperationsPort(SetupStatusReaderPort, Protocol):
    """Submit component work under the same admitted profile session."""

    async def review(self, operation_id: OperationId) -> OperationControllerPort:
        """Attach for explicit review only; this grants no execution ownership."""
        ...

    async def submit(self, *, verify: bool, items: tuple[DependencyItemKind, ...]) -> OperationControllerPort:
        """Submit browser setup or a full check without starting execution."""
        ...


def _declaration(item_id: str) -> DependencyItemDeclaration:
    return next(item for item in dependency_item_declarations() if item.item_id == item_id)


class SetupScreen(AccountChromeScreen):
    """List every setup item with its state and run the one action its row offers."""

    BINDINGS: ClassVar = [Binding("escape", "close", "", show=False)]
    CSS = BASE_CSS + tokenised(
        """
        #setup-page { width: 100%; height: 1fr; overflow-x: hidden; }
        #setup-intro, #setup-status, #setup-hint { height: auto; padding: $cadrumo-space-0 $cadrumo-space-1; }
        #setup-status { margin: $cadrumo-stack $cadrumo-space-0 $cadrumo-space-0 $cadrumo-space-0; }
        #setup-items { width: 100%; }
        #setup-actions { height: auto; padding: $cadrumo-space-0 $cadrumo-space-1; }
        """
    )

    def __init__(self, operations: SetupOperationsPort | None = None, *, focus_item: str | None = None) -> None:
        """Bind the door every read and setup goes through, and the item whose row is selected once it is read."""
        super().__init__()
        self._operations = operations
        self._rows: tuple[DependencyStatusRow, ...] = ()
        self._status: str = ""
        self._busy = False
        self._focus_item = focus_item

    @property
    def rows(self) -> tuple[DependencyStatusRow, ...]:
        """The rows this screen last read."""
        return self._rows

    @property
    def status_text(self) -> str:
        """The line under the list: complete, incomplete, working, progress, or unavailable."""
        return self._status

    @override
    def compose(self) -> ComposeResult:
        yield Static(tr("tui.setup.title"), classes="cadrumo-banner", markup=False)
        with ContentScroll(id="setup-page", classes="cadrumo-scroll"):
            yield Static(tr("tui.setup.intro"), id="setup-intro", classes="cadrumo-subtle", markup=False)
            yield ContentDataTable[str](id="setup-items", cursor_type="row", zebra_stripes=True)
            yield Static(id="setup-status", markup=False)
            with Horizontal(id="setup-actions"):
                yield Button(tr("tui.setup.set_up_all"), id="btn-setup-all", disabled=True)
                yield Button(tr("tui.setup.check_again"), id="btn-setup-check", disabled=True)
            yield Input(
                placeholder=tr("tui.setup.review.reference"),
                id="setup-review-reference",
                disabled=self._operations is None,
            )
            yield Button(tr("tui.setup.review.open"), id="btn-setup-review", disabled=self._operations is None)
            yield Static(tr("tui.setup.hint"), id="setup-hint", classes="cadrumo-note", markup=False)

    def on_mount(self) -> None:
        """Read every item's quick check."""
        self._populate_columns()
        self._read()

    @override
    async def refresh_language(self) -> None:
        """Reword the retained rows."""
        await super().refresh_language()
        self.query_one(".cadrumo-banner", Static).update(tr("tui.setup.title"))
        self.query_one("#setup-intro", Static).update(tr("tui.setup.intro"))
        self.query_one("#setup-hint", Static).update(tr("tui.setup.hint"))
        self.query_one("#btn-setup-all", Button).label = tr("tui.setup.set_up_all")
        self.query_one("#btn-setup-check", Button).label = tr("tui.setup.check_again")
        self.query_one("#setup-review-reference", Input).placeholder = tr("tui.setup.review.reference")
        self.query_one("#btn-setup-review", Button).label = tr("tui.setup.review.open")
        repaint_tables(self, self._repaint)

    def _repaint(self) -> None:
        self._populate_columns()
        self._show_rows()

    def _populate_columns(self) -> None:
        table = cast("DataTable[str]", self.query_one("#setup-items", DataTable))
        table.add_column(tr("tui.setup.column.item"))
        table.add_column(tr("tui.setup.column.state"))
        table.add_column(tr("tui.setup.column.action"))

    def _show_rows(self) -> None:
        table = cast("DataTable[str]", self.query_one("#setup-items", DataTable))
        table.clear()
        for row in self._rows:
            wording = dependency_row_wording(row, _declaration(row.item_id))
            table.add_row(wording.name, wording.sentence, wording.action or "", key=row.item_id)

    def _select_focus_item(self) -> None:
        """Select the row of the item this screen was opened on, once, so Enter runs its action."""
        item_id, self._focus_item = self._focus_item, None
        index = next((index for index, row in enumerate(self._rows) if row.item_id == item_id), None)
        if index is None:
            return
        table = cast("DataTable[str]", self.query_one("#setup-items", DataTable))
        table.move_cursor(row=index)
        table.focus()

    def _set_status(self, text: str) -> None:
        self._status = text
        self.query_one("#setup-status", Static).update(text)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        # A row that points to the desktop is not set up here, as in the role's own setup of every item.
        complete = bool(self._rows) and all(
            row.recovery in {None, DependencyRecoveryAction.SET_UP_IN_DESKTOP} for row in self._rows
        )
        self.query_one("#btn-setup-all", Button).disabled = busy or not self._rows or complete
        self.query_one("#btn-setup-check", Button).disabled = busy

    def _show_status(self, status: ProvisionResult) -> None:
        self._rows = status.rows
        self._show_rows()
        self._select_focus_item()
        lines = [tr("tui.setup.complete" if status.setup_complete is True else "tui.setup.incomplete")]
        if any(row.blocked_reason is DependencyBlockedReason.HARDWARE for row in self._rows):
            lines.append(tr("tui.setup.hardware_limited"))
        if status.failure_category is not None:
            # The engine refused the check itself, so it reported no row to word.
            lines.append(tr(dependency_failure_key(status.failure_category)))
        self._set_status("\n".join(lines))

    def _unavailable(self) -> None:
        self._set_status(tr("tui.setup.unavailable"))

    def _read(self) -> None:
        if self._operations is None:
            self._set_status(tr("tui.setup.sign_in_first"))
            self.query_one("#btn-setup-check", Button).disabled = True
            return
        self._set_busy(True)
        self._set_status(tr("tui.setup.checking"))
        self.run_worker(self._read_rows(), group="setup-read", exclusive=True)

    async def _read_rows(self) -> None:
        try:
            if self._operations is not None:
                self._show_status(await self._operations.read_status())
        except (RefusalError, FrontendRefusedError, CadrumoError):
            self._unavailable()
        finally:
            self._set_busy(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Open the supervised browser setup or full check."""
        if self._busy:
            return
        if event.button.id == "btn-setup-review":
            self.run_worker(self._open_review(), group="setup-review", exclusive=True)
        elif event.button.id == "btn-setup-all":
            self.start_setup((DependencyItemKind.BROWSER,))
        elif event.button.id == "btn-setup-check":
            self.run_worker(self._open_operation(verify=True, items=()), group="setup-submit", exclusive=True)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Run the selected row's declared recovery."""
        if event.data_table.id == "setup-items" and event.row_key.value is not None and not self._busy:
            self.act_on(event.row_key.value)

    def act_on(self, item_id: str) -> None:
        """Submit only the recovery the current row offers."""
        row = next((row for row in self._rows if row.item_id == item_id), None)
        if row is None or row.recovery is None:
            return
        if row.recovery is DependencyRecoveryAction.SET_UP_IN_DESKTOP:
            self.notify(dependency_desktop_pointer())
        elif row.recovery is DependencyRecoveryAction.CHECK_AGAIN:
            self.run_worker(self._open_operation(verify=True, items=(row.kind,)), group="setup-submit", exclusive=True)
        elif row.recovery in DEPENDENCY_SETUP_RECOVERIES:
            self.start_setup((row.kind,))

    def start_setup(self, items: tuple[DependencyItemKind, ...]) -> None:
        """Open the operation's exact plan review; Python sets up only the browser."""
        if items and items != (DependencyItemKind.BROWSER,):
            self.notify(dependency_desktop_pointer())
            return
        self.run_worker(
            self._open_operation(verify=False, items=(DependencyItemKind.BROWSER,)),
            group="setup-submit",
            exclusive=True,
        )

    async def _open_review(self) -> None:
        """Display an existing setup's current plan without starting or taking ownership."""
        operations = self._operations
        if operations is None:
            self._set_status(tr("tui.setup.sign_in_first"))
            return
        try:
            operation_id = TypeAdapter(OperationId).validate_python(
                self.query_one("#setup-review-reference", Input).value.strip()
            )
        except ValidationError:
            self._set_status(tr("tui.setup.review.reference"))
            return
        try:
            controller = await operations.review(operation_id)
            await self.app.push_screen_wait(OperationModal(controller, response_only=True))
        except (RefusalError, FrontendRefusedError, CadrumoError):
            self._unavailable()

    async def _open_operation(self, *, verify: bool, items: tuple[DependencyItemKind, ...]) -> None:
        if self._operations is None:
            self._set_status(tr("tui.setup.sign_in_first"))
            return
        self._set_busy(True)
        try:
            controller = await self._operations.submit(verify=verify, items=items)
            await controller.start()
            await self.app.push_screen_wait(OperationModal(controller))
        except (RefusalError, FrontendRefusedError, CadrumoError):
            self._unavailable()
        finally:
            if self.is_mounted:
                self._set_busy(False)
                self._read()

    def action_close(self) -> None:
        """Return to the previous screen."""
        self.dismiss(None)
