"""The shared shell of every categorisation tool in the Ledger workspace.

A tool reads through its injected doors off the event loop, stages any change
as a worded summary the operator reviews, and writes only after that summary
is confirmed. A destructive change asks once more through the shared
confirmation dialog. A write in flight cannot be abandoned, and a refusal is
said on the screen in the operator's language rather than raised.

Several tools offer more than one write, so the review step is held here
rather than in the one-shot confirmation flow: each confirmed change settles
and the tool returns to editing, ready for the next one.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass
from typing import ClassVar, override

from pydantic import ValidationError
from textual.app import ComposeResult
from textual.containers import ItemGrid
from textual.widget import Widget
from textual.widgets import Button, Input, Static

from ....core.errors.hierarchy import CadrumoError
from ....core.i18n.render import tr
from ....core.identity.transaction_ids import TransactionId
from ....domain.transactions.enums import BusinessClassification
from ..account import AccountSessionExpiredError
from ..components.dialogs import ConfirmScreen
from ..components.language import localized, repaint_tables
from ..components.theme import tokenised
from .controller import LedgerWorkspaceController, LedgerWorkspaceScreen
from .workspace_presentation import door_refusal_text, ledger_workspace_page

ACTION_MIN_COLUMN_WIDTH = 16
"""Narrowest column an action row lays a button into, so a row wraps rather than overflows."""

type Wording = Callable[[], str]
"""Copy rendered now and again after a language change."""


def line(key: str, /, *, id: str | None = None, classes: str = "") -> Static:
    """A line of authored copy that rewords itself with the operator's language."""
    return localized(Static(tr(key), id=id, classes=classes, markup=False), key)


def heading(key: str, /) -> Static:
    """A section heading in the operator's language."""
    return localized(Static(tr(key), classes="cadrumo-heading", markup=False), key)


def action(key: str, /, *, id: str, primary: bool = False, disabled: bool = False) -> Button:
    """A button whose label rewords itself with the operator's language."""
    return localized(Button(tr(key), id=id, variant="primary" if primary else "default", disabled=disabled), key)


def field(key: str, /, *, id: str, max_length: int = 0) -> Input:
    """A text input whose placeholder names the value it takes."""
    return localized(Input(placeholder=tr(key), id=id, max_length=max_length), key)


def action_row(*buttons: Button, id: str | None = None) -> ItemGrid:
    """Lay buttons out in one row that wraps on a narrow terminal."""
    return ItemGrid(*buttons, id=id, classes="categorisation-actions", min_column_width=ACTION_MIN_COLUMN_WIDTH)


def classification_label(value: str) -> str:
    """Name a business classification in the operator's language, or show an unknown token as it is."""
    try:
        member = BusinessClassification(value.upper())
    except ValueError:
        return value
    return tr(f"tui.ledger.categorisation.classification.{member.value.lower()}")


def short_id(identifier: str) -> str:
    """The short form of an entry identifier the CLI also prints."""
    return identifier[:12]


def page_label(offset: int, shown: int, total: int) -> str:
    """Say which records a page shows out of how many there are."""
    if total == 0:
        return tr("tui.ledger.categorisation.page.empty")
    return tr("tui.ledger.categorisation.page.window", first=offset + 1, last=offset + shown, total=total)


def blank_to_none(value: str) -> str | None:
    """A typed value, or ``None`` when the operator left it blank."""
    stripped = value.strip()
    return stripped or None


@dataclass(frozen=True, slots=True)
class StagedChangeV1:
    """One reviewed change: its wording, the write it stands for and whether it destroys a record."""

    summary: Wording
    write: Callable[[], Awaitable[bool]]
    """Submit the change; ``False`` when the operation refused it with its own findings."""
    destructive: bool = False
    refreshes_workspace: bool = False
    """Whether the write changes entries the workspace shows, so the workspace is read again."""


