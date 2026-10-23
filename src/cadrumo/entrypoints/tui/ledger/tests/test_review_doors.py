"""The Review and Evidence areas read their review queues through the registered review operations.

Each queue is the operation's own answer, read from a Textual worker with its
transport off the event-loop thread, never the workspace projection. Each
area shows a typed refusal on screen, says when its queue is empty, renders one
page of a long queue and pages through it, and fits every reviewed terminal
size in both themes.
"""

from __future__ import annotations

from typing import cast

import pytest
from textual.containers import VerticalScroll
from textual.pilot import Pilot
from textual.widgets import Button, DataTable

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from .....application.ledger.evidence_followup_contracts import LedgerEvidenceReviewListRequest
from .....application.ledger.review_operation import LedgerReviewRequest
from .....application.ledger.workspace import LedgerWorkspaceArea
from .....application.user_profile.access_errors import ProfileAccessRefusedError
from .....core.config import override_settings
from .....core.confirmation_gate import ConfirmationBlockReason, ReviewAdvisoryKind
from .....core.errors.hierarchy import RecordedRegisteredError
from .....core.i18n.render import tr
from ...account import AccountSessionExpiredError
from ...components.host import ScreenHostApp
from ...components.theme import CADRUMO_DARK_THEME_NAME, CADRUMO_LIGHT_THEME_NAME
from ...tests.frame import geometry_band
from ..controller import LedgerWorkspaceController
from ..evidence import LedgerEvidenceScreen
from ..models import LedgerRecordDoorsV1
from ..review import REVIEW_PAGE_SIZE, LedgerReviewScreen
from ..transaction_views import LedgerTransactionDetailScreen
from ..workspace_injection import LedgerWorkspaceInjection
from ..workspace_presentation import door_refusal_text
from .evidence_files_fixtures import EVIDENCE_FILES_REFUSAL_CODE, EVIDENCE_FILES_REFUSAL_KEY, settle, text_of
from .invoices_fixtures import MemoryRecordDoors, ReplacingHostApp
from .invoices_fixtures import transaction_projection as synthetic_transaction
from .review_door_fixtures import (
    MemoryEvidenceReviewListDoor,
    MemoryLedgerReviewDoor,
    synthetic_draft,
    synthetic_review_id,
    synthetic_review_row,
)
from .workspace_fixtures import ledger_context, ledger_evidence_action, ledger_projection, ledger_review_action

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SIZES = ((80, 24), (100, 30), (120, 40), (200, 50))
_THEMES = (CADRUMO_DARK_THEME_NAME, CADRUMO_LIGHT_THEME_NAME)
_EVIDENCE_PAGE = 100


def _review_controller(
    door: MemoryLedgerReviewDoor, *, record_doors: LedgerRecordDoorsV1 | None = None
) -> LedgerWorkspaceController:
    return LedgerWorkspaceController(
        ledger_context(),
        ledger_projection(),
        LedgerWorkspaceInjection(review_action=ledger_review_action(), review_door=door, record_doors=record_doors),
    )


def _evidence_controller(door: MemoryEvidenceReviewListDoor) -> LedgerWorkspaceController:
    return LedgerWorkspaceController(
        ledger_context(),
        ledger_projection(),
        LedgerWorkspaceInjection(
            review_action=ledger_review_action(),
            evidence_action=ledger_evidence_action(),
            evidence_review_door=door,
        ),
    )


def _keys(screen: LedgerReviewScreen | LedgerEvidenceScreen, table_id: str) -> list[str]:
    table = cast("DataTable[str]", screen.query_one(f"#{table_id}", DataTable))
    return [str(row.key.value) for row in table.ordered_rows]


def _read_off_the_loop(door: MemoryLedgerReviewDoor | MemoryEvidenceReviewListDoor) -> None:
    """Every call was made from a worker, and every answer was produced off the loop thread."""
    assert door.in_worker
    assert all(door.in_worker)
    assert door.transport_threads
    assert not set(door.transport_threads) & set(door.loop_threads)


