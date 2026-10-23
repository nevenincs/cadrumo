"""Suggested classifications and splits decided in the real operation modal: Apply writes, Reject does not."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from dataclasses import replace
from typing import override

import pytest
from textual.pilot import Pilot
from textual.screen import Screen
from textual.widgets import Button, Static

from cadrumo_client.contracts.contracts import RefusalCode, RefusalError

from .....application.ledger.llm_review_contracts import (
    LEDGER_SPLIT_REVIEW_DEFINITION_ID,
    LedgerLlmReviewProjection,
    LedgerLlmReviewRequest,
)
from .....application.ledger.llm_review_workflow import LlmReviewInvocationOrigin
from .....application.operations.frontend_requests import OperationObservationSuccessV1
from .....core.config import override_settings
from .....core.errors.error_codes import resolve_error_message
from .....core.i18n.render import tr
from .....domain.transactions.enums import BusinessClassification
from ...operations.modal import OperationModal
from ...operations.outcome import OperationOutcomeUnknownError
from ...tests.settling import SETTLE_TIMEOUT_SECONDS, settle, settle_until
from ..categorisation_review import LedgerSuggestionReviewScreen, ReviewingCategorisationScreen, suggestion_text
from ..categorisation_split import LedgerSplitScreen
from ..controller import LedgerWorkspaceController
from ..workspace_injection import LedgerWorkspaceRefreshV1
from .categorisation_fixtures import CATEGORISATION_PROFILE_ID, CATEGORISATION_REFUSAL_KEY
from .categorisation_memory_doors import MemoryCategorisationProfile, categorisation_controller
from .categorisation_pilot import press, review_and_confirm, text, type_into
from .categorisation_review_fixtures import MemoryReviewController, MemoryReviewDoor, suggestion_for
from .workspace_fixtures import LEDGER_TX_A, WorkspaceHostApp

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]


def _modal(pilot: Pilot[None]) -> OperationModal | None:
    """The operation modal, when it is the screen on top."""
    current: object = pilot.app.screen
    return current if isinstance(current, OperationModal) else None


async def _ask(pilot: Pilot[None], screen: Screen[None], button_id: str) -> None:
    """Ask for a review and wait for its modal; the modal's observer runs until the decision, so workers stay unjoined."""
    screen.query_one(f"#{button_id}", Button).press()
    await settle_until(
        pilot,
        lambda: _modal(pilot) is not None,
        f"the review modal to open ({text(screen, '#ledger-refusal')!r} shown)",
        workers=False,
    )


async def _decide(pilot: Pilot[None], button_id: str) -> None:
    """Wait for the modal to offer the decision, then take it."""

    def offered() -> bool:
        modal = _modal(pilot)
        return modal is not None and not modal.query_one(f"#{button_id}", Button).disabled

    await settle_until(pilot, offered, "the modal to offer the decision", workers=False)
    modal = _modal(pilot)
    assert modal is not None
    review = str(modal.query_one("#operation-modal-review", Static).render())
    assert tr("tui.ledger.categorisation.review.suggestion_heading") in review
    modal.query_one(f"#{button_id}", Button).press()
    await settle_until(pilot, lambda: _modal(pilot) is None, "the modal to close after the decision", workers=False)
    await settle(pilot)


def _review_screen(profile: MemoryCategorisationProfile) -> tuple[LedgerSuggestionReviewScreen, MemoryReviewDoor]:
    doors = profile.doors()
    door = doors.classify_review
    return LedgerSuggestionReviewScreen(categorisation_controller(), door=doors.classify_review), door


@pytest.mark.asyncio
async def test_applying_a_suggestion_in_the_modal_writes_it() -> None:
    profile = MemoryCategorisationProfile()
    screen, door = _review_screen(profile)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 50)) as pilot:
            await settle(pilot)
            await _ask(pilot, screen, "categorisation-review-ask")
            request = door.controllers[0].request
            assert request.transaction_id == LEDGER_TX_A
            assert request.origin is LlmReviewInvocationOrigin.CLASSIFY_LLM_APPLY
            assert profile.ledger.entries[LEDGER_TX_A].business_classification != "BUSINESS"
            await _decide(pilot, "btn-operation-apply")
            assert door.results[0].outcome == "classified"
            assert profile.ledger.entries[LEDGER_TX_A].business_classification == BusinessClassification.BUSINESS.value
            assert text(screen, "#categorisation-outcome") == tr(
                "tui.ledger.categorisation.review.classified",
                classification=tr("tui.ledger.categorisation.classification.business"),
            )


