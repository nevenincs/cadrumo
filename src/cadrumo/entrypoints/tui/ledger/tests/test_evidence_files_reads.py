"""The read-only evidence tools: attachment queue, evidence review and consent history."""

from __future__ import annotations

import pytest
from textual.pilot import Pilot
from textual.widgets import Button, DataTable, Input

from .....application.ledger.evidence_followup_contracts import (
    LedgerEvidenceAttachmentViewRequest,
    LedgerEvidenceReviewViewRequest,
)
from .....core.config import override_settings
from .....core.i18n.render import tr
from ...tests.settling import settle
from ..controller import LedgerWorkspaceController
from ..evidence_files_consent import LedgerEvidenceFilesConsentScreen
from ..evidence_files_doors import LEDGER_EVIDENCE_FILES_PAGE_SIZE
from ..evidence_files_queue import LedgerEvidenceFilesQueueScreen, attachment_detail_lines
from ..evidence_files_review import LedgerEvidenceFilesReviewScreen, summary_lines, view_lines
from ..workspace_injection import LedgerWorkspaceInjection
from .evidence_files_fixtures import (
    EVIDENCE_FILES_REFUSAL_KEY,
    MemoryEvidenceFilesStore,
    press,
    synthetic_attachment,
    synthetic_evidence_id,
    synthetic_review,
    text_of,
)
from .workspace_fixtures import WorkspaceHostApp, ledger_context, ledger_projection, ledger_review_action

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _controller() -> LedgerWorkspaceController:
    return LedgerWorkspaceController(
        ledger_context(), ledger_projection(), LedgerWorkspaceInjection(review_action=ledger_review_action())
    )


def _table(pilot: Pilot[None], table_id: str) -> DataTable[str]:
    return pilot.app.screen.query_one(f"#{table_id}", DataTable)


def _keys(pilot: Pilot[None], table_id: str) -> list[str]:
    return [str(row.key.value) for row in _table(pilot, table_id).ordered_rows]


async def _select(pilot: Pilot[None], table_id: str, row: int) -> None:
    table = _table(pilot, table_id)
    table.focus()
    table.move_cursor(row=row)
    await pilot.press("enter")
    await settle(pilot)


@pytest.mark.asyncio
async def test_the_attachment_queue_lists_pending_attachments_and_shows_one_manifest() -> None:
    store = MemoryEvidenceFilesStore()
    store.seed_attachments(3)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(LedgerEvidenceFilesQueueScreen(_controller(), store.doors())).run_test(
            size=(120, 50)
        ) as pilot:
            await settle(pilot)
            assert _keys(pilot, "evidence-files-queue") == sorted(store.attachments)
            await _select(pilot, "evidence-files-queue", 1)
            chosen = sorted(store.attachments)[1]
            [request] = store.requests_of(LedgerEvidenceAttachmentViewRequest)
            assert request.attachment_id == chosen
            assert text_of(pilot.app.screen, "#evidence-files-queue-detail") == "\n".join(
                attachment_detail_lines(store.attachments[chosen])
            )


@pytest.mark.asyncio
async def test_an_empty_queue_says_so_and_a_refused_read_is_shown() -> None:
    store = MemoryEvidenceFilesStore()
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(LedgerEvidenceFilesQueueScreen(_controller(), store.doors())).run_test(
            size=(120, 50)
        ) as pilot:
            await settle(pilot)
            assert text_of(pilot.app.screen, "#ledger-flow-status") == tr("tui.ledger.evidence_files.queue.empty")
    refused = MemoryEvidenceFilesStore()
    refused.refusing.add("attachment_queue")
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(LedgerEvidenceFilesQueueScreen(_controller(), refused.doors())).run_test(
            size=(120, 50)
        ) as pilot:
            await settle(pilot)
            assert text_of(pilot.app.screen, "#ledger-refusal") == tr(EVIDENCE_FILES_REFUSAL_KEY)


@pytest.mark.asyncio
async def test_a_thousand_queued_attachments_render_one_page_at_a_time() -> None:
    store = MemoryEvidenceFilesStore()
    store.seed_attachments(1_000)
    ordered = sorted(store.attachments)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(LedgerEvidenceFilesQueueScreen(_controller(), store.doors())).run_test(
            size=(120, 50)
        ) as pilot:
            await settle(pilot)
            assert _keys(pilot, "evidence-files-queue") == ordered[:LEDGER_EVIDENCE_FILES_PAGE_SIZE]
            await press(pilot, "evidence-files-queue-next")
            assert (
                _keys(pilot, "evidence-files-queue")
                == ordered[LEDGER_EVIDENCE_FILES_PAGE_SIZE : 2 * LEDGER_EVIDENCE_FILES_PAGE_SIZE]
            )
            await press(pilot, "evidence-files-queue-previous")
            assert _keys(pilot, "evidence-files-queue") == ordered[:LEDGER_EVIDENCE_FILES_PAGE_SIZE]
            assert pilot.app.screen.query_one("#evidence-files-queue-previous", Button).disabled