# -- Review area -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_review_area_lists_the_queue_the_review_operation_answers() -> None:
    rows = tuple(synthetic_review_row(index) for index in range(3))
    door = MemoryLedgerReviewDoor(rows)
    screen = LedgerReviewScreen(_review_controller(door))
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            # The operation's queue, not the projection's two review identities.
            assert _keys(screen, "ledger-review") == [row.id for row in rows]
            assert door.requests == [LedgerReviewRequest(profile_id=door.profile_id)]
            table = cast("DataTable[str]", screen.query_one("#ledger-review", DataTable))
            first = [str(cell) for cell in table.get_row(rows[0].id)]
            assert first == [
                tr("tui.ledger.entry_label", date=rows[0].date, description=rows[0].description),
                rows[0].amount,
                tr("tui.ledger.review_status.pending"),
                tr("tui.ledger.review.open"),
            ]
            assert text_of(screen, "#ledger-empty") == ""
            assert text_of(screen, "#ledger-refusal") == ""
            assert text_of(screen, "#ledger-flow-status") == ""
    _read_off_the_loop(door)


@pytest.mark.asyncio
async def test_a_refused_review_read_is_said_on_screen_and_lists_nothing() -> None:
    error = ProfileAccessRefusedError(AccessDenialCode.PROFILE_LOCKED)
    door = MemoryLedgerReviewDoor((synthetic_review_row(1),), refusal=error)
    screen = LedgerReviewScreen(_review_controller(door))
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            assert text_of(screen, "#ledger-refusal") == door_refusal_text(error)
            assert door_refusal_text(error)
            assert text_of(screen, "#ledger-flow-status") == tr("tui.ledger.review.failed")
            assert _keys(screen, "ledger-review") == []
            # A refusal is not an empty queue.
            assert text_of(screen, "#ledger-empty") == ""


@pytest.mark.asyncio
async def test_a_lapsed_session_forgets_the_review_queue() -> None:
    door = MemoryLedgerReviewDoor((synthetic_review_row(1),), refusal=AccountSessionExpiredError())
    screen = LedgerReviewScreen(_review_controller(door))
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            assert text_of(screen, "#ledger-refusal") == door_refusal_text(AccountSessionExpiredError())
            assert screen.rows == ()
            assert _keys(screen, "ledger-review") == []


@pytest.mark.asyncio
async def test_an_empty_review_queue_says_nothing_needs_review() -> None:
    door = MemoryLedgerReviewDoor(())
    screen = LedgerReviewScreen(_review_controller(door))
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            assert _keys(screen, "ledger-review") == []
            assert text_of(screen, "#ledger-empty") == tr("tui.ledger.review.empty")
            assert text_of(screen, "#ledger-refusal") == ""
            assert screen.query_one("#ledger-review-next", Button).disabled


async def _page(pilot: Pilot[None], button_id: str) -> None:
    pilot.app.screen.query_one(f"#{button_id}", Button).press()
    await settle(pilot)


@pytest.mark.asyncio
async def test_a_thousand_review_rows_render_one_page_and_page_forward_and_back() -> None:
    rows = tuple(synthetic_review_row(index) for index in range(1_000))
    door = MemoryLedgerReviewDoor(rows)
    screen = LedgerReviewScreen(_review_controller(door))
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            assert _keys(screen, "ledger-review") == [row.id for row in rows[:REVIEW_PAGE_SIZE]]
            assert screen.query_one("#ledger-review-previous", Button).disabled
            position = text_of(screen, "#ledger-review-position")
            assert position == tr("tui.ledger.review.page.position", first=1, last=REVIEW_PAGE_SIZE, total=1_000)
            await _page(pilot, "ledger-review-next")
            assert _keys(screen, "ledger-review") == [row.id for row in rows[REVIEW_PAGE_SIZE : 2 * REVIEW_PAGE_SIZE]]
            for _ in range(3):
                await _page(pilot, "ledger-review-next")
            assert _keys(screen, "ledger-review") == [row.id for row in rows[4 * REVIEW_PAGE_SIZE :]]
            assert screen.query_one("#ledger-review-next", Button).disabled
            await _page(pilot, "ledger-review-previous")
            assert _keys(screen, "ledger-review") == [
                row.id for row in rows[3 * REVIEW_PAGE_SIZE : 4 * REVIEW_PAGE_SIZE]
            ]
    # One read: paging moves through the held answer and asks the operation nothing more.
    assert len(door.requests) == 1


