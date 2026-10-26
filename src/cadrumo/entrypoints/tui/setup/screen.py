"""The setup screen: what Cadrumo needs on this computer, its state, and the one action each row offers.

The rows are the native component engine's own rows, read through the
components role and worded by the shared setup wording, so this screen says
what the command line, MCP and the desktop say. Setting something up runs the
role's setup: the role sends the plan, this screen shows it in a dialog, and
only the person's approval of exactly that plan lets anything move. The local
AI is not set up here: only the desktop app sets it up, so its row points to
the desktop and offers no setup. While a setup runs the screen shows the
role's progress and offers to stop it. A setup of an item another process is
already setting up follows that one instead: no dialog, the other setup's
progress, and its result; stopping it stops only the following. A Resume after
an interruption that this screen approved runs under the same approval without
a second dialog while the plan is unchanged. The rows are software only: the profile's
Google sign-in is not a setup item and is not offered here.

An engine that cannot be started or breaks its protocol is shown as
unavailable; the screen never acts around it.
"""

from __future__ import annotations

import asyncio
import math
from collections.abc import Callable
from concurrent.futures import Future
from typing import ClassVar, Final, cast, override

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Button, DataTable, Static

from cadrumo_client.contracts.contracts import RefusalError
from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

from ....adapters.outbound.components.client import ComponentsCancellation
from ....adapters.outbound.components.protocol import (
    ComponentsAnswer,
    ComponentsApprove,
    ComponentsDecline,
    ComponentsEvent,
    ComponentsNoticeCode,
    ComponentsNoticeLine,
    ComponentsOutcome,
    ComponentsPhaseLine,
    ComponentsPlan,
    ComponentsProgressLine,
    ComponentsResultLine,
    ComponentsReviewLine,
)
from ....application.dependency_contracts import (
    DEPENDENCY_SETUP_RECOVERIES,
    DependencyBlockedReason,
    DependencyItemDeclaration,
    DependencyItemKind,
    DependencyRecoveryAction,
    DependencySetupStep,
    DependencyState,
    DependencyStatusRow,
)
from ....application.dependency_registry import dependency_item_declarations
from ....application.dependency_wording import (
    dependency_desktop_pointer,
    dependency_failure_key,
    dependency_retry_sentence,
    dependency_row_wording,
    dependency_space_sentence,
)
from ....core.errors.hierarchy import CadrumoError
from ....core.i18n.render import tr
from ....core.storage_taxonomy import StorageCategory
from ....core.storage_taxonomy_locations import storage_path
from ..components.account_chrome import AccountChromeScreen
from ..components.dialogs import ConfirmScreen
from ..components.language import repaint_tables
from ..components.theme import BASE_CSS, tokenised
from ..components.widgets import ContentDataTable, ContentScroll
from .door import SetupDoorPort

__all__ = ["SetupScreen", "setup_outcome_text", "setup_review_text"]

_MIB: Final = 1024**2
_GIB: Final = 1024**3
_ANSWER_POLL_S: Final = 0.2

_STEP_KEYS: Final = {
    DependencySetupStep.PLAN: "tui.setup.step.plan",
    DependencySetupStep.PREFLIGHT: "tui.setup.step.preflight",
    DependencySetupStep.DOWNLOAD: "tui.setup.step.download",
    DependencySetupStep.INSTALL: "tui.setup.step.install",
    DependencySetupStep.VERIFY: "tui.setup.step.verify",
    DependencySetupStep.CLEANUP: "tui.setup.step.cleanup",
}

_OUTCOME_KEYS: Final = {
    ComponentsOutcome.COMPLETED: "tui.setup.outcome.completed",
    ComponentsOutcome.NOTHING_TO_DO: "tui.setup.outcome.nothing_to_do",
    ComponentsOutcome.NEEDS_APPROVAL: "tui.setup.outcome.rejected",
    ComponentsOutcome.PLAN_CHANGED: "tui.setup.outcome.plan_changed",
    ComponentsOutcome.CANCELLED: "tui.setup.outcome.cancelled",
    ComponentsOutcome.BUSY: "tui.setup.outcome.busy",
}
"""The summary of each setup outcome that names no failure; a refusal or failure says its category's sentence."""

_UNREACHABLE: Final = (RefusalError, CadrumoError)


def _declaration(item_id: str) -> DependencyItemDeclaration:
    return next(declaration for declaration in dependency_item_declarations() if declaration.item_id == item_id)


def _item_name(item_id: str) -> str:
    return tr(f"application.{_declaration(item_id).display_key}")


