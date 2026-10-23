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
from textual.widget import Widget
from textual.widgets import Button, Static

from cadrumo_client.contracts.contracts import RefusalCode, RefusalError

from .....application.ledger.llm_review_contracts import LedgerLlmReviewProjection, LedgerLlmReviewRequest
from .....application.ledger.llm_review_workflow import LlmReviewInvocationOrigin
from .....application.operations.frontend_requests import OperationObservationSuccessV1
from .....core.config import override_settings
from .....core.errors.error_codes import resolve_error_message
from .....core.i18n.render import tr
from .....domain.transactions.enums import BusinessClassification
from ...operations.modal import OperationModal
from ...operations.outcome import OperationOutcomeUnknownError
from ..categorisation_review import LedgerSuggestionReviewScreen, suggestion_text
from ..categorisation_split import LedgerSplitScreen
from ..controller import LedgerWorkspaceController
from ..workspace_injection import LedgerWorkspaceRefreshV1
from .categorisation_fixtures import CATEGORISATION_PROFILE_ID, CATEGORISATION_REFUSAL_KEY
from .categorisation_memory_doors import LEDGER_TX_A, MemoryCategorisationProfile, categorisation_controller
from .categorisation_pilot import press, settle, text
from .categorisation_review_fixtures import MemoryReviewController, MemoryReviewDoor, suggestion_for
from .test_ledger_selection_journey import _WorkspaceHostApp

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]


def _modal(pilot: Pilot[None]) -> OperationModal | None:
    """The operation modal, when it is the screen on top."""
    current: object = pilot.app.screen
    return current if isinstance(current, OperationModal) else None


async def _ask(pilot: Pilot[None], screen: Screen[None], button_id: str) -> None:
    """Ask for a review and wait for its modal; the modal's observer runs until the decision, so no settle."""
    screen.query_one(f"#{button_id}", Button).press()
    for _ in range(100):
        await pilot.pause()
        if _modal(pilot) is not None:
            return
    raise AssertionError(f"no review modal opened: {text(screen, '#ledger-refusal')}")


async def _decide(pilot: Pilot[None], button_id: str) -> None:
    """Wait for the modal to offer the decision, then take it."""
    for _ in range(50):
        await pilot.pause()
        modal = _modal(pilot)
        if modal is not None and not modal.query_one(f"#{button_id}", Button).disabled:
            break
    modal = _modal(pilot)
    assert modal is not None
    review = str(modal.query_one("#operation-modal-review", Static).render())
    assert tr("tui.ledger.categorisation.review.suggestion_heading") in review
    modal.query_one(f"#{button_id}", Button).press()
    for _ in range(50):
        await pilot.pause()
        if _modal(pilot) is None:
            break
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
        async with _WorkspaceHostApp(screen).run_test(size=(120, 50)) as pilot:
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
        async with _WorkspaceHostApp(screen).run_test(size=(120, 50)) as pilot:
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
        async with _WorkspaceHostApp(screen).run_test(size=(120, 50)) as pilot:
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
        async with _WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
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
    """Workspace re-reads that each wait for their own release, then return the workspace or fail."""

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.started = [threading.Event() for _ in range(3)]
        self.release = [threading.Event() for _ in range(3)]
        self.calls = 0

    def __call__(self) -> LedgerWorkspaceRefreshV1:
        number = self.calls
        self.calls += 1
        self.started[number].set()
        if not self.release[number].wait(timeout=10):
            raise AssertionError(f"workspace re-read {number} was not released")
        if self.fail:
            raise RefusalError(RefusalCode.DRAINING)
        return LedgerWorkspaceRefreshV1(projection=categorisation_controller().projection, evidence_items=None)


def _refreshing_controller(refresh: Callable[[], LedgerWorkspaceRefreshV1]) -> LedgerWorkspaceController:
    base = categorisation_controller()
    return LedgerWorkspaceController(base.context, base.projection, replace(base.injection, refresh=refresh))