@pytest.mark.asyncio
async def test_the_review_reads_a_summary_and_the_full_review_of_one_reference() -> None:
    store = MemoryEvidenceFilesStore()
    reference = synthetic_evidence_id(1)
    store.drafts[reference] = synthetic_review(reference)
    with override_settings(cadrumo_output_language="en"):
        screen = LedgerEvidenceFilesReviewScreen(_controller(), store.doors(), reference=reference)
        async with WorkspaceHostApp(screen).run_test(size=(120, 50)) as pilot:
            await settle(pilot)
            [request] = store.requests_of(LedgerEvidenceReviewViewRequest)
            assert request.evidence_reference == reference
            expected_summary = summary_lines(store.review_summary(request))
            assert screen.shown_lines == expected_summary
            assert tr("tui.ledger.evidence_files.review.text_withheld") in expected_summary
            # The summary never carries the document's own text.
            assert all("Suministros Delta SL" not in line for line in screen.shown_lines)

            await press(pilot, "evidence-files-full")
            assert screen.shown_lines == view_lines(store.drafts[reference])
            assert any("Suministros Delta SL" in line for line in screen.shown_lines)


@pytest.mark.asyncio
async def test_the_review_needs_a_reference_and_shows_a_typed_refusal() -> None:
    store = MemoryEvidenceFilesStore()
    store.refusing.add("review_summary")
    with override_settings(cadrumo_output_language="en"):
        screen = LedgerEvidenceFilesReviewScreen(_controller(), store.doors())
        async with WorkspaceHostApp(screen).run_test(size=(120, 50)) as pilot:
            await settle(pilot)
            await press(pilot, "evidence-files-summary")
            assert text_of(screen, "#ledger-refusal") == tr("tui.ledger.evidence_files.review.reference_required")
            assert store.requests == []
            screen.query_one("#evidence-files-reference", Input).value = synthetic_evidence_id(9)
            await press(pilot, "evidence-files-summary")
            assert text_of(screen, "#ledger-refusal") == tr(EVIDENCE_FILES_REFUSAL_KEY)
            assert screen.shown_lines == ()


@pytest.mark.asyncio
async def test_consent_history_lists_the_synthetic_events_read_only() -> None:
    store = MemoryEvidenceFilesStore()
    store.seed_consent(2)
    with override_settings(cadrumo_output_language="en"):
        screen = LedgerEvidenceFilesConsentScreen(_controller(), store.doors())
        async with WorkspaceHostApp(screen).run_test(size=(120, 50)) as pilot:
            await settle(pilot)
            dispatches = _table(pilot, "evidence-files-dispatches")
            assert dispatches.row_count == 2
            assert list(dispatches.get_row_at(0)) == [
                "2026-03-14 10:30",
                store.dispatches[0].evidence_content_address[:12],
                "provider-a",
                "model-a",
                "invoice-extraction",
            ]
            assert _table(pilot, "evidence-files-artefacts").row_count == 2
            assert tr("tui.ledger.evidence_files.consent.unrecallable") in text_of(
                screen, "#evidence-files-consent-statement"
            )
            # Read-only: the only controls are page moves, and nothing but the survey was read.
            assert {button.id for button in screen.query(Button)} == {
                "evidence-files-dispatches-previous",
                "evidence-files-dispatches-next",
                "evidence-files-artefacts-previous",
                "evidence-files-artefacts-next",
            }
            assert {type(request).__name__ for request in store.requests} == {"LedgerEvidenceConsentListRequest"}


@pytest.mark.asyncio
async def test_an_empty_consent_history_says_nothing_was_sent_and_a_refusal_is_shown() -> None:
    store = MemoryEvidenceFilesStore()
    with override_settings(cadrumo_output_language="en"):
        screen = LedgerEvidenceFilesConsentScreen(_controller(), store.doors())
        async with WorkspaceHostApp(screen).run_test(size=(120, 50)) as pilot:
            await settle(pilot)
            statement = text_of(screen, "#evidence-files-consent-statement")
            assert tr("tui.ledger.evidence_files.consent.no_dispatches") in statement
            assert tr("tui.ledger.evidence_files.consent.no_artefacts") in statement
    refused = MemoryEvidenceFilesStore()
    refused.refusing.add("consent_list")
    with override_settings(cadrumo_output_language="en"):
        screen = LedgerEvidenceFilesConsentScreen(_controller(), refused.doors())
        async with WorkspaceHostApp(screen).run_test(size=(120, 50)) as pilot:
            await settle(pilot)
            assert text_of(screen, "#ledger-refusal") == tr(EVIDENCE_FILES_REFUSAL_KEY)
            assert text_of(screen, "#evidence-files-consent-statement") == ""


@pytest.mark.asyncio
async def test_a_thousand_consent_events_render_one_page_at_a_time() -> None:
    store = MemoryEvidenceFilesStore()
    store.seed_consent(1_000)
    with override_settings(cadrumo_output_language="en"):
        screen = LedgerEvidenceFilesConsentScreen(_controller(), store.doors())
        async with WorkspaceHostApp(screen).run_test(size=(120, 50)) as pilot:
            await settle(pilot)
            assert _table(pilot, "evidence-files-dispatches").row_count == LEDGER_EVIDENCE_FILES_PAGE_SIZE
            assert _table(pilot, "evidence-files-artefacts").row_count == LEDGER_EVIDENCE_FILES_PAGE_SIZE
            for _ in range(10):
                if screen.query_one("#evidence-files-dispatches-next", Button).disabled:
                    break
                await press(pilot, "evidence-files-dispatches-next")
            assert screen.dispatches.offset == 1_000 - LEDGER_EVIDENCE_FILES_PAGE_SIZE
            assert _table(pilot, "evidence-files-dispatches").row_count == LEDGER_EVIDENCE_FILES_PAGE_SIZE
            assert screen.artefacts.offset == 0


def test_attachment_detail_never_names_where_an_attachment_was_fetched_from() -> None:
    item = synthetic_attachment(1).model_copy(update={"provider_locator": "drive:synthetic-folder"})
    assert all("synthetic-folder" not in line for line in attachment_detail_lines(item))
