"""Gate: a door the TUI calls never runs on the event-loop thread.

Every fake here stands at the transport boundary a real door crosses (storage,
registry, network) and records whether it was entered while an event loop was
running on the calling thread. A door entered there freezes every key and every
repaint for as long as it takes, which is exactly the defect this gate exists
to keep out.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, cast, override

import pytest
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Button, DataTable, Static

from ....application.ledger.attachment_review import AttachmentReviewItem
from ....application.operations.composition import OperationComposedServices
from ....application.overview.next_actions import declare_next_action
from ....application.search.workbench import WorkbenchSearchService
from ...tui.components.host import ScreenHostApp
from ..app import CadrumoTuiApp, RootBindingV1
from ..declarations.calendar import DeclarationsCalendarScreen
from ..declarations.tests.calendar_fixtures import calendar_controller, calendar_projection
from ..home import HomeScreen
from ..ledger.controller import LedgerWorkspaceController
from ..ledger.evidence import LedgerEvidenceScreen
from ..ledger.models import (
    LedgerEvidenceConfirmationV1,
    LedgerEvidenceConfirmedV1,
    LedgerEvidenceDraftV1,
    LedgerEvidenceRecordRowV1,
    LedgerImportOutcomeV1,
    LedgerImportRequestV1,
    LedgerImportSourceKind,
    LedgerReaderReadinessV1,
)
from ..ledger.tests.workspace_fixtures import (
    ledger_context,
    ledger_evidence_action,
    ledger_projection,
    ledger_review_action,
)
from ..ledger.workspace_injection import LedgerWorkspaceInjection
from ..ledger_doors import LedgerImportDoor
from .home_fixtures import HomeFixtureScenario, build_home_projection_fixture
from .test_app import HandoverScreen, _account_factories, _catalogue

if TYPE_CHECKING:
    from ....domain.calculations.registry.authority import PinnedAuthorityOperation

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


class TransportBoundary:
    """Records each entry and whether an event loop was running on that thread."""

    def __init__(self) -> None:
        self.entries: list[tuple[str, bool]] = []

    def enter(self, name: str) -> None:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            on_loop = False
        else:
            on_loop = True
        self.entries.append((name, on_loop))

    @property
    def on_loop(self) -> list[str]:
        return [name for name, on_loop in self.entries if on_loop]

    @property
    def names(self) -> set[str]:
        return {name for name, _on_loop in self.entries}


@pytest.mark.asyncio
async def test_the_root_opens_and_returns_home_without_reading_on_the_loop() -> None:
    boundary = TransportBoundary()

    def refresh_home():
        boundary.enter("refresh_home")
        return build_home_projection_fixture(HomeFixtureScenario.READY)

    def refresh_search():
        boundary.enter("refresh_search")
        return WorkbenchSearchService(())

    def load_root() -> RootBindingV1:
        boundary.enter("load_root")
        return RootBindingV1(
            destination_catalogue=_catalogue([]),
            refresh_home=refresh_home,
            workbench_search_service=WorkbenchSearchService(()),
            refresh_workbench_search=refresh_search,
            refresh_destination_catalogue=None,
            account_factories=_account_factories(HandoverScreen()),
            read_account_session=None,
        )

    app = CadrumoTuiApp(services=cast(OperationComposedServices, object()), load_root=load_root)
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        for _ in range(4):
            await pilot.pause()
        assert isinstance(app.screen, HomeScreen)
        app._show_home(None)
        await app.workers.wait_for_complete()
        app._on_destination_dismissed(None)
        await app.workers.wait_for_complete()
        for _ in range(4):
            await pilot.pause()

    assert boundary.names == {"load_root", "refresh_home", "refresh_search"}
    assert boundary.on_loop == []


class _GuardedEvidenceDoor:
    def __init__(self, boundary: TransportBoundary) -> None:
        self.boundary = boundary

    def list_records(self) -> tuple[LedgerEvidenceRecordRowV1, ...]:
        self.boundary.enter("list_records")
        return ()

    async def add(self, source_path: str) -> LedgerEvidenceRecordRowV1:
        raise AssertionError(f"not exercised: {source_path}")

    def reader_readiness(self) -> LedgerReaderReadinessV1:
        self.boundary.enter("reader_readiness")
        return LedgerReaderReadinessV1(extraction_ready=False, failed_condition_id="provisioning.runtime.reachable")

    async def extract(self, evidence_id: str) -> LedgerEvidenceDraftV1:
        raise AssertionError(f"not exercised: {evidence_id}")

    async def confirm(self, confirmation: LedgerEvidenceConfirmationV1) -> LedgerEvidenceConfirmedV1:
        raise AssertionError(f"not exercised: {confirmation}")


def _evidence_screen(boundary: TransportBoundary) -> LedgerEvidenceScreen:
    items: tuple[AttachmentReviewItem, ...] = ()
    return LedgerEvidenceScreen(
        LedgerWorkspaceController(
            ledger_context(),
            ledger_projection(),
            LedgerWorkspaceInjection(
                review_action=ledger_review_action(),
                evidence_action=ledger_evidence_action(),
                evidence_items=items,
                evidence_door=_GuardedEvidenceDoor(boundary),
            ),
        )
    )


@pytest.mark.asyncio
async def test_the_evidence_area_reads_records_and_the_reader_off_the_loop() -> None:
    boundary = TransportBoundary()
    screen = _evidence_screen(boundary)
    async with ScreenHostApp[None](screen).run_test(size=(100, 40)) as pilot:
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()

    assert boundary.names == {"list_records", "reader_readiness"}
    assert boundary.on_loop == []


class _GuardedImportDoor(LedgerImportDoor):
    """The real door with its synchronous transport step replaced."""

    boundary: TransportBoundary = TransportBoundary()

    @override
    def _run(self, request: LedgerImportRequestV1, *, dry_run: bool) -> LedgerImportOutcomeV1:
        self.boundary.enter("import_run")
        return LedgerImportOutcomeV1(
            source_kind=request.source_kind, dry_run=dry_run, files=1, rows=0, imported=0, skipped=0
        )


@pytest.mark.asyncio
async def test_the_import_door_does_its_reading_and_writing_off_the_loop(tmp_path: Path) -> None:
    boundary = TransportBoundary()
    _GuardedImportDoor.boundary = boundary
    # The overridden transport step never reads the authority.
    door = _GuardedImportDoor(profile_id="synthetic", operation=cast("PinnedAuthorityOperation", object()))
    request = LedgerImportRequestV1(path=tmp_path, source_kind=LedgerImportSourceKind.BANK_STATEMENT)
    await door.preview(request)
    await door.apply(request)
    assert boundary.names == {"import_run"}
    assert boundary.on_loop == []


@pytest.mark.asyncio
async def test_the_calendar_creates_a_declaration_off_the_loop() -> None:
    boundary = TransportBoundary()
    base = calendar_projection()
    recovery_row = base.entries[0].model_copy(
        update={
            "recovery_action": declare_next_action("operator.modelo.work.create", modelo="130", year=2026, period="1T")
        }
    )
    projection = base.model_copy(update={"entries": (recovery_row, *base.entries[1:])})
    screen = DeclarationsCalendarScreen(
        calendar_controller(projection, recovery_handoff=lambda action, row: boundary.enter("create_declaration"))
    )
    async with ScreenHostApp[None](screen).run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        table = screen.query_one("#declarations-calendar-agenda", DataTable)
        table.focus()
        table.move_cursor(row=0)
        await pilot.press("enter")
        await pilot.pause()
        pilot.app.screen.query_one("#btn-confirm-accept", Button).press()
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()

    assert boundary.names == {"create_declaration"}
    assert boundary.on_loop == []


class _BlockingScreen(Screen[None]):
    """A deliberately wrong screen: it reads through its door while mounting."""

    def __init__(self, boundary: TransportBoundary) -> None:
        super().__init__()
        self._boundary = boundary

    @override
    def compose(self) -> ComposeResult:
        yield Static("")

    def on_mount(self) -> None:
        self._boundary.enter("read_on_mount")


@pytest.mark.asyncio
async def test_the_gate_catches_a_door_entered_on_the_loop() -> None:
    """Detector teeth: the same boundary flags a screen that reads while mounting."""
    boundary = TransportBoundary()
    async with ScreenHostApp[None](_BlockingScreen(boundary)).run_test() as pilot:
        await pilot.pause()
    assert boundary.on_loop == ["read_on_mount"]

    moved = TransportBoundary()
    await asyncio.to_thread(moved.enter, "read_in_thread")
    assert moved.on_loop == []
    assert moved.names == {"read_in_thread"}
