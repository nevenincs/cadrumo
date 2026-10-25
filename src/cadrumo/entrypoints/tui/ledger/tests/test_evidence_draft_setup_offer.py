"""A label reading that stood without the local AI offers the local AI's setup beside its line.

The Evidence area reads one document through its door; the draft's fallback
says the model fill did not run and names the local AI's setup, as the reader
probe names it. The offer reads the local AI's quick-status row the way the TUI
root reads it: an absent row's action sets the item up, so the offer opens the
setup page on it; a row this build cannot set up shows its own sentence and
offers nothing. A fallback for any other cause offers nothing and reads no row.
The screen runs under Textual's pilot.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from textual.pilot import Pilot
from textual.widgets import Button, DataTable, Static

from .....adapters.outbound.components.tests.recorded_rows import not_in_this_build_row, recorded_absent_row
from .....application.dependency_contracts import DependencyStatusRow
from .....application.ledger.attachment_review import AttachmentReviewItem
from .....application.ledger.invoice_draft_records import LabelReadingFallback, LabelReadingFallbackCause
from .....application.provisioning_contracts import LOCAL_AI_PROVISION_ACTION_ID, ProvisioningPreconditionCondition
from .....core.config import override_settings
from .....domain.iva.schema import InvoiceKind
from ...setup.offer import SetupItemOffer
from ...tests.settling import settle, settle_until
from ..controller import LedgerWorkspaceController
from ..evidence import LedgerEvidenceScreen
from ..models import (
    LedgerEvidenceConfirmationV1,
    LedgerEvidenceConfirmedV1,
    LedgerEvidenceDraftV1,
    LedgerEvidenceRecordRowV1,
    LedgerEvidenceRecordStatus,
    LedgerReaderReadinessV1,
)
from ..workspace_injection import LedgerWorkspaceInjection, LedgerWorkspaceRefreshV1
from .setup_status_fixtures import LOCAL_AI_HELD, SetupStatusWorkspaceHostApp
from .workspace_fixtures import ledger_context, ledger_evidence_action, ledger_projection, ledger_review_action

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_EVIDENCE_ID = "8747cbf318cf0adb"


def _local_ai_fallback() -> LabelReadingFallback:
    return LabelReadingFallback(
        cause=LabelReadingFallbackCause.READER_UNAVAILABLE,
        unread_fields=("currency", "supplier_name"),
        reader_error_type="InvoiceDraftReaderUnavailableError",
        failed_condition_id=ProvisioningPreconditionCondition.ROLE_MODEL_INSTALLED.value,
        recovery_action_id=LOCAL_AI_PROVISION_ACTION_ID,
    )


def _headroom_fallback() -> LabelReadingFallback:
    return LabelReadingFallback(
        cause=LabelReadingFallbackCause.LOAD_HEADROOM_REFUSED,
        unread_fields=("currency",),
        reader_error_type="InvoiceDraftReaderUnavailableError",
    )


class _EvidenceDoor:
    """One stored document whose reading stands on its labels with ``fallback``."""

    def __init__(self, fallback: LabelReadingFallback) -> None:
        self.fallback = fallback
        self.extracted: list[str] = []

    def list_records(self) -> tuple[LedgerEvidenceRecordRowV1, ...]:
        return (
            LedgerEvidenceRecordRowV1(
                evidence_id=_EVIDENCE_ID,
                media_kind="pdf",
                file_name="invoice_A-0003.pdf",
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
        return LedgerEvidenceDraftV1(
            evidence_id=evidence_id,
            supplier_name=None,
            supplier_tax_id="B92000090",
            invoice_number="A-0003",
            invoice_date="2026-03-27",
            taxable_base="60.00",
            iva_rate="21",
            iva_amount="12.60",
            grand_total="72.60",
            currency=None,
            suggested_kind=InvoiceKind.RECEIVED,
            discrepancies=0,
            label_reading_fallback=self.fallback,
        )

    async def confirm(self, confirmation: LedgerEvidenceConfirmationV1) -> LedgerEvidenceConfirmedV1:
        return LedgerEvidenceConfirmedV1(
            invoice_id="c" * 64,
            invoice_number="A-0003",
            grand_total=Decimal("72.60"),
            currency="EUR",
            created=True,
            printed_total_disagrees=False,
        )


def _screen(door: _EvidenceDoor) -> LedgerEvidenceScreen:
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


async def _read(pilot: Pilot[None], screen: LedgerEvidenceScreen, door: _EvidenceDoor) -> SetupItemOffer:
    records = screen.query_one("#ledger-evidence-records", DataTable)
    await settle_until(pilot, lambda: bool(records.ordered_rows), "the evidence rows")
    records.focus()
    records.move_cursor(row=0)
    await pilot.press("enter")
    await settle(pilot)
    screen.query_one("#ledger-evidence-extract", Button).press()
    await settle_until(pilot, lambda: door.extracted == [_EVIDENCE_ID], "the document to be read")
    await settle(pilot)
    return screen.query_one("#ledger-evidence-setup", SetupItemOffer)


async def _run(
    fallback: LabelReadingFallback, rows: tuple[DependencyStatusRow, ...]
) -> tuple[SetupStatusWorkspaceHostApp, bool, str, str | None]:
    door = _EvidenceDoor(fallback)
    screen = _screen(door)
    host = SetupStatusWorkspaceHostApp(screen, rows=rows)
    with override_settings(cadrumo_output_language="en"):
        async with host.run_test(size=(100, 70)) as pilot:
            await settle(pilot)
            offer = await _read(pilot, screen, door)
            shown = offer.display
            text = str(offer.query_one(Static).render())
            button = offer.query_one(Button)
            label = str(button.label) if button.display and shown else None
            if label is not None:
                button.press()
                await settle(pilot)
    return host, shown, text, label


@pytest.mark.asyncio
async def test_a_label_reading_without_the_local_ai_offers_its_setup() -> None:
    host, shown, _text, label = await _run(_local_ai_fallback(), (recorded_absent_row("local_ai"),))

    assert shown
    assert label == "Set up: Local AI"
    assert host.row_reads == ["local_ai"]
    assert host.requested == ["local_ai"]


@pytest.mark.asyncio
async def test_a_local_ai_this_build_cannot_set_up_shows_its_sentence_and_offers_nothing() -> None:
    host, shown, text, label = await _run(_local_ai_fallback(), (not_in_this_build_row("local_ai"),))

    assert shown
    assert label is None
    assert text == LOCAL_AI_HELD
    assert host.requested == []


@pytest.mark.asyncio
async def test_a_fallback_setup_cannot_end_offers_nothing_and_reads_no_row() -> None:
    host, shown, _text, label = await _run(_headroom_fallback(), (recorded_absent_row("local_ai"),))

    assert not shown
    assert label is None
    assert host.row_reads == []
    assert host.requested == []