@pytest.mark.asyncio
async def test_choosing_a_review_row_opens_that_entry() -> None:
    transaction_id = synthetic_review_id(7)
    records = MemoryRecordDoors(transactions=(synthetic_transaction(transaction_id),))
    door = MemoryLedgerReviewDoor((synthetic_review_row(7),))
    screen = LedgerReviewScreen(_review_controller(door, record_doors=cast(LedgerRecordDoorsV1, records)))
    with override_settings(cadrumo_output_language="en"):
        async with ReplacingHostApp(screen).run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            table = screen.query_one("#ledger-review", DataTable)
            table.focus()
            await pilot.press("enter")
            await settle(pilot)
            assert screen.requested_transaction_id == transaction_id
            detail = pilot.app.screen
            assert isinstance(detail, LedgerTransactionDetailScreen)
            assert detail.transaction_id == transaction_id


def test_the_review_area_is_not_offered_without_its_review_door() -> None:
    controller = LedgerWorkspaceController(
        ledger_context(), ledger_projection(), LedgerWorkspaceInjection(review_action=ledger_review_action())
    )
    refusal = controller.refusal_for(LedgerWorkspaceArea.REVIEW)
    assert refusal is not None
    assert refusal.reason_key == "tui.ledger.refusal.submission_unavailable"


# -- Evidence area -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_evidence_area_lists_the_drafts_the_review_list_operation_answers() -> None:
    drafts = (
        synthetic_draft(
            2,
            reasons=(ConfirmationBlockReason.CLOSURE_DISCREPANCY, ConfirmationBlockReason.AMBIGUOUS_IDENTITY),
            advisories=(ReviewAdvisoryKind.COUNTRY_CODE_UNASSIGNED,),
        ),
        synthetic_draft(1),
    )
    door = MemoryEvidenceReviewListDoor(drafts)
    screen = LedgerEvidenceScreen(_evidence_controller(door))
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(120, 50)) as pilot:
            await settle(pilot)
            assert _keys(screen, "ledger-evidence-review-queue") == [f"{1:016x}", f"{2:016x}"]
            assert door.requests == [LedgerEvidenceReviewListRequest(profile_id=door.profile_id)]
            table = cast("DataTable[str]", screen.query_one("#ledger-evidence-review-queue", DataTable))
            assert [str(cell) for cell in table.get_row(f"{2:016x}")] == ["000000000000", "2026-03-14", "2", "1"]
            table.focus()
            table.move_cursor(row=1)
            await pilot.press("enter")
            await settle(pilot)
            detail = text_of(screen, "#ledger-evidence-review-queue-detail")
            assert f"{2:016x}" in detail
            assert tr("tui.ledger.evidence.review_queue.blocking", count=2) in detail
            assert tr("tui.ledger.evidence_files.review.reason.closure_discrepancy") in detail
            assert tr("tui.ledger.evidence_files.review.reason.ambiguous_identity") in detail
            assert tr("tui.ledger.evidence.review_queue.advisories", count=1) in detail
            assert tr("tui.ledger.evidence.review_queue.advisory.country_code_unassigned") in detail
            assert text_of(screen, "#ledger-refusal") == ""
    _read_off_the_loop(door)


@pytest.mark.asyncio
async def test_a_refused_drafts_read_is_said_on_screen_and_lists_nothing() -> None:
    error = RecordedRegisteredError(EVIDENCE_FILES_REFUSAL_CODE, translated_message=EVIDENCE_FILES_REFUSAL_KEY)
    door = MemoryEvidenceReviewListDoor((synthetic_draft(1),), refusal=error)
    screen = LedgerEvidenceScreen(_evidence_controller(door))
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(120, 50)) as pilot:
            await settle(pilot)
            assert text_of(screen, "#ledger-refusal") == door_refusal_text(error)
            assert door_refusal_text(error)
            assert text_of(screen, "#ledger-evidence-review-queue-status") == tr(
                "tui.ledger.evidence.review_queue.failed"
            )
            assert _keys(screen, "ledger-evidence-review-queue") == []