@pytest.mark.asyncio
async def test_rejecting_a_suggestion_in_the_modal_writes_nothing() -> None:
    profile = MemoryCategorisationProfile()
    before = profile.ledger.entries[LEDGER_TX_A]
    screen, door = _review_screen(profile)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 50)) as pilot:
            await settle(pilot)
            await _ask(pilot, screen, "categorisation-review-ask")
            await _decide(pilot, "btn-operation-reject")
            assert door.results[0].outcome == "rejected"
            assert profile.ledger.entries[LEDGER_TX_A] == before
            assert text(screen, "#categorisation-outcome") == tr("tui.ledger.categorisation.review.rejected")
            assert text(screen, "#ledger-flow-status") == tr("tui.ledger.categorisation.not_done")


@pytest.mark.asyncio
async def test_a_refused_submission_is_said_and_no_modal_opens() -> None:
    profile = MemoryCategorisationProfile()
    screen, door = _review_screen(profile)
    door.refusing = True
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 50)) as pilot:
            await settle(pilot)
            await press(pilot, screen, "categorisation-review-ask")
            assert _modal(pilot) is None
            assert text(screen, "#ledger-refusal") == tr(CATEGORISATION_REFUSAL_KEY)
            assert not screen.busy


@pytest.mark.asyncio
async def test_a_suggested_split_applied_in_the_modal_is_reported() -> None:
    profile = MemoryCategorisationProfile()
    doors = profile.doors()
    door = doors.split_review
    screen = LedgerSplitScreen(categorisation_controller(), split_door=doors.split, review_door=doors.split_review)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            await _ask(pilot, screen, "categorisation-split-ask")
            assert door.controllers[0].request.mode == "split"
            await _decide(pilot, "btn-operation-apply")
            assert door.results[0].outcome == "split"
            assert text(screen, "#categorisation-outcome") == tr("tui.ledger.categorisation.review.split", count=2)


class _AccessLostAfterDecisionController(MemoryReviewController):
    """A review whose observation is refused once the operator has decided, as a lost runtime connection is."""

    @override
    async def observe(self, after_cursor: int, *, page_limit: int = 256) -> OperationObservationSuccessV1:
        if self.decision is not None:
            raise RefusalError(RefusalCode.CONNECTION_CLOSED)
        return await super().observe(after_cursor, page_limit=page_limit)


class _AccessLostAfterDecisionDoor(MemoryReviewDoor):
    @override
    async def submit(self, request: LedgerLlmReviewRequest) -> MemoryReviewController:
        transaction_id = next(key for key in self.ledger.entries if key.startswith(request.transaction_id))
        controller = _AccessLostAfterDecisionController(request, self.definition_id, transaction_id)
        self.controllers.append(controller)
        return controller


class _HeldRefreshes:
    """Workspace re-reads that each wait for their own release, then fail while ``failures`` last, else return."""

    def __init__(self, *, failures: int = 0) -> None:
        self.failures = failures
        self.started = [threading.Event() for _ in range(3)]
        self.release = [threading.Event() for _ in range(3)]
        self.calls = 0

    def __call__(self) -> LedgerWorkspaceRefreshV1:
        number = self.calls
        self.calls += 1
        self.started[number].set()
        if not self.release[number].wait(timeout=10):
            raise AssertionError(f"workspace re-read {number} was not released")
        if number < self.failures:
            raise RefusalError(RefusalCode.DRAINING)
        return LedgerWorkspaceRefreshV1(projection=categorisation_controller().projection, evidence_items=None)


def _refreshing_controller(refresh: Callable[[], LedgerWorkspaceRefreshV1]) -> LedgerWorkspaceController:
    base = categorisation_controller()
    return LedgerWorkspaceController(base.context, base.projection, replace(base.injection, refresh=refresh))


async def _apply_then_lose_access(
    pilot: Pilot[None], screen: ReviewingCategorisationScreen, ask: str = "categorisation-review-ask"
) -> None:
    """Apply the suggestion, let the modal lose access to the operation, then close it."""
    await _ask(pilot, screen, ask)
    modal = _modal(pilot)
    assert modal is not None
    apply = modal.query_one("#btn-operation-apply", Button)
    await settle_until(pilot, lambda: not apply.disabled, "offering Apply", workers=False)
    apply.press()
    status = modal.query_one("#operation-modal-status", Static)
    lost = tr("operation.modal.status.access_unavailable")
    await settle_until(
        pilot, lambda: str(status.render()) == lost, "losing access to the applied review", workers=False
    )
    modal.query_one("#btn-operation-close", Button).press()
    await settle_until(pilot, lambda: pilot.app.screen is screen, "closing the modal", workers=False)