class CategorisationScreen(LedgerWorkspaceScreen):
    """Review-then-write shell shared by the categorisation tools."""

    ENTRY_SCOPED: ClassVar[bool] = False
    """Whether the tool acts on the entry the operator selected in the workspace."""

    DEFAULT_CSS = tokenised(
        """
        .categorisation-actions { height: auto; margin-bottom: $cadrumo-stack; grid-gutter: 0 $cadrumo-control-gap; }
        .categorisation-actions Button { width: 1fr; }
        #categorisation-staged { height: auto; text-style: bold; }
        #categorisation-outcome { height: auto; }
        #categorisation-entry { height: auto; }
        """
    )

    def __init__(self, controller: LedgerWorkspaceController, *, id: str) -> None:
        """Bind the workspace whose entry, if any, the tool acts on."""
        super().__init__(controller, id=id)
        self.busy = False
        self.staged: StagedChangeV1 | None = None
        self._outcome: Wording | None = None

    @property
    def available(self) -> bool:
        """Whether the tool can work: an entry-scoped tool needs a selected entry."""
        return not self.ENTRY_SCOPED or self.controller.classification_target is not None

    @property
    def target(self) -> TransactionId:
        """The selected entry an entry-scoped tool acts on."""
        target = self.controller.classification_target
        if target is None:
            raise ValueError(tr("tui.ledger.categorisation.choose_entry"))
        return target

    @override
    def compose(self) -> ComposeResult:
        yield self.banner()
        with ledger_workspace_page() as navigation:
            yield navigation
            yield self.prompt()
            if not self.available:
                yield line("tui.ledger.categorisation.choose_entry", id="categorisation-choose-entry")
                yield Static("", id="ledger-flow-status", markup=False)
                yield Static("", id="ledger-refusal", classes="ledger-refusal", markup=False)
                return
            if self.ENTRY_SCOPED:
                yield Static(self._entry_text(), id="categorisation-entry", markup=False)
            yield Static("", id="categorisation-staged", markup=False)
            yield action_row(
                action("tui.ledger.categorisation.confirm", id="categorisation-confirm", primary=True, disabled=True),
                action("tui.ledger.categorisation.cancel", id="categorisation-cancel", disabled=True),
                id="categorisation-decision",
            )
            yield Static("", id="ledger-flow-status", markup=False)
            yield Static("", id="ledger-refusal", classes="ledger-refusal", markup=False)
            yield Static("", id="categorisation-outcome", markup=False)
            yield from self.compose_body()

    def banner(self) -> Static:
        """The tool's title line, built with ``line`` from a literal key so the key is seen as used."""
        raise NotImplementedError

    def prompt(self) -> Static:
        """The tool's one-line explanation, built with ``line`` from a literal key."""
        raise NotImplementedError

    def compose_body(self) -> Iterator[Widget]:
        """Yield the tool's own controls and tables."""
        return iter(())

    def on_mount(self) -> None:
        """Show the navigation, then let an available tool start its own reads."""
        self.populate_navigation()
        if not self.available:
            return
        self._show_staged_controls(staged=False)
        self.paint_tables()
        self.mount_body()

    def mount_body(self) -> None:
        """Start the tool's first reads; called once the controls exist."""

    def paint_tables(self) -> None:
        """Add the columns and rows of the tool's own tables in the current language."""

    @override
    async def refresh_language(self) -> None:
        """Reword copy, tables and the held review and outcome without restarting a read."""
        await super().refresh_language()
        if not self.available:
            return

        def paint() -> None:
            self.populate_navigation()
            self.paint_tables()

        repaint_tables(self, paint)
        if self.ENTRY_SCOPED:
            self.query_one("#categorisation-entry", Static).update(self._entry_text())
        staged = self.staged
        self.query_one("#categorisation-staged", Static).update("" if staged is None else staged.summary())
        outcome = self._outcome
        self.query_one("#categorisation-outcome", Static).update("" if outcome is None else outcome())

    def _entry_text(self) -> str:
        target = self.controller.classification_target
        if target is None:
            return tr("tui.ledger.categorisation.choose_entry")
        return tr("tui.ledger.categorisation.entry", entry=self.controller.entry_label(target))

    # -- Status, refusal and outcome ---------------------------------------

    def status(self, key: str | None) -> None:
        """Say what the tool is doing, or nothing."""
        self.query_one("#ledger-flow-status", Static).update("" if key is None else tr(key))

    def refuse(self, text: str) -> None:
        """Say why the last request was not done."""
        self.query_one("#ledger-refusal", Static).update(text)

    def refuse_error(self, error: CadrumoError | ValueError) -> None:
        """Say why typed values could not become a request, in the operator's language."""
        if isinstance(error, CadrumoError | ValidationError):
            self.refuse(door_refusal_text(error))
        else:
            self.refuse(str(error))

    def show_outcome(self, wording: Wording | None) -> None:
        """Say what the last request found or changed, and keep saying it in a new language."""
        self._outcome = wording
        self.query_one("#categorisation-outcome", Static).update("" if wording is None else wording())

    # -- Staging -------------------------------------------------------------

    def stage(
        self,
        summary: Wording,
        write: Callable[[], Awaitable[bool]],
        *,
        destructive: bool = False,
        refreshes_workspace: bool = False,
    ) -> None:
        """Hold one change for review; nothing is written until it is confirmed."""
        self.staged = StagedChangeV1(
            summary=summary, write=write, destructive=destructive, refreshes_workspace=refreshes_workspace
        )
        self.refuse("")
        self.query_one("#categorisation-staged", Static).update(summary())
        self.status("tui.ledger.categorisation.reviewed")
        self._show_staged_controls(staged=True)
        self.query_one("#categorisation-confirm", Button).focus()

    def unstage(self) -> None:
        """Drop the held change without writing anything."""
        self.staged = None
        self.query_one("#categorisation-staged", Static).update("")
        self._show_staged_controls(staged=False)

    def stage_from(self, build: Callable[[], StagedChangeV1]) -> None:
        """Stage what ``build`` returns, or say why the typed values cannot be staged."""
        try:
            staged = build()
        except (CadrumoError, ValueError) as error:
            self.refuse_error(error)
            return
        self.stage(
            staged.summary,
            staged.write,
            destructive=staged.destructive,
            refreshes_workspace=staged.refreshes_workspace,
        )

    def staged_controls(self) -> tuple[str, ...]:
        """Selectors of the tool's own controls that freeze while a change is staged."""
        return ()

    def _show_staged_controls(self, *, staged: bool) -> None:
        for selector in self.staged_controls():
            self.query_one(selector).disabled = staged
        self.query_one("#categorisation-confirm", Button).disabled = not staged
        self.query_one("#categorisation-cancel", Button).disabled = not staged
        self.query_one("#categorisation-decision", ItemGrid).display = staged

    # -- Running doors -------------------------------------------------------

    def run_read(self, read: Callable[[], Awaitable[None]]) -> None:
        """Run one read through a door off the event loop, unless another request is running."""
        if self.refuse_while_busy():
            return
        self.busy = True
        self.run_worker(self._run(read, writing=False, refreshes=False), exclusive=True, group="categorisation")

    def refuse_while_busy(self) -> bool:
        """Say that a request is already running, and report whether one is."""
        if self.busy:
            self.status("tui.ledger.flow.in_flight_refusal")
        return self.busy

    async def _run(self, request: Callable[[], Awaitable[bool | None]], *, writing: bool, refreshes: bool) -> None:
        self.refuse("")
        self.status("tui.ledger.categorisation.saving" if writing else "tui.ledger.categorisation.loading")
        try:
            written = await request()
        except AccountSessionExpiredError as error:
            self.clear_private_view()
            self.refuse(door_refusal_text(error))
            self.status("tui.ledger.categorisation.failed")
            return
        except CadrumoError as error:
            self.refuse(door_refusal_text(error))
            self.status("tui.ledger.categorisation.failed")
            if writing:
                self._show_staged_controls(staged=self.staged is not None)
            return
        finally:
            self.busy = False
        if not writing:
            self.status(None)
            return
        self.unstage()
        if written is False:
            self.status("tui.ledger.categorisation.not_done")
            return
        self.status("tui.ledger.categorisation.saved")
        if refreshes:
            self.refresh_then(self.after_refresh)

    def after_refresh(self) -> None:
        """Continue once the workspace has been read again after a write."""
        self.status("tui.ledger.categorisation.saved")

    def clear_private_view(self) -> None:
        """Discard every fact the tool shows once the admitted session is lost."""
        self.unstage()
        self.show_outcome(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Answer the review decision; every other button belongs to the tool."""
        button_id = event.button.id or ""
        if button_id == "categorisation-cancel":
            if not self.busy:
                self.unstage()
                self.status("tui.ledger.categorisation.cancelled")
            return
        if button_id == "categorisation-confirm":
            self._confirm()
            return
        if self.refuse_while_busy():
            return
        self.on_tool_button(button_id)

    def on_tool_button(self, button_id: str) -> None:
        """Answer one of the tool's own buttons."""

    def _confirm(self) -> None:
        staged = self.staged
        if staged is None or self.refuse_while_busy():
            return
        if not staged.destructive:
            self._write(staged)
            return

        def decided(confirmed: bool | None) -> None:
            if confirmed is True and self.staged is staged:
                self._write(staged)
            else:
                self.status("tui.ledger.categorisation.not_done")

        self.app.push_screen(
            ConfirmScreen(
                title=lambda: tr("tui.ledger.categorisation.destructive_title"),
                message=staged.summary,
                confirm_label=lambda: tr("tui.ledger.categorisation.destructive_accept"),
                cancel_label=lambda: tr("tui.ledger.categorisation.cancel"),
            ),
            decided,
        )

    def _write(self, staged: StagedChangeV1) -> None:
        self.busy = True
        self.query_one("#categorisation-confirm", Button).disabled = True
        self.query_one("#categorisation-cancel", Button).disabled = True
        self.run_worker(
            self._run(staged.write, writing=True, refreshes=staged.refreshes_workspace),
            exclusive=True,
            group="categorisation",
        )

    @override
    def action_back(self) -> None:
        if self.busy:
            self.status("tui.ledger.flow.in_flight_refusal")
            return
        super().action_back()


__all__ = [
    "ACTION_MIN_COLUMN_WIDTH",
    "CategorisationScreen",
    "StagedChangeV1",
    "Wording",
    "action",
    "action_row",
    "blank_to_none",
    "classification_label",
    "field",
    "heading",
    "line",
    "page_label",
    "short_id",
]
