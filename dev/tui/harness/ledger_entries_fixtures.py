"""Records entry tool states for reviewing the shipped Browse, Add, Export, status and Reset screens.

Each screen is driven through its own controls over an in-memory ledger whose
doors answer with the registered operations' own result models, so every
frame shows the review, result and refusal copy the operator sees. Every entry
and amount is synthetic; nothing is written to storage or to disk.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from enum import StrEnum
from pathlib import Path
from typing import cast, override

from textual.events import Mount
from textual.widgets import Button, Collapsible, DataTable, Input, Select

from cadrumo.core.operations import OperationEffect
from cadrumo.entrypoints.tui.components.host import ScreenHostApp
from cadrumo.entrypoints.tui.ledger.controller import LedgerWorkspaceController, LedgerWorkspaceScreen
from cadrumo.entrypoints.tui.ledger.entries_add import LedgerEntryAddScreen
from cadrumo.entrypoints.tui.ledger.entries_browse import LedgerEntriesBrowseScreen
from cadrumo.entrypoints.tui.ledger.entries_export import LedgerEntriesExportScreen
from cadrumo.entrypoints.tui.ledger.entries_health import LedgerHealthScreen
from cadrumo.entrypoints.tui.ledger.entries_reset import LedgerResetScreen
from cadrumo.entrypoints.tui.ledger.entries_trace import LedgerEntryTraceScreen
from cadrumo.entrypoints.tui.ledger.tests.entries_door_fixtures import (
    REFUSED_ADD_AMOUNT,
    MemoryEntriesLedger,
    entries_controller,
    entry_id,
)

_INTERFACES = {
    "browse": "cadrumo.entrypoints.tui.ledger.entries_browse.LedgerEntriesBrowseScreen",
    "trace": "cadrumo.entrypoints.tui.ledger.entries_trace.LedgerEntryTraceScreen",
    "add": "cadrumo.entrypoints.tui.ledger.entries_add.LedgerEntryAddScreen",
    "export": "cadrumo.entrypoints.tui.ledger.entries_export.LedgerEntriesExportScreen",
    "health": "cadrumo.entrypoints.tui.ledger.entries_health.LedgerHealthScreen",
    "reset": "cadrumo.entrypoints.tui.ledger.entries_reset.LedgerResetScreen",
}
#: An absolute destination on the review machine's own root; the export door writes nothing.
_EXPORT_PATH = str(Path(Path.cwd().anchor) / "exports" / "ledger-2026.csv")


class EntriesFixtureState(StrEnum):
    """The reviewable states of the Records entry tools."""

    BROWSE_PAGE = "browse-page"
    BROWSE_SELECTED = "browse-selected"
    BROWSE_ARCHIVE_CONFIRM = "browse-archive-confirm"
    BROWSE_REFUSED = "browse-refused"
    BROWSE_EMPTY = "browse-empty"
    TRACE_TYPED = "trace-typed"
    TRACE_FULL = "trace-full"
    ADD_EMPTY = "add-empty"
    ADD_OPTIONAL = "add-optional"
    ADD_REVIEW = "add-review"
    ADD_CREATED = "add-created"
    ADD_REFUSED = "add-refused"
    EXPORT_REVIEW = "export-review"
    EXPORT_WRITTEN = "export-written"
    EXPORT_PARTIAL = "export-partial"
    HEALTH_READ = "health-read"
    RESET_PREVIEW = "reset-preview"
    RESET_CONFIRM = "reset-confirm"
    RESET_DONE = "reset-done"


def _interface(state: EntriesFixtureState) -> str:
    return _INTERFACES[state.value.split("-", 1)[0]]


class EntriesCaptureHost(ScreenHostApp[None]):
    """Drive one production entry tool to a declared, settled review state."""

    def __init__(self, screen: LedgerWorkspaceScreen, state: EntriesFixtureState) -> None:
        """Bind the production screen and the state the capture must reach."""
        super().__init__(screen)
        self.tool_screen = screen
        self.fixture_state = state

    @override
    async def on_mount(self, event: Mount | None = None) -> None:
        # Mounted explicitly before driving, so Textual must not dispatch the inherited handler again.
        if event is not None:
            event.prevent_default()
        await super().on_mount()
        await self.settle()
        await _STEPS[self.fixture_state](self)

    async def settle(self) -> None:
        """Let posted messages land, then wait for every door call they started."""
        for _ in range(5):
            await asyncio.sleep(0.01)
        await self.workers.wait_for_complete()
        await asyncio.sleep(0.01)

    async def press(self, button_id: str) -> None:
        """Press one control on the tool screen and wait for the work it started."""
        self.tool_screen.query_one(f"#{button_id}", Button).press()
        await self.settle()

    async def accept(self) -> None:
        """Accept the confirmation dialog on top."""
        self.screen.query_one("#btn-confirm-accept", Button).press()
        await self.settle()

    async def choose(self, row: int) -> None:
        """Choose one row of the entry list."""
        table = cast("DataTable[str]", self.tool_screen.query_one("#entries-browse", DataTable))
        table.move_cursor(row=row)
        table.action_select_cursor()
        await self.settle()

    def type(self, values: dict[str, str]) -> None:
        """Type into the named inputs."""
        for selector, value in values.items():
            self.tool_screen.query_one(selector, Input).value = value

    def show(self, selector: str) -> None:
        """Scroll the page so one widget leads the frame."""
        self.tool_screen.query_one(selector).scroll_visible(top=True, animate=False, immediate=True)


async def _nothing(_host: EntriesCaptureHost) -> None:
    return None


async def _browse_selected(host: EntriesCaptureHost) -> None:
    await host.choose(3)
    host.show("#entries-browse-selected")


async def _browse_archive_confirm(host: EntriesCaptureHost) -> None:
    await host.choose(3)
    host.type({"#entries-browse-reason": "Cargo duplicado"})
    await host.press("entries-browse-archive")


async def _browse_refused(host: EntriesCaptureHost) -> None:
    await host.choose(3)
    await host.press("entries-browse-archive")
    await host.accept()
    host.show("#entries-browse-selected")


async def _trace_full(host: EntriesCaptureHost) -> None:
    await host.press("entries-trace-full")


async def _add_optional(host: EntriesCaptureHost) -> None:
    host.tool_screen.query_one("#entries-add-optional", Collapsible).collapsed = False
    await host.settle()


def _required(host: EntriesCaptureHost, amount: str = "121.00") -> None:
    host.type(
        {
            "#entries-add-booked-date": "2026-03-14",
            "#entries-add-amount": amount,
            "#entries-add-description": "Material de oficina",
        }
    )


async def _add_review(host: EntriesCaptureHost) -> None:
    _required(host)
    await host.press("entries-add-review")
    host.show("#entries-add-summary")


async def _add_created(host: EntriesCaptureHost) -> None:
    await _add_review(host)
    await host.press("entries-add-confirm")
    host.show("#entries-add-summary")


async def _add_refused(host: EntriesCaptureHost) -> None:
    _required(host, REFUSED_ADD_AMOUNT)
    await host.press("entries-add-review")
    await host.press("entries-add-confirm")
    host.show("#entries-add-summary")


async def _export_review(host: EntriesCaptureHost) -> None:
    host.type({"#entries-export-path": _EXPORT_PATH, "#entries-export-year": "2026"})
    cast("Select[str]", host.tool_screen.query_one("#entries-export-period", Select)).value = "1T"
    await host.press("entries-export-review")
    host.show("#entries-export-summary")


async def _export_written(host: EntriesCaptureHost) -> None:
    await _export_review(host)
    await host.press("entries-export-confirm")
    host.show("#entries-export-summary")


async def _health_read(host: EntriesCaptureHost) -> None:
    host.type({"#entries-health-year": "2026"})
    cast("Select[str]", host.tool_screen.query_one("#entries-health-period", Select)).value = "1T"
    await host.press("entries-health-read")


async def _reset_preview(host: EntriesCaptureHost) -> None:
    host.type({"#entries-reset-reason": "Volver a importar los extractos"})
    await host.press("entries-reset-preview-button")


async def _reset_confirm(host: EntriesCaptureHost) -> None:
    await _reset_preview(host)
    await host.press("entries-reset-run")


async def _reset_done(host: EntriesCaptureHost) -> None:
    await _reset_confirm(host)
    await host.accept()


_STEPS: dict[EntriesFixtureState, Callable[[EntriesCaptureHost], Awaitable[None]]] = {
    EntriesFixtureState.BROWSE_PAGE: _nothing,
    EntriesFixtureState.BROWSE_SELECTED: _browse_selected,
    EntriesFixtureState.BROWSE_ARCHIVE_CONFIRM: _browse_archive_confirm,
    EntriesFixtureState.BROWSE_REFUSED: _browse_refused,
    EntriesFixtureState.BROWSE_EMPTY: _nothing,
    EntriesFixtureState.TRACE_TYPED: _nothing,
    EntriesFixtureState.TRACE_FULL: _trace_full,
    EntriesFixtureState.ADD_EMPTY: _nothing,
    EntriesFixtureState.ADD_OPTIONAL: _add_optional,
    EntriesFixtureState.ADD_REVIEW: _add_review,
    EntriesFixtureState.ADD_CREATED: _add_created,
    EntriesFixtureState.ADD_REFUSED: _add_refused,
    EntriesFixtureState.EXPORT_REVIEW: _export_review,
    EntriesFixtureState.EXPORT_WRITTEN: _export_written,
    EntriesFixtureState.EXPORT_PARTIAL: _export_written,
    EntriesFixtureState.HEALTH_READ: _health_read,
    EntriesFixtureState.RESET_PREVIEW: _reset_preview,
    EntriesFixtureState.RESET_CONFIRM: _reset_confirm,
    EntriesFixtureState.RESET_DONE: _reset_done,
}


def _ledger(state: EntriesFixtureState) -> MemoryEntriesLedger:
    if state is EntriesFixtureState.BROWSE_EMPTY:
        return MemoryEntriesLedger()
    ledger = MemoryEntriesLedger.with_entries(1000)
    if state is EntriesFixtureState.BROWSE_REFUSED:
        ledger.validation_refusals.add("ledger.archive")
    if state is EntriesFixtureState.EXPORT_PARTIAL:
        ledger.export_effect = OperationEffect.PARTIAL
    return ledger


def _screen(
    controller: LedgerWorkspaceController, ledger: MemoryEntriesLedger, state: EntriesFixtureState
) -> LedgerWorkspaceScreen:
    doors = ledger.doors()
    kind = state.value.split("-", 1)[0]
    if kind == "browse":
        return LedgerEntriesBrowseScreen(controller, doors)
    if kind == "trace":
        return LedgerEntryTraceScreen(
            controller,
            doors,
            transaction_id=entry_id(0),
            label="2026-01-01 · 100.00 EUR · Synthetic entry 0000",
            back_to=lambda again: LedgerEntriesBrowseScreen(again, doors),
        )
    if kind == "add":
        return LedgerEntryAddScreen(controller, doors)
    if kind == "export":
        return LedgerEntriesExportScreen(controller, doors)
    if kind == "health":
        return LedgerHealthScreen(controller, doors)
    return LedgerResetScreen(controller, doors)


def build_entries_fixture(state: EntriesFixtureState) -> EntriesCaptureHost:
    """Open one entry tool over a synthetic in-memory ledger and drive it to ``state``."""
    return EntriesCaptureHost(_screen(entries_controller(), _ledger(state), state), state)


def entries_fixture_interfaces(state: EntriesFixtureState) -> tuple[str, ...]:
    """The production screen each state shows."""
    return (_interface(state),)


__all__ = [
    "EntriesCaptureHost",
    "EntriesFixtureState",
    "build_entries_fixture",
    "entries_fixture_interfaces",
]
