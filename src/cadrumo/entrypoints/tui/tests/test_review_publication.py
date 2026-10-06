"""Real Textual dialogs disclose the remote destination and retained publication state."""

import pytest
from textual.app import App
from textual.widgets import Input, Link, Static

from ....application.export.publication_receipt import PublicationFailure, PublicationState
from ...tests.review_publication_fixture import (
    frontend_authorization,
    frontend_created_publication,
    frontend_publication,
    frontend_published_publication,
    frontend_review_label,
    frontend_review_snapshot,
)
from ..components.widgets import ContentDataTable
from ..review_publication import ReviewPublicationOfferScreen, ReviewPublicationResultScreen

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.asyncio
async def test_a_provisional_review_offer_has_no_local_output_path_and_can_be_published() -> None:
    snapshot = frontend_review_snapshot()
    screen = ReviewPublicationOfferScreen(
        snapshot, frontend_authorization(frontend_publication(snapshot)), label=frontend_review_label
    )
    app: App[None] = App()
    choices: list[bool | None] = []
    async with app.run_test(size=(120, 45)) as pilot:
        app.push_screen(screen, choices.append)
        await pilot.pause()
        table = screen.query_one("#review-publication-table", ContentDataTable)
        values = {str(key.value): str(table.get_row(key)[1]) for key in table.rows}
        assert values["review_status"] == "google_review.status.provisional"
        assert values["destination"] == "google_review.destination.managed_google_folder"
        assert not screen.query(Input)
        assert "calculation_revision_id" not in values
        await pilot.click("#review-publication-publish")
        await pilot.pause()
    assert choices == [True]


@pytest.mark.asyncio
async def test_escape_cancels_a_standalone_ledger_offer() -> None:
    snapshot = frontend_review_snapshot(ledger_only=True)
    screen = ReviewPublicationOfferScreen(
        snapshot, frontend_authorization(frontend_publication(snapshot)), label=frontend_review_label
    )
    app: App[None] = App()
    choices: list[bool | None] = []
    async with app.run_test(size=(120, 45)) as pilot:
        app.push_screen(screen, choices.append)
        await pilot.pause()
        table = screen.query_one("#review-publication-table", ContentDataTable)
        assert table.get_row("selection")[1] == "google_review.selection.ledger"
        await pilot.press("escape")
        await pilot.pause()
    assert choices == [False]


@pytest.mark.asyncio
async def test_result_shows_the_known_link_and_uncertainty_without_a_retry_action() -> None:
    snapshot = frontend_review_snapshot()
    receipt = frontend_created_publication(snapshot).advance(
        PublicationState.UNCERTAIN, failure=PublicationFailure.POPULATION
    )
    screen = ReviewPublicationResultScreen(snapshot, receipt, label=frontend_review_label)
    app: App[None] = App()
    async with app.run_test(size=(120, 45)) as pilot:
        app.push_screen(screen)
        await pilot.pause()
        assert screen.query_one(Link).url == "https://docs.google.com/spreadsheets/d/saved-review/edit"
        notice_text = "\n".join(
            str(item.content) for item in screen.query_one("#review-publication-notices").query(Static)
        )
        assert "google_review.publication.uncertain" in notice_text
        assert "google_review.failure.population" in notice_text
        assert not screen.query("#review-publication-publish")
        await pilot.press("t")
        await pilot.pause()
        table = screen.query_one("#review-publication-table", ContentDataTable)
        assert table.get_row("calculation_revision_id")[1] == "c" * 64


@pytest.mark.asyncio
async def test_published_result_retains_draft_and_missing_evidence_notices() -> None:
    snapshot = frontend_review_snapshot()
    screen = ReviewPublicationResultScreen(
        snapshot, frontend_published_publication(snapshot), label=frontend_review_label
    )
    app: App[None] = App()
    async with app.run_test(size=(120, 45)) as pilot:
        app.push_screen(screen)
        await pilot.pause()
        table = screen.query_one("#review-publication-table", ContentDataTable)
        assert table.get_row("publication_state")[1] == "google_review.publication.published"
        assert table.get_row("review_status")[1] == "google_review.status.provisional"
        notice_text = "\n".join(
            str(item.content) for item in screen.query_one("#review-publication-notices").query(Static)
        )
        assert "google_review.notice.missing_evidence" in notice_text
        assert "google_review.notice.provisional" in notice_text