@pytest.mark.asyncio
async def test_a_lapsed_session_forgets_the_drafts_waiting_for_review() -> None:
    door = MemoryEvidenceReviewListDoor((synthetic_draft(1),), refusal=AccountSessionExpiredError())
    screen = LedgerEvidenceScreen(_evidence_controller(door))
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(120, 50)) as pilot:
            await settle(pilot)
            assert text_of(screen, "#ledger-refusal") == door_refusal_text(AccountSessionExpiredError())
            assert screen.review_queue.items == ()
            assert _keys(screen, "ledger-evidence-review-queue") == []


@pytest.mark.asyncio
async def test_no_draft_waiting_for_review_is_said_as_such() -> None:
    door = MemoryEvidenceReviewListDoor(())
    screen = LedgerEvidenceScreen(_evidence_controller(door))
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(120, 50)) as pilot:
            await settle(pilot)
            assert _keys(screen, "ledger-evidence-review-queue") == []
            assert text_of(screen, "#ledger-evidence-review-queue-status") == tr(
                "tui.ledger.evidence.review_queue.empty"
            )
            assert text_of(screen, "#ledger-refusal") == ""


@pytest.mark.asyncio
async def test_a_thousand_drafts_render_one_page_and_page_forward_and_back() -> None:
    drafts = tuple(synthetic_draft(index) for index in range(1_000))
    door = MemoryEvidenceReviewListDoor(drafts)
    screen = LedgerEvidenceScreen(_evidence_controller(door))
    references = [draft.evidence_reference for draft in drafts]
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(120, 50)) as pilot:
            await settle(pilot)
            assert _keys(screen, "ledger-evidence-review-queue") == references[:_EVIDENCE_PAGE]
            await _page(pilot, "ledger-evidence-review-queue-next")
            assert _keys(screen, "ledger-evidence-review-queue") == references[_EVIDENCE_PAGE : 2 * _EVIDENCE_PAGE]
            await _page(pilot, "ledger-evidence-review-queue-previous")
            assert _keys(screen, "ledger-evidence-review-queue") == references[:_EVIDENCE_PAGE]
            assert screen.query_one("#ledger-evidence-review-queue-previous", Button).disabled
    assert len(door.requests) == 1


def test_the_evidence_area_opens_on_the_drafts_door_alone() -> None:
    controller = _evidence_controller(MemoryEvidenceReviewListDoor(()))
    assert controller.refusal_for(LedgerWorkspaceArea.EVIDENCE) is None


# -- Geometry ----------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("theme", _THEMES)
@pytest.mark.parametrize("size", _SIZES)
@pytest.mark.parametrize("area", ["review", "evidence"])
async def test_both_review_areas_fit_without_sideways_or_nested_scrolling(
    area: str, size: tuple[int, int], theme: str
) -> None:
    if area == "review":
        screen: LedgerReviewScreen | LedgerEvidenceScreen = LedgerReviewScreen(
            _review_controller(MemoryLedgerReviewDoor(tuple(synthetic_review_row(index) for index in range(300))))
        )
    else:
        drafts = tuple(
            synthetic_draft(index, reasons=(ConfirmationBlockReason.UNRESOLVED_DIRECTION,)) for index in range(150)
        )
        screen = LedgerEvidenceScreen(_evidence_controller(MemoryEvidenceReviewListDoor(drafts)))
    with override_settings(cadrumo_output_language="es"):
        app = ScreenHostApp[None](screen)
        async with app.run_test(size=size) as pilot:
            app.theme = theme
            await settle(pilot)
            if area == "evidence":
                table = screen.query_one("#ledger-evidence-review-queue", DataTable)
                table.focus()
                await pilot.press("enter")
                await settle(pilot)
                assert text_of(screen, "#ledger-evidence-review-queue-detail")
            assert geometry_band(app, size[0]) == []
            assert [table.id for table in screen.query(DataTable) if table.max_scroll_x != 0] == []
            owners = [
                widget.id
                for widget in screen.query(VerticalScroll)
                if widget.display and widget.show_vertical_scrollbar
            ]
            assert owners in ([], ["ledger-page"])
            assert not screen.show_vertical_scrollbar
