"""The evidence tools as the workspace lists them, and the event-loop and geometry gates over every screen.

Event loop: each of the twelve doors is reached through its own screen, and the
gate proves the call was made from a Textual worker and its transport crossed
off the event-loop thread. Geometry: every screen fits 80x24 through 200x50 in
both themes, with no table scrolling sideways and only the page scrolling.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import cast, override

import pytest
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.pilot import Pilot
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import DataTable, Input, Static

from .....application.ledger.evidence_read_operation import LedgerEvidenceQueryRequest
from .....application.ledger.workspace import LedgerWorkspaceArea
from .....core.config import override_settings
from ...components.host import ScreenHostApp
from ...components.theme import CADRUMO_DARK_THEME_NAME, CADRUMO_LIGHT_THEME_NAME
from ...tests.frame import geometry_band
from ..controller import LedgerWorkspaceController
from ..entries import LedgerEntriesScreen
from ..evidence import LedgerEvidenceScreen
from ..evidence_files_attachments import LedgerEvidenceFilesAttachmentsScreen
from ..evidence_files_batch import LedgerEvidenceFilesBatchScreen
from ..evidence_files_consent import LedgerEvidenceFilesConsentScreen
from ..evidence_files_queue import LedgerEvidenceFilesQueueScreen
from ..evidence_files_records import LedgerEvidenceFilesRecordsScreen
from ..evidence_files_review import LedgerEvidenceFilesReviewScreen
from ..evidence_files_tools import evidence_files_tools
from ..evidence_files_write import LedgerEvidenceFilesWriteScreen
from ..routes import resolve_ledger_screen
from ..workspace_injection import LedgerWorkspaceInjection
from .evidence_files_fixtures import MemoryEvidenceFilesStore, press, settle, synthetic_evidence_id, synthetic_review
from .test_ledger_selection_journey import _WorkspaceHostApp
from .workspace_fixtures import (
    LEDGER_TX_A,
    LEDGER_TX_B,
    ledger_context,
    ledger_evidence_action,
    ledger_focused_context,
    ledger_projection,
    ledger_review_action,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_DOOR_NAMES = (
    "query",
    "view",
    "update",
    "remove",
    "batch",
    "attachment_queue",
    "attachment_view",
    "consent_list",
    "review_view",
    "review_summary",
    "attach",
    "detach",
)


def _controller(store: MemoryEvidenceFilesStore, *, focused: bool = False) -> LedgerWorkspaceController:
    return LedgerWorkspaceController(
        ledger_focused_context(LEDGER_TX_A) if focused else ledger_context(),
        ledger_projection(),
        LedgerWorkspaceInjection(
            review_action=ledger_review_action(),
            evidence_action=ledger_evidence_action(),
            evidence_items=(),
            tools=evidence_files_tools(store.doors()),
        ),
    )


def _tool_keys(screen: Widget) -> list[str]:
    table = cast("DataTable[str]", screen.query_one("#ledger-tools", DataTable))
    return [str(row.key.value) for row in table.ordered_rows]


async def _open_tool(pilot: Pilot[None], row: int) -> None:
    tools = cast("DataTable[str]", pilot.app.screen.query_one("#ledger-tools", DataTable))
    tools.focus()
    tools.move_cursor(row=row)
    await pilot.press("enter")
    await settle(pilot)


def test_the_six_tools_attach_to_evidence_and_entries_under_their_own_keys() -> None:
    tools = evidence_files_tools(MemoryEvidenceFilesStore().doors())
    assert [(tool.key, tool.area) for tool in tools] == [
        ("ledger.tool.evidence_files.records", LedgerWorkspaceArea.EVIDENCE),
        ("ledger.tool.evidence_files.batch", LedgerWorkspaceArea.EVIDENCE),
        ("ledger.tool.evidence_files.queue", LedgerWorkspaceArea.EVIDENCE),
        ("ledger.tool.evidence_files.review", LedgerWorkspaceArea.EVIDENCE),
        ("ledger.tool.evidence_files.consent", LedgerWorkspaceArea.EVIDENCE),
        ("ledger.tool.evidence_files.attachments", LedgerWorkspaceArea.ENTRIES),
    ]
    assert len({tool.label_key for tool in tools}) == len(tools)


@pytest.mark.asyncio
async def test_the_evidence_area_lists_its_tools_opens_one_and_back_returns_to_the_area() -> None:
    store = MemoryEvidenceFilesStore()
    store.seed_records(2)
    with override_settings(cadrumo_output_language="en"):
        async with _WorkspaceHostApp(LedgerEvidenceScreen(_controller(store))).run_test(size=(120, 50)) as pilot:
            await settle(pilot)
            assert _tool_keys(pilot.app.screen) == [
                "ledger.tool.evidence_files.records",
                "ledger.tool.evidence_files.batch",
                "ledger.tool.evidence_files.queue",
                "ledger.tool.evidence_files.review",
                "ledger.tool.evidence_files.consent",
            ]
            await _open_tool(pilot, 0)
            opened = pilot.app.screen
            assert isinstance(opened, LedgerEvidenceFilesRecordsScreen)
            assert opened.back_area is LedgerWorkspaceArea.EVIDENCE
            assert store.requests_of(LedgerEvidenceQueryRequest)
            await pilot.press("escape")
            await settle(pilot)
            assert isinstance(pilot.app.screen, LedgerEvidenceScreen)


@pytest.mark.asyncio
async def test_attachments_open_from_entries_for_the_entry_just_selected() -> None:
    store = MemoryEvidenceFilesStore()
    controller = _controller(store)
    entries = resolve_ledger_screen(controller, controller.route_target(LedgerWorkspaceArea.ENTRIES))
    assert isinstance(entries, LedgerEntriesScreen)
    with override_settings(cadrumo_output_language="en"):
        async with _WorkspaceHostApp(entries).run_test(size=(120, 50)) as pilot:
            await settle(pilot)
            assert _tool_keys(entries) == ["ledger.tool.evidence_files.attachments"]
            table = cast("DataTable[str]", entries.query_one("#ledger-entries", DataTable))
            table.focus()
            table.move_cursor(row=1)
            await pilot.press("enter")
            await settle(pilot)
            await _open_tool(pilot, 0)
            opened = pilot.app.screen
            assert isinstance(opened, LedgerEvidenceFilesAttachmentsScreen)
            assert opened.target == LEDGER_TX_B
            assert opened.back_area is LedgerWorkspaceArea.ENTRIES


# Event loop: one case per door, each reached through its own screen.

type _Drive = Callable[[Pilot[None], MemoryEvidenceFilesStore], Awaitable[None]]


async def _select_first(pilot: Pilot[None], table_id: str) -> None:
    table = cast("DataTable[str]", pilot.app.screen.query_one(f"#{table_id}", DataTable))
    table.focus()
    table.move_cursor(row=0)
    await pilot.press("enter")
    await settle(pilot)


async def _records(pilot: Pilot[None], _store: MemoryEvidenceFilesStore) -> None:
    await settle(pilot)


async def _view(pilot: Pilot[None], store: MemoryEvidenceFilesStore) -> None:
    await _records(pilot, store)
    await _select_first(pilot, "evidence-files-records")


async def _update(pilot: Pilot[None], store: MemoryEvidenceFilesStore) -> None:
    await _view(pilot, store)
    pilot.app.screen.query_one("#evidence-files-field-notes", Input).value = "Revisada"
    await press(pilot, "evidence-files-review-update")
    await press(pilot, "evidence-files-confirm")


async def _remove(pilot: Pilot[None], store: MemoryEvidenceFilesStore) -> None:
    await _view(pilot, store)
    await press(pilot, "evidence-files-review-remove")
    await press(pilot, "evidence-files-confirm")
    await press(pilot, "btn-confirm-accept")


async def _batch(pilot: Pilot[None], _store: MemoryEvidenceFilesStore) -> None:
    pilot.app.screen.query_one("#evidence-files-batch-directory", Input).value = str(Path.cwd())
    await press(pilot, "evidence-files-batch-review")
    await press(pilot, "evidence-files-confirm")


async def _queue_view(pilot: Pilot[None], _store: MemoryEvidenceFilesStore) -> None:
    await settle(pilot)
    await _select_first(pilot, "evidence-files-queue")


async def _review_full(pilot: Pilot[None], _store: MemoryEvidenceFilesStore) -> None:
    await settle(pilot)
    await press(pilot, "evidence-files-full")


async def _attach(pilot: Pilot[None], store: MemoryEvidenceFilesStore) -> None:
    await settle(pilot)
    pilot.app.screen.query_one("#evidence-files-attach-ids", Input).value = sorted(store.attachments)[0]
    await press(pilot, "evidence-files-review-attach")
    await press(pilot, "evidence-files-confirm")


async def _detach(pilot: Pilot[None], store: MemoryEvidenceFilesStore) -> None:
    await settle(pilot)
    pilot.app.screen.query_one("#evidence-files-detach-ids", Input).value = store.transactions[LEDGER_TX_A][0]
    await press(pilot, "evidence-files-review-detach")
    await press(pilot, "evidence-files-confirm")
    await press(pilot, "btn-confirm-accept")


def _seeded() -> MemoryEvidenceFilesStore:
    store = MemoryEvidenceFilesStore()
    store.seed_records(2)
    store.seed_attachments(2)
    store.seed_consent(1)
    store.batch_documents = (("factura-a.pdf", "ingested"),)
    store.drafts[synthetic_evidence_id(1)] = synthetic_review(synthetic_evidence_id(1))
    store.transactions[LEDGER_TX_A] = (sorted(store.attachments)[1],)
    return store


_SCREENS: dict[str, Callable[[LedgerWorkspaceController, MemoryEvidenceFilesStore], Screen[None]]] = {
    "records": lambda controller, store: LedgerEvidenceFilesRecordsScreen(controller, store.doors()),
    "batch": lambda controller, store: LedgerEvidenceFilesBatchScreen(controller, store.doors()),
    "queue": lambda controller, store: LedgerEvidenceFilesQueueScreen(controller, store.doors()),
    "consent": lambda controller, store: LedgerEvidenceFilesConsentScreen(controller, store.doors()),
    "review": lambda controller, store: LedgerEvidenceFilesReviewScreen(
        controller, store.doors(), reference=synthetic_evidence_id(1)
    ),
    "attachments": lambda controller, store: LedgerEvidenceFilesAttachmentsScreen(controller, store.doors()),
}

_DRIVES: dict[str, tuple[str, _Drive]] = {
    "query": ("records", _records),
    "view": ("records", _view),
    "update": ("records", _update),
    "remove": ("records", _remove),
    "batch": ("batch", _batch),
    "attachment_queue": ("queue", _records),
    "attachment_view": ("queue", _queue_view),
    "consent_list": ("consent", _records),
    "review_summary": ("review", _records),
    "review_view": ("review", _review_full),
    "attach": ("attachments", _attach),
    "detach": ("attachments", _detach),
}


def test_every_door_has_an_event_loop_case() -> None:
    assert set(_DRIVES) == set(_DOOR_NAMES)


@pytest.mark.parametrize("door", _DOOR_NAMES)
@pytest.mark.asyncio
async def test_each_door_is_called_from_a_worker_and_crosses_off_the_event_loop(door: str) -> None:
    store = _seeded()
    screen_name, drive = _DRIVES[door]
    screen = _SCREENS[screen_name](_controller(store, focused=True), store)
    with override_settings(cadrumo_output_language="en"):
        async with _WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await drive(pilot, store)
    assert door in {name for name, _in_worker in store.calls}
    assert [name for name, in_worker in store.calls if not in_worker] == []
    assert [name for name, on_loop in store.transports if on_loop] == []


class _InlineCallScreen(Screen[None]):
    """A deliberately wrong screen: it starts a door call as a bare task, not a worker."""

    def __init__(self, store: MemoryEvidenceFilesStore) -> None:
        super().__init__()
        self._store = store
        self.pending_call: asyncio.Task[object] | None = None

    @override
    def compose(self) -> ComposeResult:
        yield Static("")

    def on_mount(self) -> None:
        doors = self._store.doors()
        self.pending_call = asyncio.ensure_future(doors.query(LedgerEvidenceQueryRequest(profile_id=doors.profile_id)))


@pytest.mark.asyncio
async def test_the_gate_catches_a_door_called_outside_a_worker() -> None:
    """Detector teeth: the same store flags a call that no worker made."""
    store = MemoryEvidenceFilesStore()
    screen = _InlineCallScreen(store)
    async with ScreenHostApp[None](screen).run_test() as pilot:
        await pilot.pause()
        assert screen.pending_call is not None
        await screen.pending_call
    assert store.calls == [("query", False)]


# Geometry: every screen at every reviewed size, in both themes.

_SIZES = ((80, 24), (100, 30), (120, 40), (200, 50))
_THEMES = (CADRUMO_DARK_THEME_NAME, CADRUMO_LIGHT_THEME_NAME)


async def _write_with_outcome(pilot: Pilot[None], _store: MemoryEvidenceFilesStore) -> None:
    await _batch(pilot, _store)
    assert isinstance(pilot.app.screen, LedgerEvidenceFilesWriteScreen)


_GEOMETRY: dict[str, tuple[str, _Drive]] = {
    "records": ("records", _view),
    "batch": ("batch", _records),
    "write": ("batch", _write_with_outcome),
    "queue": ("queue", _queue_view),
    "consent": ("consent", _records),
    "review": ("review", _review_full),
    "attachments": ("attachments", _records),
}


@pytest.mark.parametrize("theme", _THEMES)
@pytest.mark.parametrize("size", _SIZES)
@pytest.mark.parametrize("surface", tuple(_GEOMETRY))
@pytest.mark.asyncio
async def test_every_evidence_screen_fits_without_sideways_or_nested_scrolling(
    surface: str, size: tuple[int, int], theme: str
) -> None:
    store = _seeded()
    screen_name, drive = _GEOMETRY[surface]
    screen = _SCREENS[screen_name](_controller(store, focused=True), store)
    with override_settings(cadrumo_output_language="en"):
        app = _WorkspaceHostApp(screen)
        async with app.run_test(size=size) as pilot:
            app.theme = theme
            await drive(pilot, store)
            await settle(pilot)
            shown = app.screen
            assert geometry_band(app, size[0]) == []
            assert [table.id for table in shown.query(DataTable) if table.max_scroll_x != 0] == []
            owners = [
                widget.id for widget in shown.query(VerticalScroll) if widget.display and widget.show_vertical_scrollbar
            ]
            assert owners in ([], ["ledger-page"])
