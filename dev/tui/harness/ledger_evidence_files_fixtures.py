"""Evidence and attachment tool states for reviewing the Records workspace screens.

Each screen is driven through its own controls over a synthetic in-memory
evidence store whose doors return the registered operations' real result
models, so every frame shows what the screens render from a real result.
Every document, supplier and identifier is synthetic; nothing is written to
storage.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path, PurePath
from typing import cast, override

from textual.events import Mount
from textual.screen import Screen
from textual.widgets import DataTable, Input

from cadrumo.entrypoints.tui.components.host import ScreenHostApp
from cadrumo.entrypoints.tui.ledger.controller import LedgerWorkspaceController
from cadrumo.entrypoints.tui.ledger.evidence_files_attachments import LedgerEvidenceFilesAttachmentsScreen
from cadrumo.entrypoints.tui.ledger.evidence_files_batch import LedgerEvidenceFilesBatchScreen
from cadrumo.entrypoints.tui.ledger.evidence_files_consent import LedgerEvidenceFilesConsentScreen
from cadrumo.entrypoints.tui.ledger.evidence_files_queue import LedgerEvidenceFilesQueueScreen
from cadrumo.entrypoints.tui.ledger.evidence_files_records import LedgerEvidenceFilesRecordsScreen
from cadrumo.entrypoints.tui.ledger.evidence_files_review import LedgerEvidenceFilesReviewScreen
from cadrumo.entrypoints.tui.ledger.tests.evidence_files_fixtures import (
    MemoryEvidenceFilesStore,
    synthetic_evidence_id,
    synthetic_review,
)
from cadrumo.entrypoints.tui.ledger.tests.workspace_fixtures import (
    LEDGER_TX_A,
    ledger_context,
    ledger_focused_context,
    ledger_projection,
    ledger_review_action,
)
from cadrumo.entrypoints.tui.ledger.workspace_injection import LedgerWorkspaceInjection
from cadrumo.entrypoints.tui.tests.settling import settle_host, settle_host_until

from .settling import press_when_enabled

_PACKAGE = "cadrumo.entrypoints.tui.ledger"
_WRITE_INTERFACE = f"{_PACKAGE}.evidence_files_write.LedgerEvidenceFilesWriteScreen"


class EvidenceFilesFixtureState(StrEnum):
    """The reviewable states of the evidence and attachment tools."""

    RECORDS = "records"
    RECORD_DETAIL = "record-detail"
    RECORD_CORRECTION = "record-correction"
    RECORD_REMOVAL = "record-removal"
    BATCH_FORM = "batch-form"
    BATCH_PARTIAL = "batch-partial"
    QUEUE_DETAIL = "queue-detail"
    REVIEW_SUMMARY = "review-summary"
    REVIEW_FULL = "review-full"
    CONSENT = "consent"
    ATTACHMENTS_NO_ENTRY = "attachments-no-entry"
    ATTACHMENTS_ENTRY = "attachments-entry"


_INTERFACES: dict[EvidenceFilesFixtureState, str] = {
    EvidenceFilesFixtureState.RECORDS: f"{_PACKAGE}.evidence_files_records.LedgerEvidenceFilesRecordsScreen",
    EvidenceFilesFixtureState.RECORD_DETAIL: f"{_PACKAGE}.evidence_files_records.LedgerEvidenceFilesRecordsScreen",
    EvidenceFilesFixtureState.RECORD_CORRECTION: _WRITE_INTERFACE,
    EvidenceFilesFixtureState.RECORD_REMOVAL: _WRITE_INTERFACE,
    EvidenceFilesFixtureState.BATCH_FORM: f"{_PACKAGE}.evidence_files_batch.LedgerEvidenceFilesBatchScreen",
    EvidenceFilesFixtureState.BATCH_PARTIAL: _WRITE_INTERFACE,
    EvidenceFilesFixtureState.QUEUE_DETAIL: f"{_PACKAGE}.evidence_files_queue.LedgerEvidenceFilesQueueScreen",
    EvidenceFilesFixtureState.REVIEW_SUMMARY: f"{_PACKAGE}.evidence_files_review.LedgerEvidenceFilesReviewScreen",
    EvidenceFilesFixtureState.REVIEW_FULL: f"{_PACKAGE}.evidence_files_review.LedgerEvidenceFilesReviewScreen",
    EvidenceFilesFixtureState.CONSENT: f"{_PACKAGE}.evidence_files_consent.LedgerEvidenceFilesConsentScreen",
    EvidenceFilesFixtureState.ATTACHMENTS_NO_ENTRY: (
        f"{_PACKAGE}.evidence_files_attachments.LedgerEvidenceFilesAttachmentsScreen"
    ),
    EvidenceFilesFixtureState.ATTACHMENTS_ENTRY: (
        f"{_PACKAGE}.evidence_files_attachments.LedgerEvidenceFilesAttachmentsScreen"
    ),
}


def _store() -> MemoryEvidenceFilesStore:
    """Twelve evidence records, five pending attachments, three consent events and one draft."""
    store = MemoryEvidenceFilesStore()
    store.seed_records(12)
    store.seed_attachments(5)
    store.seed_consent(3)
    store.drafts[synthetic_evidence_id(1)] = synthetic_review(synthetic_evidence_id(1))
    store.batch_documents = (
        ("factura-enero.pdf", "ingested"),
        ("factura-febrero.pdf", "no_op"),
        ("factura-marzo.pdf", "refused"),
    )
    store.batch_unreadable = ("factura-abril.pdf",)
    return store


class EvidenceFilesCaptureHost(ScreenHostApp[None]):
    """Drive one evidence tool to a declared, settled review state."""

    def __init__(self, screen: Screen[None], state: EvidenceFilesFixtureState) -> None:
        """Bind the production screen and the state the capture must reach."""
        super().__init__(screen)
        self.fixture_state = state
        self._driving = False
        self._pending: Screen[None] | None = None

    def replace_workspace_body(self, screen: Screen[None], /) -> None:
        """Swap the tool for the write step it opens, as the root shell does.

        While the capture is still driving from this host's own mount handler,
        a deferred swap could not land until that handler returned; the swap is
        held and applied by the driver on this host's pump instead.
        """
        if self._driving:
            self._pending = screen
            return
        self.call_next(self._replace_workspace_body, screen)

    def _replace_workspace_body(self, screen: Screen[None]) -> None:
        while len(self.screen_stack) > 1:
            self.pop_screen()
        self.push_screen(screen, self.exit)

    async def _apply_pending_swap(self) -> None:
        screen, self._pending = self._pending, None
        if screen is None:
            return
        while len(self.screen_stack) > 1:
            await self.pop_screen()
        await self.push_screen(screen, self.exit)
        await self._settle()

    @override
    async def on_mount(self, event: Mount | None = None) -> None:
        # Mounted explicitly before driving, so Textual must not dispatch the
        # inherited handler a second time.
        if event is not None:
            event.prevent_default()
        await super().on_mount()
        await self._settle()
        self._driving = True
        try:
            await self._reach_state()
        finally:
            self._driving = False

    async def _settle(self) -> None:
        """Wait until the screen has handled every posted message and finished every door call."""
        await settle_host(self)

    async def _press(self, button_id: str) -> None:
        await press_when_enabled(self, button_id)
        await self._apply_pending_swap()

    async def _select(self, table_id: str, row: int) -> None:
        table = cast("DataTable[str]", self.screen.query_one(f"#{table_id}", DataTable))
        await settle_host_until(self, lambda: table.row_count > row, f"#{table_id} to show row {row}")
        table.move_cursor(row=row)
        table.action_select_cursor()
        await self._settle()

    async def _reach_state(self) -> None:
        state = self.fixture_state
        if state in {EvidenceFilesFixtureState.RECORD_DETAIL, EvidenceFilesFixtureState.RECORD_CORRECTION}:
            await self._select("evidence-files-records", 1)
            if state is EvidenceFilesFixtureState.RECORD_CORRECTION:
                self.screen.query_one("#evidence-files-field-supplier", Input).value = "Suministros Gamma SL"
                self.screen.query_one("#evidence-files-field-taxable-base", Input).value = "110"
                await self._press("evidence-files-review-update")
        elif state is EvidenceFilesFixtureState.RECORD_REMOVAL:
            await self._select("evidence-files-records", 0)
            await self._press("evidence-files-review-remove")
        elif state is EvidenceFilesFixtureState.BATCH_PARTIAL:
            # An absolute folder on either platform; the synthetic door reads nothing from it.
            self.screen.query_one("#evidence-files-batch-directory", Input).value = str(
                PurePath(Path.cwd().anchor, "facturas")
            )
            await self._press("evidence-files-batch-review")
            await self._press("evidence-files-confirm")
        elif state is EvidenceFilesFixtureState.QUEUE_DETAIL:
            await self._select("evidence-files-queue", 0)
        elif state is EvidenceFilesFixtureState.REVIEW_FULL:
            await self._press("evidence-files-full")


def build_evidence_files_fixture(state: EvidenceFilesFixtureState) -> EvidenceFilesCaptureHost:
    """Open the tool a state belongs to over a synthetic evidence store."""
    store = _store()
    focused = state is EvidenceFilesFixtureState.ATTACHMENTS_ENTRY
    controller = LedgerWorkspaceController(
        ledger_focused_context(LEDGER_TX_A) if focused else ledger_context(),
        ledger_projection(),
        LedgerWorkspaceInjection(review_action=ledger_review_action()),
    )
    doors = store.doors()
    screen: Screen[None]
    match state:
        case (
            EvidenceFilesFixtureState.RECORDS
            | EvidenceFilesFixtureState.RECORD_DETAIL
            | EvidenceFilesFixtureState.RECORD_CORRECTION
            | EvidenceFilesFixtureState.RECORD_REMOVAL
        ):
            screen = LedgerEvidenceFilesRecordsScreen(controller, doors)
        case EvidenceFilesFixtureState.BATCH_FORM | EvidenceFilesFixtureState.BATCH_PARTIAL:
            screen = LedgerEvidenceFilesBatchScreen(controller, doors)
        case EvidenceFilesFixtureState.QUEUE_DETAIL:
            screen = LedgerEvidenceFilesQueueScreen(controller, doors)
        case EvidenceFilesFixtureState.REVIEW_SUMMARY | EvidenceFilesFixtureState.REVIEW_FULL:
            screen = LedgerEvidenceFilesReviewScreen(controller, doors, reference=synthetic_evidence_id(1))
        case EvidenceFilesFixtureState.CONSENT:
            screen = LedgerEvidenceFilesConsentScreen(controller, doors)
        case EvidenceFilesFixtureState.ATTACHMENTS_NO_ENTRY | EvidenceFilesFixtureState.ATTACHMENTS_ENTRY:
            screen = LedgerEvidenceFilesAttachmentsScreen(controller, doors)
    return EvidenceFilesCaptureHost(screen, state)


def evidence_files_fixture_interfaces(state: EvidenceFilesFixtureState) -> tuple[str, ...]:
    """The one interface class a state paints at its opening frame."""
    return (_INTERFACES[state],)


__all__ = [
    "EvidenceFilesCaptureHost",
    "EvidenceFilesFixtureState",
    "build_evidence_files_fixture",
    "evidence_files_fixture_interfaces",
]
