"""Gates for the entry tools: no door runs on the event-loop thread, and every screen fits.

The off-loop gate records, at each door's transport boundary, whether it was
entered on the thread that runs the application's event loop. A runtime door
checks its session with a blocking exchange, so a door entered there would
freeze every key while it waits.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import cast, override

import pytest
from textual.containers import VerticalScroll
from textual.pilot import Pilot
from textual.screen import Screen
from textual.widgets import Button, Collapsible, DataTable, Input, Select

from .....application.ledger.list_operation import LedgerListRequest
from .....core.config import override_settings
from ...components.dialogs import ConfirmScreen
from ...tests.frame import geometry_band
from ..controller import LedgerWorkspaceController, LedgerWorkspaceScreen
from ..entries_add import LedgerEntryAddScreen
from ..entries_browse import LedgerEntriesBrowseScreen
from ..entries_export import LedgerEntriesExportScreen
from ..entries_health import LedgerHealthScreen
from ..entries_reset import LedgerResetScreen
from ..entries_trace import LedgerEntryTraceScreen
from .entries_door_fixtures import (
    ENTRIES_PROFILE_ID,
    MemoryEntriesLedger,
    entries_controller,
    entry_id,
    synthetic_entry,
)
from .test_ledger_selection_journey import _WorkspaceHostApp

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_ALL_DOORS = frozenset(
    {
        "list",
        "add",
        "remove",
        "ledger.archive",
        "ledger.stash",
        "ledger.restore",
        "ledger.exclude",
        "merge",
        "history",
        "history_typed",
        "track",
        "status",
        "check",
        "preflight",
        "reset",
        "export",
    }
)


class _ThreadBoundary(MemoryEntriesLedger):
    """A memory ledger whose doors record whether they were entered on the event-loop thread."""

    def __init__(self, count: int) -> None:
        super().__init__(tuple(synthetic_entry(index) for index in range(count)))
        self.loop_thread = threading.get_ident()
        self.entered: list[tuple[str, bool]] = []

    @override
    def raise_if_configured(self, name: str) -> None:
        self.entered.append((name, threading.get_ident() == self.loop_thread))
        super().raise_if_configured(name)

    @property
    def on_loop(self) -> list[str]:
        return [name for name, on_loop in self.entered if on_loop]

    @property
    def names(self) -> set[str]:
        return {name for name, _ in self.entered}


async def _settle(pilot: Pilot[None]) -> None:
    await pilot.pause()
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()


async def _press(pilot: Pilot[None], screen: Screen[None], button_id: str) -> None:
    screen.query_one(f"#{button_id}", Button).press()
    await _settle(pilot)


async def _accept(pilot: Pilot[None]) -> None:
    dialog = pilot.app.screen
    assert isinstance(dialog, ConfirmScreen)
    dialog.query_one("#btn-confirm-accept", Button).press()
    await _settle(pilot)


async def _choose(pilot: Pilot[None], screen: LedgerEntriesBrowseScreen, row: int) -> None:
    table = screen.query_one("#entries-browse", DataTable)
    table.focus()
    table.move_cursor(row=row)
    await pilot.press("enter")
    await _settle(pilot)


async def _drive_browse(ledger: _ThreadBoundary) -> None:
    screen = LedgerEntriesBrowseScreen(entries_controller(), ledger.doors())
    app = _WorkspaceHostApp(screen)
    async with app.run_test(size=(120, 40)) as pilot:
        await _settle(pilot)
        await _choose(pilot, screen, 0)
        for button_id in ("entries-browse-stash", "entries-browse-restore", "entries-browse-archive"):
            await _press(pilot, screen, button_id)
            await _accept(pilot)
        await _press(pilot, screen, "entries-browse-exclude")
        await _accept(pilot)
        for row in (1, 2):
            await _choose(pilot, screen, row)
            await _press(pilot, screen, "entries-browse-mark")
        await _press(pilot, screen, "entries-browse-merge")
        await _accept(pilot)
        await _choose(pilot, screen, 0)
        await _press(pilot, screen, "entries-browse-remove")
        await _accept(pilot)
        await _choose(pilot, screen, 0)
        await _press(pilot, screen, "entries-browse-trace")
        await _settle(pilot)
        trace = app.screen
        assert isinstance(trace, LedgerEntryTraceScreen)
        await _press(pilot, trace, "entries-trace-full")


async def _drive_forms(ledger: _ThreadBoundary, export_path: str) -> None:
    doors = ledger.doors()
    add = LedgerEntryAddScreen(entries_controller(), doors)
    async with _WorkspaceHostApp(add).run_test(size=(120, 40)) as pilot:
        await _settle(pilot)
        add.query_one("#entries-add-booked-date", Input).value = "2026-03-14"
        add.query_one("#entries-add-amount", Input).value = "10.00"
        add.query_one("#entries-add-description", Input).value = "Synthetic"
        await _press(pilot, add, "entries-add-review")
        await _press(pilot, add, "entries-add-confirm")
    export = LedgerEntriesExportScreen(entries_controller(), doors)
    async with _WorkspaceHostApp(export).run_test(size=(120, 40)) as pilot:
        await _settle(pilot)
        export.query_one("#entries-export-path", Input).value = export_path
        await _press(pilot, export, "entries-export-review")
        await _press(pilot, export, "entries-export-confirm")
    health = LedgerHealthScreen(entries_controller(), doors)
    async with _WorkspaceHostApp(health).run_test(size=(120, 40)) as pilot:
        await _settle(pilot)
        health.query_one("#entries-health-year", Input).value = "2026"
        cast("Select[str]", health.query_one("#entries-health-period", Select)).value = "1T"
        await _press(pilot, health, "entries-health-read")
    reset = LedgerResetScreen(entries_controller(), doors)
    async with _WorkspaceHostApp(reset).run_test(size=(120, 40)) as pilot:
        await _settle(pilot)
        reset.query_one("#entries-reset-reason", Input).value = "synthetic"
        await _press(pilot, reset, "entries-reset-preview-button")
        await _press(pilot, reset, "entries-reset-run")
        await _accept(pilot)


@pytest.mark.asyncio
async def test_every_entry_door_is_entered_off_the_event_loop_thread(tmp_path_factory: pytest.TempPathFactory) -> None:
    ledger = _ThreadBoundary(6)
    export_path = str(tmp_path_factory.mktemp("export") / "ledger.csv")
    with override_settings(cadrumo_output_language="en"):
        await _drive_browse(ledger)
        await _drive_forms(ledger, export_path)
    assert ledger.names == _ALL_DOORS
    assert ledger.on_loop == []


@pytest.mark.asyncio
async def test_the_gate_catches_a_door_entered_on_the_loop() -> None:
    """Detector teeth: awaiting a door directly on the loop is recorded as on the loop."""
    ledger = _ThreadBoundary(1)
    request = LedgerListRequest(profile_id=ENTRIES_PROFILE_ID, limit=10)
    await ledger.doors().list_entries(request)
    assert ledger.on_loop == ["list"]


_SIZES = ((80, 24), (100, 30), (120, 40), (200, 50))
_THEMES = ("cadrumo-dark", "cadrumo-light")


def _browse(controller: LedgerWorkspaceController, ledger: MemoryEntriesLedger) -> LedgerWorkspaceScreen:
    return LedgerEntriesBrowseScreen(controller, ledger.doors())


def _trace(controller: LedgerWorkspaceController, ledger: MemoryEntriesLedger) -> LedgerWorkspaceScreen:
    return LedgerEntryTraceScreen(
        controller,
        ledger.doors(),
        transaction_id=entry_id(0),
        label="2026-01-01 · 100.00 EUR · Synthetic entry 0000",
        back_to=lambda again: LedgerEntriesBrowseScreen(again, ledger.doors()),
    )


def _add(controller: LedgerWorkspaceController, ledger: MemoryEntriesLedger) -> LedgerWorkspaceScreen:
    return LedgerEntryAddScreen(controller, ledger.doors())


def _export(controller: LedgerWorkspaceController, ledger: MemoryEntriesLedger) -> LedgerWorkspaceScreen:
    return LedgerEntriesExportScreen(controller, ledger.doors())


def _health(controller: LedgerWorkspaceController, ledger: MemoryEntriesLedger) -> LedgerWorkspaceScreen:
    return LedgerHealthScreen(controller, ledger.doors())


def _reset(controller: LedgerWorkspaceController, ledger: MemoryEntriesLedger) -> LedgerWorkspaceScreen:
    return LedgerResetScreen(controller, ledger.doors())


async def _fill(pilot: Pilot[None], screen: LedgerWorkspaceScreen) -> None:
    """Bring each screen to its fullest state: findings read, preview shown, optional facts open."""
    if isinstance(screen, LedgerEntryAddScreen):
        screen.query_one("#entries-add-optional", Collapsible).collapsed = False
    elif isinstance(screen, LedgerHealthScreen):
        screen.query_one("#entries-health-year", Input).value = "2026"
        cast("Select[str]", screen.query_one("#entries-health-period", Select)).value = "1T"
        await _press(pilot, screen, "entries-health-read")
    elif isinstance(screen, LedgerResetScreen):
        screen.query_one("#entries-reset-reason", Input).value = "synthetic"
        await _press(pilot, screen, "entries-reset-preview-button")
    elif isinstance(screen, LedgerEntryTraceScreen):
        await _press(pilot, screen, "entries-trace-full")
    await _settle(pilot)


@pytest.mark.asyncio
@pytest.mark.parametrize("theme", _THEMES)
@pytest.mark.parametrize("size", _SIZES)
@pytest.mark.parametrize("build", (_browse, _trace, _add, _export, _health, _reset))
async def test_every_entry_screen_fits_every_supported_terminal(
    build: Callable[[LedgerWorkspaceController, MemoryEntriesLedger], LedgerWorkspaceScreen],
    size: tuple[int, int],
    theme: str,
) -> None:
    ledger = MemoryEntriesLedger.with_entries(1000)
    screen = build(entries_controller(), ledger)
    app = _WorkspaceHostApp(screen)
    with override_settings(cadrumo_output_language="en"):
        async with app.run_test(size=size) as pilot:
            app.theme = theme
            await _settle(pilot)
            await _fill(pilot, screen)
            assert geometry_band(app, size[0]) == []
            assert all(table.max_scroll_x == 0 for table in screen.query(DataTable))
            owners = [w for w in screen.query(VerticalScroll) if w.display and w.show_vertical_scrollbar]
            assert all(owner.id == "ledger-page" for owner in owners)