def _size(value: int) -> str:
    if value >= _GIB:
        return tr("tui.setup.size.gigabytes", value=f"{value / _GIB:.1f}")
    return tr("tui.setup.size.megabytes", value=f"{max(1, round(value / _MIB))}")


def _space_sentence(plan: ComponentsPlan) -> str:
    free = "?" if plan.space.free_bytes is None else _size(plan.space.free_bytes)
    return dependency_space_sentence(required=_size(plan.space.required_bytes), free=free)


def _destination(destination: str | None) -> str | None:
    """Say where a plan stores what it downloads, for the destinations that are storage locations."""
    if destination is None:
        return None
    try:
        category = StorageCategory(destination)
    except ValueError:
        return None
    return tr("tui.setup.plan.destination", path=str(storage_path(category)))


def setup_review_text(plan: ComponentsPlan) -> str:
    """Word a setup plan for the person who approves it: what, how large, from where, and where."""
    unknown = tr("tui.setup.plan.size_unknown")
    lines = [tr("tui.setup.plan.heading")]
    for entry in plan.entries:
        size = unknown if entry.download_bytes is None else _size(entry.download_bytes)
        lines.append(
            tr("tui.setup.plan.entry", name=_item_name(entry.item_id), size=size, hosts=", ".join(entry.source_hosts))
        )
        destination = _destination(None if entry.destination is None else entry.destination.value)
        if destination is not None:
            lines.append(destination)
        if entry.installs_outside_program:
            lines.append(tr("tui.setup.plan.installs_program"))
    total_key = "tui.setup.plan.total_unknown" if plan.has_unknown_size else "tui.setup.plan.total"
    lines.append(tr(total_key, size=_size(plan.known_download_bytes)))
    if not plan.space.sufficient:
        lines.append(_space_sentence(plan))
    return "\n".join(lines)


def _usable(rows: tuple[DependencyStatusRow, ...], items: tuple[DependencyItemKind, ...]) -> bool:
    named = {item.value for item in items}
    return all(
        row.state in {DependencyState.READY, DependencyState.STALE} for row in rows if not named or row.item_id in named
    )


def setup_outcome_text(
    result: ComponentsResultLine, items: tuple[DependencyItemKind, ...], *, followed: bool = False
) -> str:
    """Say how a setup ended: its outcome's sentence, or the item and sentence of its failure.

    A setup that followed one already running ends ``busy`` when it stopped
    following, while the followed setup carries on.
    """
    if followed and result.outcome is ComponentsOutcome.BUSY:
        return tr("tui.setup.outcome.follow_stopped")
    if result.outcome is ComponentsOutcome.NOTHING_TO_DO and not _usable(result.status_rows(), items):
        # Nothing could be set up, so the rows say what holds each item.
        return tr("tui.setup.incomplete")
    key = _OUTCOME_KEYS.get(result.outcome)
    if key is not None:
        return tr(key)
    category = result.failure_category
    sentence = tr(dependency_failure_key(category)) if category is not None else tr("tui.setup.incomplete")
    if result.item_id is not None:
        sentence = f"{_item_name(result.item_id)}: {sentence}"
    if category is DependencyFailureCategory.DISK_FULL and result.plan is not None:
        sentence = f"{sentence} {_space_sentence(result.plan)}"
    return sentence