async def _until(pilot: Pilot[None], condition: Callable[[], bool], what: str) -> None:
    """Pause until ``condition`` holds; a loaded machine can need many pauses, so only time bounds the wait."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + 10
    while not condition():
        if loop.time() > deadline:
            raise AssertionError(f"{what} did not happen")
        await pilot.pause()


async def _handled(pilot: Pilot[None]) -> None:
    """Return once every posted message is handled, a pressed button's bubbling ``Pressed`` included."""

    def drained() -> bool:
        screen = pilot.app.screen
        return all(pump.message_queue_size == 0 for pump in (pilot.app, screen, *screen.walk_children(Widget)))

    await pilot.pause()
    await _until(pilot, drained, "handling every posted message")


async def _apply_then_lose_access(pilot: Pilot[None], screen: LedgerSuggestionReviewScreen) -> None:
    """Apply the suggestion, let the modal lose access to the operation, then close it."""
    await _ask(pilot, screen, "categorisation-review-ask")
    modal = _modal(pilot)
    assert modal is not None
    apply = modal.query_one("#btn-operation-apply", Button)
    await _until(pilot, lambda: not apply.disabled, "offering Apply")
    apply.press()
    status = modal.query_one("#operation-modal-status", Static)
    lost = tr("operation.modal.status.access_unavailable")
    await _until(pilot, lambda: str(status.render()) == lost, "losing access to the applied review")
    modal.query_one("#btn-operation-close", Button).press()
    await _until(pilot, lambda: pilot.app.screen is screen, "closing the modal")


async def _ask_is_refused(pilot: Pilot[None], screen: LedgerSuggestionReviewScreen, door: MemoryReviewDoor) -> None:
    asked = len(door.controllers)
    # Blanked first, so the line below can only come from the refused request.
    screen.status(None)
    screen.query_one("#categorisation-review-ask", Button).press()
    await _handled(pilot)
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
    refreshes = _HeldRefreshes(fail=fail)
    screen = LedgerSuggestionReviewScreen(_refreshing_controller(refreshes), door=door)
    with override_settings(cadrumo_output_language="en"):
        async with _WorkspaceHostApp(screen).run_test(size=(120, 50)) as pilot:
            await settle(pilot)
            await _apply_then_lose_access(pilot, screen)

            # The review was applied and then lost from sight: it may have written, so it is unknown.
            unknown = OperationOutcomeUnknownError(operation_id=door.controllers[0].operation_id, effect=None)
            assert text(screen, "#ledger-refusal") == resolve_error_message(unknown)
            assert door.controllers[0].operation_id in text(screen, "#ledger-refusal")
            assert screen.write_outcome_unknown
            assert not screen.in_flight
            assert await asyncio.to_thread(refreshes.started[0].wait, 10)
            await _ask_is_refused(pilot, screen, door)

            refreshes.release[0].set()
            await settle(pilot)
            assert refreshes.calls == 1
            assert text(screen, "#ledger-flow-status") == tr("tui.ledger.flow.outcome_unknown")
            assert text(screen, "#ledger-refusal") == resolve_error_message(unknown)
            if fail:
                # Nothing was read after the review, so it is still not offered again.
                assert screen.review_awaits_reread
                await _ask_is_refused(pilot, screen, door)
            else:
                assert not screen.review_awaits_reread
                await _ask(pilot, screen, "categorisation-review-ask")
                assert len(door.controllers) == 2


@pytest.mark.asyncio
async def test_a_reread_started_before_an_unknown_review_does_not_offer_the_review_again() -> None:
    profile = MemoryCategorisationProfile()
    door = _AccessLostAfterDecisionDoor(profile.ledger)
    refreshes = _HeldRefreshes()
    screen = LedgerSuggestionReviewScreen(_refreshing_controller(refreshes), door=door)
    with override_settings(cadrumo_output_language="en"):
        async with _WorkspaceHostApp(screen).run_test(size=(120, 50)) as pilot:
            await settle(pilot)
            # A re-read already out, as one after an earlier write would be.
            screen.refresh_then(lambda: None)
            assert await asyncio.to_thread(refreshes.started[0].wait, 10)
            await _apply_then_lose_access(pilot, screen)

            refreshes.release[0].set()
            # That re-read began before the review was applied, so another one is read.
            assert await asyncio.to_thread(refreshes.started[1].wait, 10)
            assert screen.review_awaits_reread
            await _ask_is_refused(pilot, screen, door)

            refreshes.release[1].set()
            await settle(pilot)
            assert refreshes.calls == 2
            assert not screen.review_awaits_reread


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
