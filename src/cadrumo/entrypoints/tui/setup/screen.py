"""The setup screen: what Cadrumo needs on this computer, its state, and the one action each row offers.

The rows are the setup registry's own rows, read through the runtime's
``dependencies.status`` operation and worded by the shared setup wording, so
this screen says what the command line and the desktop say. Setting
something up submits ``dependencies.setup``; the runtime raises the plan for
review and the operation modal shows it, worded here, with any model licence
notice, before the person approves it. The rows are software only: the
profile's Google sign-in is not a setup item and is not offered here.

A runtime that cannot be reached is shown as unavailable; the screen never
starts or recovers it.
"""

from __future__ import annotations

from typing import ClassVar, Final, cast, override

from pydantic import BaseModel, ValidationError
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Button, DataTable, Static

from cadrumo_client.contracts.contracts import RefusalError
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

from ....application.dependency_contracts import (
    DEPENDENCY_SETUP_RECOVERIES,
    DependencyCheckMode,
    DependencyItemDeclaration,
    DependencyRecoveryAction,
    DependencyStatusRow,
)
from ....application.dependency_registry import dependency_item_declarations
from ....application.dependency_setup_operation import (
    DependencySetupOutcome,
    DependencySetupReviewV2,
    DependencyStatusResultV1,
)
from ....application.dependency_wording import dependency_row_wording, dependency_space_sentence
from ....core.errors.hierarchy import CadrumoError
from ....core.i18n.render import tr
from ..components.account_chrome import AccountChromeScreen
from ..components.language import repaint_tables
from ..components.theme import BASE_CSS, tokenised
from ..components.widgets import ContentDataTable, ContentScroll
from ..operations.controller_port import OperationControllerPort
from ..operations.modal import OperationModal, OperationModalOutcomeV1, OperationModalSettledOutcomeV1
from .door import SetupDoorPort

__all__ = ["SetupScreen", "setup_review_text"]

_MIB: Final = 1024**2
_GIB: Final = 1024**3


def _declaration(item_id: str) -> DependencyItemDeclaration:
    return next(declaration for declaration in dependency_item_declarations() if declaration.item_id == item_id)


def _item_name(item_id: str) -> str:
    return tr(f"application.{_declaration(item_id).display_key}")


def _size(value: int) -> str:
    if value >= _GIB:
        return tr("tui.setup.size.gigabytes", value=f"{value / _GIB:.1f}")
    return tr("tui.setup.size.megabytes", value=f"{max(1, round(value / _MIB))}")


def setup_review_text(projection: BaseModel) -> str:
    """Word a setup plan for the person who approves it: what, how large, from where, where, and any licence notice."""
    try:
        review = DependencySetupReviewV2.model_validate_json(projection.model_dump_json())
    except ValidationError:
        return projection.model_dump_json()
    lines = [tr("tui.setup.plan.heading")]
    for view in review.entries:
        entry = view.entry
        size = tr("tui.setup.plan.size_unknown") if entry.download_bytes is None else _size(entry.download_bytes)
        lines.append(
            tr("tui.setup.plan.entry", name=_item_name(entry.item_id), size=size, hosts=", ".join(entry.source_hosts))
        )
        for part in view.parts:
            part_size = tr("tui.setup.plan.size_unknown") if part.download_bytes is None else _size(part.download_bytes)
            lines.append(tr("tui.setup.plan.part", name=part.name, size=part_size))
        if view.shares_download_with is not None:
            lines.append(tr("tui.setup.plan.shared", name=_item_name(view.shares_download_with)))
        if view.destination_path is not None:
            lines.append(tr("tui.setup.plan.destination", path=view.destination_path))
        if entry.installs_outside_program:
            lines.append(tr("tui.setup.plan.installs_program"))
        if view.licence_notice is not None:
            lines.append(f"  {view.licence_notice}")
    total_key = "tui.setup.plan.total_unknown" if review.has_unknown_size else "tui.setup.plan.total"
    lines.append(tr(total_key, size=_size(review.known_download_bytes)))
    if not review.space_sufficient:
        free = "?" if review.space.free_bytes is None else _size(review.space.free_bytes)
        lines.append(dependency_space_sentence(required=_size(review.space.required_bytes), free=free))
    return "\n".join(lines)