def _event_text(event: ComponentsEvent) -> str | None:
    """Word one event the role sent while it works; ``None`` for one that changes nothing shown."""
    if isinstance(event, ComponentsPhaseLine):
        return tr("tui.setup.progress", name=_item_name(event.item_id), step=tr(_STEP_KEYS[event.step]))
    if isinstance(event, ComponentsProgressLine):
        return tr(
            "tui.setup.progress_bytes",
            name=_item_name(event.subject_code),
            done=_size(event.completed),
            total=_size(event.total),
            percent=min(100, event.completed * 100 // event.total),
        )
    return _notice_text(event)


def _notice_text(event: ComponentsNoticeLine) -> str | None:
    if event.notice_code is ComponentsNoticeCode.RETRYING and event.subject_code is not None:
        seconds = math.ceil((event.delay_ms or 0) / 1000)
        sentence = dependency_retry_sentence(attempt=event.attempt or 1, delay_s=seconds)
        return f"{_item_name(event.subject_code)}: {sentence}"
    if event.notice_code is ComponentsNoticeCode.WAITING_FOR_SERVER and event.subject_code is not None:
        return tr("tui.setup.waiting_for_program", name=_item_name(event.subject_code))
    if event.notice_code is ComponentsNoticeCode.FOLLOWING and event.subject_code is not None:
        return tr("tui.setup.following", name=_item_name(event.subject_code))
    if event.notice_code is ComponentsNoticeCode.CANCEL_REQUESTED:
        return tr("tui.setup.stopping")
    return None


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

    def __init__(self, door: SetupDoorPort, *, focus_item: str | None = None) -> None:
        """Bind the door every read and setup goes through, and the item whose row is selected once it is read."""
        super().__init__()
        self._door = door
        self._rows: tuple[DependencyStatusRow, ...] = ()
        self._status: str = ""
        self._busy = False
        self._focus_item = focus_item
        self._setup_stop: ComponentsCancellation | None = None
        self._approved: dict[tuple[DependencyItemKind, ...], str] = {}
        self._following = False

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
                yield Button(tr("tui.setup.stop"), id="btn-setup-stop")
            yield Static(tr("tui.setup.hint"), id="setup-hint", classes="cadrumo-note", markup=False)

    def on_mount(self) -> None:
        """Read every item's quick check."""
        self.query_one("#btn-setup-stop", Button).display = False
        self._populate_columns()
        self._read()

    def on_unmount(self) -> None:
        """Stop a setup still running, so the role ends with the screen."""
        if self._setup_stop is not None:
            self._setup_stop.cancel()

    @override
    async def refresh_language(self) -> None:
        """Reword the retained rows."""
        await super().refresh_language()
        self.query_one(".cadrumo-banner", Static).update(tr("tui.setup.title"))
        self.query_one("#setup-intro", Static).update(tr("tui.setup.intro"))
        self.query_one("#setup-hint", Static).update(tr("tui.setup.hint"))
        self.query_one("#btn-setup-all", Button).label = tr("tui.setup.set_up_all")
        self.query_one("#btn-setup-check", Button).label = tr("tui.setup.check_again")
        self.query_one("#btn-setup-stop", Button).label = tr("tui.setup.stop")
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
        # A row that points to the desktop is not set up here, as in the role's own setup of every item.
        complete = bool(self._rows) and all(
            row.recovery in {None, DependencyRecoveryAction.SET_UP_IN_DESKTOP} for row in self._rows
        )
        self.query_one("#btn-setup-all", Button).disabled = busy or not self._rows or complete
        self.query_one("#btn-setup-check", Button).disabled = busy
        self.query_one("#btn-setup-stop", Button).display = self._setup_stop is not None

    def _show_status(self, status: ComponentsResultLine) -> None:
        self._rows = status.status_rows()
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

    def _relay(self, loop: asyncio.AbstractEventLoop) -> _LoopRelay:
        return _LoopRelay(loop, self._show_event)

    def _show_event(self, event: ComponentsEvent) -> None:
        if isinstance(event, ComponentsNoticeLine) and event.notice_code is ComponentsNoticeCode.FOLLOWING:
            # Another process is setting the item up: this setup asks nothing and reports that one.
            self._following = True
        text = _event_text(event)
        if text is not None and self.is_mounted:
            self._set_status(text)

    def _read(self, items: tuple[DependencyItemKind, ...] = (), *, full: bool = False) -> None:
        self._set_busy(True)
        self._set_status(tr("tui.setup.checking"))
        self.run_worker(self._read_rows(items, full=full), group="setup-read", exclusive=True)

    async def _read_rows(self, items: tuple[DependencyItemKind, ...], *, full: bool) -> None:
        try:
            if full:
                relay = self._relay(asyncio.get_running_loop())
                checked = await self._door.verify(items, on_event=relay)
                # A check of one item reports its row alone, so every row is read again.
                status = await self._door.read_status() if items else checked
            else:
                status = await self._door.read_status()
        except _UNREACHABLE:
            self._unavailable()
        else:
            self._show_status(status)
        finally:
            self._set_busy(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Set up everything that offers it, check every item fully, or stop the running setup."""
        if event.button.id == "btn-setup-stop":
            if self._setup_stop is not None:
                self._setup_stop.cancel()
                self._set_status(tr("tui.setup.stopping"))
            return
        if self._busy:
            return
        if event.button.id == "btn-setup-all":
            self.start_setup(())
        elif event.button.id == "btn-setup-check":
            self._read(full=True)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Run the selected row's one action."""
        if event.data_table.id != "setup-items" or event.row_key.value is None or self._busy:
            return
        self.act_on(event.row_key.value)

    def act_on(self, item_id: str) -> None:
        """Run the one action ``item_id``'s row offers: set up, resume, try again, update, or check again.

        A row that points to the desktop runs nothing and says where the setup is.
        """
        row = next((row for row in self._rows if row.item_id == item_id), None)
        if row is None or row.recovery is None:
            return
        if row.recovery is DependencyRecoveryAction.SET_UP_IN_DESKTOP:
            self.notify(dependency_desktop_pointer())
        elif row.recovery is DependencyRecoveryAction.CHECK_AGAIN:
            self._read((row.kind,), full=True)
        elif row.recovery in DEPENDENCY_SETUP_RECOVERIES:
            items = (row.kind,)
            resumed = self._approved.get(items) if row.recovery is DependencyRecoveryAction.RESUME else None
            self.start_setup(items, approved=resumed)

    def start_setup(self, items: tuple[DependencyItemKind, ...], *, approved: str | None = None) -> None:
        """Run a setup of ``items``, every item that offers it when empty; the plan is approved in a dialog.

        With ``approved``, the digest of a plan this screen's person approved,
        the setup runs under that approval while the plan is unchanged, and a
        changed plan is shown for a new approval.
        """
        self._setup_stop = ComponentsCancellation()
        self._following = False
        self._set_busy(True)
        self._set_status(tr("tui.setup.working"))
        self.run_worker(self._setup(items, approved, self._setup_stop), group="setup-run", exclusive=True)

    async def _setup(
        self, items: tuple[DependencyItemKind, ...], approved: str | None, cancellation: ComponentsCancellation
    ) -> None:
        loop = asyncio.get_running_loop()
        try:
            result = await self._run_setup(items, approved, cancellation, loop)
            if result.outcome is ComponentsOutcome.PLAN_CHANGED and approved is not None:
                # The plan approved before is not this one: the person sees the new plan.
                result = await self._run_setup(items, None, cancellation, loop)
        except _UNREACHABLE:
            self._setup_stop = None
            self._set_busy(False)
            self._unavailable()
            return
        self._setup_stop = None
        self._set_busy(False)
        self._read()
        self.notify(setup_outcome_text(result, items, followed=self._following))

    async def _run_setup(
        self,
        items: tuple[DependencyItemKind, ...],
        approved: str | None,
        cancellation: ComponentsCancellation,
        loop: asyncio.AbstractEventLoop,
    ) -> ComponentsResultLine:
        def review(line: ComponentsReviewLine) -> ComponentsAnswer:
            answer = self._ask(line, cancellation, loop)
            if isinstance(answer, ComponentsApprove):
                self._approved[items] = answer.plan_digest
            return answer

        return await self._door.set_up(
            items, approved=approved, review=review, on_event=self._relay(loop), cancellation=cancellation
        )

    def _ask(
        self, line: ComponentsReviewLine, cancellation: ComponentsCancellation, loop: asyncio.AbstractEventLoop
    ) -> ComponentsAnswer:
        """Show the plan in a dialog and wait, on the role's thread, for the person's answer to exactly that plan."""
        decided: Future[bool] = Future()

        def answered(approved: bool | None) -> None:
            if not decided.done():
                decided.set_result(approved is True)

        def show() -> None:
            if not self.is_mounted:
                answered(False)
                return
            self.app.push_screen(
                ConfirmScreen(
                    title=lambda: tr("tui.setup.review.title"),
                    message=lambda: setup_review_text(line.plan),
                    confirm_label=lambda: tr("application.provisioning.action.set_up"),
                    cancel_label=lambda: tr("tui.setup.review.decline"),
                ),
                answered,
            )

        try:
            loop.call_soon_threadsafe(show)
        except RuntimeError:
            return ComponentsDecline()
        while True:
            try:
                approved = decided.result(timeout=_ANSWER_POLL_S)
            except TimeoutError:
                if cancellation.requested:
                    return ComponentsDecline()
                continue
            return ComponentsApprove(plan_digest=line.plan_digest) if approved else ComponentsDecline()

    def action_close(self) -> None:
        """Return to whatever opened the screen."""
        self.dismiss(None)


class _LoopRelay:
    """Relays each event the role sends, from its thread, to the screen's event loop without waiting."""

    def __init__(self, loop: asyncio.AbstractEventLoop, show: Callable[[ComponentsEvent], None]) -> None:
        """Bind the loop the screen runs on and the call that shows one event there."""
        self._loop = loop
        self._show = show

    def __call__(self, event: ComponentsEvent) -> None:
        """Hand ``event`` to the screen's loop; an event that arrives once the loop has closed is dropped."""
        try:
            self._loop.call_soon_threadsafe(self._show, event)
        except RuntimeError:
            return