async def _end_observation(pilot: Pilot[None]) -> None:
    """Reject the open review, whose observation then loses access and ends, so no modal worker outlives the test."""
    modal = _modal(pilot)
    assert modal is not None
    reject = modal.query_one("#btn-operation-reject", Button)
    await settle_until(pilot, lambda: not reject.disabled, "offering Reject", workers=False)
    reject.press()
    status = modal.query_one("#operation-modal-status", Static)
    lost = tr("operation.modal.status.access_unavailable")
    await settle_until(pilot, lambda: str(status.render()) == lost, "ending the review's observation", workers=False)


async def _ask_is_refused(pilot: Pilot[None], screen: LedgerSuggestionReviewScreen, door: MemoryReviewDoor) -> None:
    asked = len(door.controllers)
    # Blanked first, so the line below can only come from the refused request.
    screen.status(None)
    screen.query_one("#categorisation-review-ask", Button).press()
    await settle(pilot, workers=False)
    assert _modal(pilot) is None
    assert not screen.busy
    assert len(door.controllers) == asked
    assert text(screen, "#ledger-flow-status") == tr("tui.ledger.flow.outcome_unknown")


@pytest.mark.asyncio
@pytest.mark.parametrize("fail", [False, True], ids=["reread", "reread-failed"])
async def test_a_review_whose_modal_loses_access_after_apply_is_unknown_until_the_workspace_is_read_again(
    fail: bool,
) -> None:
    profile = MemoryCategorisationProfile()
    door = _AccessLostAfterDecisionDoor(profile.ledger)
    refreshes = _HeldRefreshes(failures=1 if fail else 0)
    screen = LedgerSuggestionReviewScreen(_refreshing_controller(refreshes), door=door)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 50)) as pilot:
            await settle(pilot)
            await _apply_then_lose_access(pilot, screen)

            # The review was applied and then lost from sight: it may have written, so it is unknown.
            unknown = OperationOutcomeUnknownError(operation_id=door.controllers[0].operation_id, effect=None)
            assert text(screen, "#ledger-refusal") == resolve_error_message(unknown)
            assert door.controllers[0].operation_id in text(screen, "#ledger-refusal")
            assert screen.write_outcome_unknown
            assert not screen.in_flight
            assert await asyncio.to_thread(refreshes.started[0].wait, SETTLE_TIMEOUT_SECONDS)
            await _ask_is_refused(pilot, screen, door)

            refreshes.release[0].set()
            await settle(pilot)
            assert refreshes.calls == 1
            assert text(screen, "#ledger-refusal") == resolve_error_message(unknown)
            if fail:
                # Nothing was read after the review: the failed re-read is said, and nothing is offered.
                assert text(screen, "#ledger-flow-status") == tr("tui.ledger.flow.refresh_failed_unknown")
                assert screen.review_awaits_reread
                # Asking again reads the workspace again instead of asking.
                screen.query_one("#categorisation-review-ask", Button).press()
                assert await asyncio.to_thread(refreshes.started[1].wait, SETTLE_TIMEOUT_SECONDS)
                await settle(pilot, workers=False)
                assert _modal(pilot) is None
                assert len(door.controllers) == 1
                assert text(screen, "#ledger-refusal") == resolve_error_message(unknown)
                refreshes.release[1].set()
                await settle(pilot)
                assert refreshes.calls == 2
            assert text(screen, "#ledger-flow-status") == tr("tui.ledger.flow.outcome_unknown")
            assert not screen.review_awaits_reread
            await _ask(pilot, screen, "categorisation-review-ask")
            assert len(door.controllers) == 2
            await _end_observation(pilot)


@pytest.mark.asyncio
async def test_a_reread_started_before_an_unknown_review_does_not_offer_the_review_again() -> None:
    profile = MemoryCategorisationProfile()
    door = _AccessLostAfterDecisionDoor(profile.ledger)
    refreshes = _HeldRefreshes()
    screen = LedgerSuggestionReviewScreen(_refreshing_controller(refreshes), door=door)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 50)) as pilot:
            await settle(pilot)
            # A re-read already out, as one after an earlier write would be.
            screen.refresh_then(lambda: None)
            assert await asyncio.to_thread(refreshes.started[0].wait, SETTLE_TIMEOUT_SECONDS)
            await _apply_then_lose_access(pilot, screen)

            refreshes.release[0].set()
            # That re-read began before the review was applied, so another one is read.
            assert await asyncio.to_thread(refreshes.started[1].wait, SETTLE_TIMEOUT_SECONDS)
            assert screen.review_awaits_reread
            await _ask_is_refused(pilot, screen, door)

            refreshes.release[1].set()
            await settle(pilot)
            assert refreshes.calls == 2
            assert not screen.review_awaits_reread