class SetupScreen(AccountChromeScreen):
    """List every setup item with its state and open the one action its row offers."""

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

    def __init__(self, door: SetupDoorPort, *, focus_item: str | None = None) -> None:
        """Bind the door every read and setup goes through, and the item whose row is selected once it is read."""
        super().__init__()
        self._door = door
        self._rows: tuple[DependencyStatusRow, ...] = ()
        self._status: str = ""
        self._busy = False
        self._focus_item = focus_item

    @property
    def rows(self) -> tuple[DependencyStatusRow, ...]:
        """The registry rows this screen last read."""
        return self._rows

    @property
    def status_text(self) -> str:
        """The line under the list: complete, incomplete, working, or unavailable."""
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
            yield Static(tr("tui.setup.hint"), id="setup-hint", classes="cadrumo-note", markup=False)

    def on_mount(self) -> None:
        """Read every item's quick check."""
        self._populate_columns()
        self._read(DependencyCheckMode.QUICK)

    @override
    async def refresh_language(self) -> None:
        """Reword the retained rows."""
        await super().refresh_language()
        self.query_one(".cadrumo-banner", Static).update(tr("tui.setup.title"))
        self.query_one("#setup-intro", Static).update(tr("tui.setup.intro"))
        self.query_one("#setup-hint", Static).update(tr("tui.setup.hint"))
        self.query_one("#btn-setup-all", Button).label = tr("tui.setup.set_up_all")
        self.query_one("#btn-setup-check", Button).label = tr("tui.setup.check_again")
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
            declaration = _declaration(row.item_id)
            wording = dependency_row_wording(row, declaration)
            sentence = wording.sentence if wording.note is None else f"{wording.sentence} {wording.note}"
            table.add_row(wording.name, sentence, wording.action or "", key=row.item_id)

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
        complete = bool(self._rows) and all(row.recovery is None for row in self._rows)
        self.query_one("#btn-setup-all", Button).disabled = busy or not self._rows or complete
        self.query_one("#btn-setup-check", Button).disabled = busy

    def _show_status(self, status: DependencyStatusResultV1) -> None:
        self._rows = status.rows
        self._show_rows()
        self._select_focus_item()
        lines = [tr("tui.setup.complete" if status.complete else "tui.setup.incomplete")]
        if status.hardware_limited:
            lines.append(tr("tui.setup.hardware_limited"))
        self._set_status("\n".join(lines))

    def _unavailable(self) -> None:
        self._set_status(tr("tui.setup.unavailable"))

    def _read(self, mode: DependencyCheckMode, item_ids: tuple[str, ...] | None = None) -> None:
        self._set_busy(True)
        self._set_status(tr("tui.setup.checking"))
        self.run_worker(self._read_rows(mode, item_ids), group="setup-read", exclusive=True)

    async def _read_rows(self, mode: DependencyCheckMode, item_ids: tuple[str, ...] | None) -> None:
        try:
            if item_ids is None and mode is DependencyCheckMode.QUICK:
                status = await self._door.read_status(mode)
            else:
                checked = await self._door.verify(item_ids)
                status = checked if item_ids is None else await self._door.read_status(DependencyCheckMode.QUICK)
        except (FrontendRefusedError, RefusalError, CadrumoError):
            self._unavailable()
        else:
            self._show_status(status)
        finally:
            self._set_busy(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Set up everything that is not ready, or check every item fully."""
        if self._busy:
            return
        if event.button.id == "btn-setup-all":
            self.start_setup(None)
        elif event.button.id == "btn-setup-check":
            self._read(DependencyCheckMode.FULL)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Run the selected row's one action."""
        if event.data_table.id != "setup-items" or event.row_key.value is None or self._busy:
            return
        self.act_on(event.row_key.value)

    def act_on(self, item_id: str) -> None:
        """Run the one action ``item_id``'s row offers: set up, or check again."""
        row = next((row for row in self._rows if row.item_id == item_id), None)
        if row is None or row.recovery is None:
            return
        if row.recovery is DependencyRecoveryAction.CHECK_AGAIN:
            self._read(DependencyCheckMode.FULL, (item_id,))
        elif row.recovery in DEPENDENCY_SETUP_RECOVERIES:
            self.start_setup((item_id,))

    def start_setup(self, item_ids: tuple[str, ...] | None) -> None:
        """Submit a setup and open its plan review in the operation modal."""
        self._set_busy(True)
        self._set_status(tr("tui.setup.working"))
        self.run_worker(self._setup(item_ids), group="setup-run", exclusive=True)

    async def _setup(self, item_ids: tuple[str, ...] | None) -> None:
        try:
            controller = await self._door.start_setup(item_ids)
        except (FrontendRefusedError, RefusalError, CadrumoError):
            self._set_busy(False)
            self._unavailable()
            return

        async def settled(outcome: OperationModalOutcomeV1 | None) -> None:
            await self._settled(controller, outcome)

        def dismissed(outcome: OperationModalOutcomeV1 | None) -> None:
            self.run_worker(settled(outcome), group="setup-settled", exclusive=True)

        self.app.push_screen(OperationModal(controller, review_text=setup_review_text), dismissed)

    async def _settled(self, controller: OperationControllerPort, outcome: OperationModalOutcomeV1 | None) -> None:
        summary: str | None = None
        if isinstance(outcome, OperationModalSettledOutcomeV1):
            try:
                result = await self._door.setup_result(controller, outcome.view_model.projection)
            except (FrontendRefusedError, RefusalError, CadrumoError):
                result = None
            if result is not None:
                summary = tr(f"tui.setup.outcome.{result.outcome.value}")
                if result.outcome is DependencySetupOutcome.NOT_ENOUGH_SPACE and result.space is not None:
                    free = "?" if result.space.free_bytes is None else _size(result.space.free_bytes)
                    summary += " " + dependency_space_sentence(required=_size(result.space.required_bytes), free=free)
        self._set_busy(False)
        self._read(DependencyCheckMode.QUICK)
        if summary is not None:
            self.notify(summary)

    def action_close(self) -> None:
        """Return to whatever opened the screen."""
        self.dismiss(None)
