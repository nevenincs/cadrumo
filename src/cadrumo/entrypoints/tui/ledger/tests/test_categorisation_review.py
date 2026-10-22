"""Suggested classifications and splits decided in the real operation modal: Apply writes, Reject does not."""

from __future__ import annotations

import pytest
from textual.pilot import Pilot
from textual.screen import Screen
from textual.widgets import Button, Static

from .....application.ledger.llm_review_contracts import LedgerLlmReviewProjection, LedgerLlmReviewRequest
from .....application.ledger.llm_review_workflow import LlmReviewInvocationOrigin
from .....core.config import override_settings
from .....core.i18n.render import tr
from .....domain.transactions.enums import BusinessClassification
from ...operations.modal import OperationModal
from ..categorisation_review import LedgerSuggestionReviewScreen, suggestion_text
from ..categorisation_split import LedgerSplitScreen
from .categorisation_fixtures import CATEGORISATION_PROFILE_ID, CATEGORISATION_REFUSAL_KEY
from .categorisation_memory_doors import LEDGER_TX_A, MemoryCategorisationProfile, categorisation_controller
from .categorisation_pilot import press, settle, text
from .categorisation_review_fixtures import MemoryReviewDoor, suggestion_for
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
