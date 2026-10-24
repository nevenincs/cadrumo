"""A read the local AI could not do offers its setup on the Evidence screen and on the evidence review.

An extraction refused through the Evidence door arrives as the error the runtime
door raises from the operation's recorded detail: the reader refusal the real
reader probe gives against a closed runtime port, carried through the public
error detail and restored with its verdict. A full review whose label reading
stood without the local AI carries the same probe's verdict on its fallback.
Either offer reads the local AI's quick-status row the way the TUI root reads
it: an absent row's action sets the item up, so the offer opens the setup page
on it; a row this build cannot set up shows its own sentence and offers nothing;
a status without the row offers nothing. A refusal or a review that names no
setup reads no row. The screens run under Textual's pilot.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from textual.pilot import Pilot
from textual.widgets import Button, DataTable, Static

from .....application.dependency_contracts import DependencyStatusRow
from .....application.ledger.attachment_review import AttachmentReviewItem
from .....application.ledger.evidence_errors import (
    EVIDENCE_LOCAL_AI_NOT_READY_KEY,
    PurchaseInvoiceEvidenceReaderError,
    evidence_reader_refusal_key,
)
from .....application.ledger.invoice_draft_records import LabelReadingFallbackCause
from .....application.ledger.invoice_evidence_operation_dtos import LabelReadingFallbackProjectionV1
from .....application.ledger.preconditions import LedgerPreconditionCondition, ledger_no_recovery_verdict
from .....application.local_reader import probe_local_reader
from .....application.operations.error_detail import build_operation_error_detail
from .....application.operator_actions.models import PreconditionVerdict
from .....application.provisioning_contracts import LOCAL_AI_PROVISION_ACTION_ID
from .....core.config import Settings, override_settings
from .....core.errors.hierarchy import CadrumoError
from .....core.i18n.render import tr
from .....core.model_catalogue import ModelRole
from ...setup.offer import SetupItemOffer
from ...tests.settling import settle, settle_until
from ..controller import LedgerWorkspaceController
from ..evidence import LedgerEvidenceScreen
from ..evidence_files_review import LedgerEvidenceFilesReviewScreen
from ..models import (
    LedgerEvidenceConfirmationV1,
    LedgerEvidenceConfirmedV1,
    LedgerEvidenceDraftV1,
    LedgerEvidenceRecordRowV1,
    LedgerEvidenceRecordStatus,
    LedgerReaderReadinessV1,
)
from ..workspace_injection import LedgerWorkspaceInjection, LedgerWorkspaceRefreshV1
from .evidence_files_fixtures import MemoryEvidenceFilesStore, press, synthetic_evidence_id, synthetic_review
from .setup_status_fixtures import LOCAL_AI_HELD, SetupStatusWorkspaceHostApp, absent_row, not_in_this_build_row
from .workspace_fixtures import (
    ledger_context,
    ledger_evidence_action,
    ledger_projection,
    ledger_review_action,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_EVIDENCE_ID = "8747cbf318cf0adb"
#: A runtime port nothing listens on, so the reader probe finds no local AI answering.
_CLOSED_ENDPOINT = "http://127.0.0.1:1/api/chat"


def _probe_verdict() -> PreconditionVerdict:
    """The verdict the real reader probe gives for a local AI that does not answer."""
    status = probe_local_reader(ModelRole.TEXT_EXTRACTION, Settings(cadrumo_llm_ollama_chat_url=_CLOSED_ENDPOINT))
    verdict = status.precondition_verdict
    assert verdict is not None
    assert verdict.action is not None
    assert verdict.action.action_id == LOCAL_AI_PROVISION_ACTION_ID
    return verdict


def _recorded_refusal(verdict: PreconditionVerdict) -> CadrumoError:
    """The reader refusal as a frontend in another process receives it: through its recorded detail."""
    refusal = PurchaseInvoiceEvidenceReaderError(
        translated_message=evidence_reader_refusal_key(verdict), precondition_verdict=verdict
    )
    detail = build_operation_error_detail(refusal)
    assert detail is not None
    recorded = detail.recorded_error()
    assert recorded is not None
    return recorded


def _local_ai_refusal() -> CadrumoError:
    return _recorded_refusal(_probe_verdict())


def _unrecoverable_refusal() -> CadrumoError:
    """A reader refusal setup cannot end: its verdict names no action."""
    return _recorded_refusal(
        ledger_no_recovery_verdict(
            LedgerPreconditionCondition.EVIDENCE_READER_AVAILABLE,
            facts={"semantic_reader_available": False, "reader_error_type": "ConnectionError"},
        )
    )


class _RefusingEvidenceDoor:
    """One stored document whose reading the runtime refuses with ``refusal``."""

    def __init__(self, refusal: CadrumoError) -> None:
        self.refusal = refusal
        self.extracted: list[str] = []

    def list_records(self) -> tuple[LedgerEvidenceRecordRowV1, ...]:
        return (
            LedgerEvidenceRecordRowV1(
                evidence_id=_EVIDENCE_ID,
                media_kind="pdf",
                file_name="invoice_A-0004.pdf",
                supplier=None,
                invoice_number=None,
                created_at="2026-09-16",
                status=LedgerEvidenceRecordStatus.AWAITING,
            ),
        )

    async def add(self, source_path: str) -> LedgerEvidenceRecordRowV1:
        raise AssertionError("nothing is added")

    def reader_readiness(self) -> LedgerReaderReadinessV1:
        return LedgerReaderReadinessV1(extraction_ready=False, failed_condition_id="provisioning.runtime.reachable")

    async def extract(self, evidence_id: str) -> LedgerEvidenceDraftV1:
        self.extracted.append(evidence_id)
        raise self.refusal

    async def confirm(self, confirmation: LedgerEvidenceConfirmationV1) -> LedgerEvidenceConfirmedV1:
        return LedgerEvidenceConfirmedV1(
            invoice_id="c" * 64,
            invoice_number="A-0004",
            grand_total=Decimal("72.60"),
            currency="EUR",
            created=True,
            printed_total_disagrees=False,
        )


def _evidence_screen(door: _RefusingEvidenceDoor) -> LedgerEvidenceScreen:
    projection = ledger_projection()
    items: tuple[AttachmentReviewItem, ...] = ()
    return LedgerEvidenceScreen(
        LedgerWorkspaceController(
            ledger_context(),
            projection,
            LedgerWorkspaceInjection(
                review_action=ledger_review_action(),
                evidence_action=ledger_evidence_action(),
                evidence_items=items,
                evidence_door=door,
                refresh=lambda: LedgerWorkspaceRefreshV1(projection=projection, evidence_items=()),
            ),
        )
    )


async def _read_refused(pilot: Pilot[None], screen: LedgerEvidenceScreen, door: _RefusingEvidenceDoor) -> None:
    records = screen.query_one("#ledger-evidence-records", DataTable)
    await settle_until(pilot, lambda: bool(records.ordered_rows), "the evidence rows")
    records.focus()
    records.move_cursor(row=0)
    await pilot.press("enter")
    await settle(pilot)
    screen.query_one("#ledger-evidence-extract", Button).press()
    await settle_until(pilot, lambda: door.extracted == [_EVIDENCE_ID], "the document to be read")
    await settle_until(pilot, lambda: not screen.reading, "the refused read to settle")


async def _refused_read(
    refusal: CadrumoError, rows: tuple[DependencyStatusRow, ...]
) -> tuple[SetupStatusWorkspaceHostApp, str, bool, str, str | None]:
    """Read the document, see the refusal and the offer beside it, and press the offer when it is a button."""
    door = _RefusingEvidenceDoor(refusal)
    screen = _evidence_screen(door)
    host = SetupStatusWorkspaceHostApp(screen, rows=rows)
    with override_settings(cadrumo_output_language="en"):
        async with host.run_test(size=(100, 70)) as pilot:
            await settle(pilot)
            await _read_refused(pilot, screen, door)
            refused = str(screen.query_one("#ledger-refusal", Static).render())
            offer = screen.query_one("#ledger-evidence-setup", SetupItemOffer)
            shown = offer.display
            text = str(offer.query_one(Static).render())
            button = offer.query_one(Button)
            label = str(button.label) if shown and button.display else None
            if label is not None:
                button.press()
                await settle(pilot)
    return host, refused, shown, text, label


@pytest.mark.asyncio
async def test_a_read_refused_for_the_local_ai_offers_its_setup_beside_the_refusal() -> None:
    host, refused, shown, _text, label = await _refused_read(_local_ai_refusal(), (absent_row("local_ai"),))

    with override_settings(cadrumo_output_language="en"):
        assert refused == tr(EVIDENCE_LOCAL_AI_NOT_READY_KEY)
    assert shown
    assert label == "Set up: Local AI"
    assert host.row_reads == ["local_ai"]
    assert host.requested == ["local_ai"]


@pytest.mark.asyncio
async def test_a_read_refused_for_a_local_ai_this_build_cannot_set_up_shows_its_sentence_and_offers_nothing() -> None:
    host, _refused, shown, text, label = await _refused_read(_local_ai_refusal(), (not_in_this_build_row("local_ai"),))

    assert shown
    assert label is None
    assert text == LOCAL_AI_HELD
    assert host.row_reads == ["local_ai"]
    assert host.requested == []


@pytest.mark.asyncio
async def test_a_read_refused_while_the_setup_status_cannot_be_read_offers_nothing() -> None:
    host, refused, shown, _text, label = await _refused_read(_local_ai_refusal(), ())

    with override_settings(cadrumo_output_language="en"):
        assert refused == tr(EVIDENCE_LOCAL_AI_NOT_READY_KEY)
    assert not shown
    assert label is None
    assert host.row_reads == ["local_ai"]
    assert host.requested == []


@pytest.mark.asyncio
async def test_a_read_refused_for_a_reason_setup_cannot_end_offers_nothing_and_reads_no_row() -> None:
    host, refused, shown, _text, label = await _refused_read(_unrecoverable_refusal(), (absent_row("local_ai"),))

    assert refused
    assert not shown
    assert label is None
    assert host.row_reads == []
    assert host.requested == []


def _review_store(verdict: PreconditionVerdict, reference: str) -> MemoryEvidenceFilesStore:
    """A stored draft whose label reading stood because the local AI the probe asked did not answer."""
    assert verdict.action is not None
    store = MemoryEvidenceFilesStore()
    store.drafts[reference] = synthetic_review(reference).model_copy(
        update={
            "label_reading_fallback": LabelReadingFallbackProjectionV1(
                cause=LabelReadingFallbackCause.READER_UNAVAILABLE,
                unread_fields=("currency", "supplier_name"),
                reader_error_type="InvoiceDraftReaderUnavailableError",
                failed_condition_id=str(verdict.failed_condition_id),
                recovery_action_id=verdict.action.action_id,
            )
        }
    )
    return store


def _review_controller() -> LedgerWorkspaceController:
    return LedgerWorkspaceController(
        ledger_context(), ledger_projection(), LedgerWorkspaceInjection(review_action=ledger_review_action())
    )


async def _full_review(
    rows: tuple[DependencyStatusRow, ...],
) -> tuple[SetupStatusWorkspaceHostApp, bool, bool, str, str | None]:
    """Read the summary, then the full review, and press the offer when it is a button."""
    reference = synthetic_evidence_id(1)
    store = _review_store(_probe_verdict(), reference)
    screen = LedgerEvidenceFilesReviewScreen(_review_controller(), store.doors(), reference=reference)
    host = SetupStatusWorkspaceHostApp(screen, rows=rows)
    with override_settings(cadrumo_output_language="en"):
        async with host.run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            offer = screen.query_one("#evidence-files-review-setup", SetupItemOffer)
            await settle_until(pilot, lambda: bool(screen.shown_lines), "the review summary")
            summary_offered = offer.display
            assert host.row_reads == []
            await press(pilot, "evidence-files-full")
            await settle_until(pilot, lambda: offer.row is not None, "the local AI's row to be read")
            shown = offer.display
            text = str(offer.query_one(Static).render())
            button = offer.query_one(Button)
            label = str(button.label) if shown and button.display else None
            if label is not None:
                button.press()
                await settle(pilot)
    return host, summary_offered, shown, text, label


@pytest.mark.asyncio
async def test_a_full_review_whose_label_reading_stood_without_the_local_ai_offers_its_setup() -> None:
    host, summary_offered, shown, _text, label = await _full_review((absent_row("local_ai"),))

    assert not summary_offered
    assert shown
    assert label == "Set up: Local AI"
    assert host.row_reads == ["local_ai"]
    assert host.requested == ["local_ai"]


@pytest.mark.asyncio
async def test_a_full_review_for_a_local_ai_this_build_cannot_set_up_shows_its_sentence_and_offers_nothing() -> None:
    host, summary_offered, shown, text, label = await _full_review((not_in_this_build_row("local_ai"),))

    assert not summary_offered
    assert shown
    assert label is None
    assert text == LOCAL_AI_HELD
    assert host.requested == []