def _split_screen_losing_access(
    refreshes: _HeldRefreshes,
) -> tuple[LedgerSplitScreen, _AccessLostAfterDecisionDoor, MemoryCategorisationProfile]:
    profile = MemoryCategorisationProfile()
    review_door = _AccessLostAfterDecisionDoor(profile.ledger, definition_id=LEDGER_SPLIT_REVIEW_DEFINITION_ID)
    screen = LedgerSplitScreen(
        _refreshing_controller(refreshes), split_door=profile.doors().split, review_door=review_door
    )
    return screen, review_door, profile


async def _stage_two_halves(pilot: Pilot[None], screen: LedgerSplitScreen) -> None:
    half = f"{screen.parent_amount() / 2:.2f}"
    for description in ("first half", "second half"):
        type_into(screen, "#categorisation-split-amount", half)
        type_into(screen, "#categorisation-split-description", description)
        screen.query_one("#categorisation-split-add", Button).press()
        await settle(pilot, workers=False)
    assert len(screen.children_staged) == 2, text(screen, "#ledger-refusal")


@pytest.mark.asyncio
async def test_a_manual_split_is_not_written_until_an_unknown_suggested_split_is_read_back() -> None:
    refreshes = _HeldRefreshes()
    screen, review_door, profile = _split_screen_losing_access(refreshes)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            await _apply_then_lose_access(pilot, screen, "categorisation-split-ask")
            unknown = OperationOutcomeUnknownError(operation_id=review_door.controllers[0].operation_id, effect=None)
            assert await asyncio.to_thread(refreshes.started[0].wait, SETTLE_TIMEOUT_SECONDS)

            # The suggested split may have been applied: a manual split now could split the entry twice.
            await _stage_two_halves(pilot, screen)
            screen.query_one("#categorisation-split-review", Button).press()
            await settle(pilot, workers=False)
            assert screen.staged is None
            assert text(screen, "#ledger-flow-status") == tr("tui.ledger.flow.outcome_unknown")
            # Neither the refusal nor the staging cleared the unknown review's message and operation.
            assert text(screen, "#ledger-refusal") == resolve_error_message(unknown)

            refreshes.release[0].set()
            await settle_until(
                pilot, lambda: not screen.review_awaits_reread, "reading the workspace back", workers=False
            )
            await settle(pilot)
            assert refreshes.calls == 1
            assert profile.ledger.entries[LEDGER_TX_A].lifecycle_state != "SPLIT"

            # Read back, the manual split is reviewed and written once.
            refreshes.release[1].set()
            await review_and_confirm(pilot, screen, "categorisation-split-review")
            assert profile.ledger.entries[LEDGER_TX_A].lifecycle_state == "SPLIT"
            assert text(screen, "#ledger-flow-status") == tr("tui.ledger.categorisation.saved")


@pytest.mark.asyncio
async def test_a_reread_after_an_unknown_suggested_split_survives_a_refresh_asked_for_meanwhile() -> None:
    refreshes = _HeldRefreshes()
    screen, _review_door, _profile = _split_screen_losing_access(refreshes)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            await _apply_then_lose_access(pilot, screen, "categorisation-split-ask")
            assert await asyncio.to_thread(refreshes.started[0].wait, SETTLE_TIMEOUT_SECONDS)

            # A saved write asks for its own re-read while the one after the unknown review is out.
            screen.refresh_then(screen.after_refresh)
            refreshes.release[0].set()
            await settle_until(
                pilot, lambda: not screen.refreshing and refreshes.calls == 1, "landing the re-read", workers=False
            )
            await settle(pilot)

            # The one read answered both: the write's step ran, and the unknown review was read back.
            assert refreshes.calls == 1
            assert text(screen, "#ledger-flow-status") == tr("tui.ledger.categorisation.saved")
            assert not screen.review_awaits_reread
            await _ask(pilot, screen, "categorisation-split-ask")
            await _end_observation(pilot)


def test_a_suggestion_is_worded_as_a_proposal_with_its_values() -> None:
    with override_settings(cadrumo_output_language="en"):
        request = LedgerLlmReviewRequest(
            profile_id=CATEGORISATION_PROFILE_ID,
            transaction_id=LEDGER_TX_A,
            mode="classification",
            origin=LlmReviewInvocationOrigin.CLASSIFY_LLM_APPLY,
        )
        projection: LedgerLlmReviewProjection = suggestion_for(request, LEDGER_TX_A)
        worded = suggestion_text(projection)
        assert worded.splitlines()[0] == tr("tui.ledger.categorisation.review.suggestion_heading")
        assert (
            tr(
                "tui.ledger.categorisation.review.suggested_classification",
                value=tr("tui.ledger.categorisation.classification.business"),
            )
            in worded
        )
        assert tr("tui.ledger.categorisation.review.suggested_confidence", value="0.82") in worded
        assert worded.splitlines()[-1] == tr("tui.ledger.categorisation.review.decide")
