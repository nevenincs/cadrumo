"""Invoice entry and evidence registration over injected doors."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import cast, override

import pytest
from textual.widgets import Button, DataTable, Input, Select, Static

from cadrumo_client.contracts.contracts import RefusalCode, RefusalError

from .....application.ledger.attachment_review import AttachmentReviewItem
from .....application.ledger.evidence_errors import PurchaseInvoiceEvidenceInputError
from .....application.ledger.invoice_evidence_operation_dtos import InvoiceDraftProjectionV1
from .....application.ledger.models import ManualLedgerTransactionResult
from .....application.ledger.workspace import LedgerWorkspaceArea
from .....core.config import override_settings
from .....core.errors.error_codes import resolve_error_message
from .....core.identity.transaction_ids import TransactionId
from .....domain.invoices.errors import InvoiceValidationError
from .....domain.iva.schema import InvoiceKind
from .....domain.transactions.models import BucketTransactionRef
from ...account import AccountSessionExpiredError
from ...components.host import ScreenHostApp
from ...navigation import TuiScreenContextV1
from ...tests.settling import settle, settle_until
from ..controller import LedgerWorkspaceController
from ..evidence import LedgerEvidenceScreen
from ..invoice_entry import LedgerInvoiceEntryScreen
from ..models import (
    LedgerEvidenceConfirmationV1,
    LedgerEvidenceConfirmedV1,
    LedgerEvidenceDraftV1,
    LedgerEvidenceRecordRowV1,
    LedgerEvidenceRecordStatus,
    LedgerExclusionResultV1,
    LedgerExclusionSubmissionV1,
    LedgerFlowState,
    LedgerInvoiceAddResultV1,
    LedgerInvoiceEntryV1,
)
from ..review import LedgerReviewScreen
from ..routes import ledger_screen_factory
from ..workspace_injection import LedgerWorkspaceInjection, LedgerWorkspaceRefreshV1
from .workspace_fixtures import (
    ClassificationDoor,
    ledger_classify_action,
    ledger_context,
    ledger_evidence_action,
    ledger_projection,
    ledger_review_action,
    ledger_review_door,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_INVOICE_ID = "c" * 64


class _InvoiceDoor:
    def __init__(self, *, refuse: bool = False) -> None:
        self.entries: list[LedgerInvoiceEntryV1] = []
        self._refuse = refuse

    async def __call__(self, entry: LedgerInvoiceEntryV1) -> LedgerInvoiceAddResultV1:
        self.entries.append(entry)
        if self._refuse:
            raise InvoiceValidationError(
                "duplicate",
                translated_message="application.invoices.creation.errors.duplicate_invoice",
                context={"invoice_id": _INVOICE_ID},
            )
        taxable_base = entry.taxable_base
        assert taxable_base is not None
        return LedgerInvoiceAddResultV1(
            invoice_id=_INVOICE_ID,
            invoice_number=entry.invoice_number,
            base_total=taxable_base,
            iva_total=Decimal("252.00"),
            grand_total=Decimal("1452.00"),
            currency=entry.currency,
        )


def _invoice_screen(door: _InvoiceDoor) -> LedgerInvoiceEntryScreen:
    return LedgerInvoiceEntryScreen(
        LedgerWorkspaceController(
            ledger_context(),
            ledger_projection(),
            LedgerWorkspaceInjection(review_action=ledger_review_action(), invoice_add_door=door),
        )
    )


def _fill(screen: LedgerInvoiceEntryScreen, **values: str) -> None:
    for name, value in values.items():
        screen.query_one(f"#ledger-invoice-{name.replace('_', '-')}", Input).value = value


@pytest.mark.asyncio
async def test_invoice_entry_names_every_unreadable_field_and_writes_nothing() -> None:
    door = _InvoiceDoor()
    screen = _invoice_screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(100, 80)) as pilot:
            await settle(pilot)
            _fill(screen, invoice_date="27/03/2026", taxable_base="twelve")
            screen.query_one("#ledger-invoice-review", Button).press()
            await settle(pilot)
            notice = str(screen.query_one("#ledger-refusal", Static).render())
            assert "Counterparty name is required." in notice
            assert "YYYY-MM-DD" in notice
            assert "must be a number" in notice
            assert screen.flow_state is LedgerFlowState.EDITING
            assert not door.entries


@pytest.mark.asyncio
async def test_invoice_entry_records_only_the_reviewed_entry() -> None:
    door = _InvoiceDoor()
    screen = _invoice_screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(100, 80)) as pilot:
            await settle(pilot)
            _fill(
                screen,
                counterparty_name="Hardware Profesional Sur SL",
                counterparty_nif="B92000090",
                invoice_number="A-0003",
                invoice_date="2026-03-27",
                taxable_base="1200.00",
                iva_rate="21",
            )
            screen.query_one("#ledger-invoice-review", Button).press()
            await settle(pilot)
            assert screen.flow_state is LedgerFlowState.CONFIRMING
            assert screen.query_one("#ledger-invoice-invoice-number", Input).disabled
            assert "A-0003" in str(screen.query_one("#ledger-invoice-summary", Static).render())
            assert not door.entries
            screen.query_one("#ledger-invoice-confirm", Button).press()
            await settle(pilot)
            assert screen.flow_state is LedgerFlowState.SUCCEEDED
            assert "total 1452.00 EUR" in str(screen.query_one("#ledger-flow-status", Static).render())
    assert door.entries == [
        LedgerInvoiceEntryV1(
            kind=InvoiceKind.RECEIVED,
            counterparty_name="Hardware Profesional Sur SL",
            counterparty_nif="B92000090",
            country_code="ES",
            invoice_number="A-0003",
            invoice_date=date(2026, 3, 27),
            taxable_base=Decimal("1200.00"),
            iva_rate=Decimal(21),
            currency="EUR",
        )
    ]


@pytest.mark.asyncio
async def test_invoice_entry_preserves_explicit_iva_treatment_for_linked_income() -> None:
    """The issued document's tax treatment reaches the shared invoice writer."""
    door = _InvoiceDoor()
    screen = _invoice_screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(100, 80)) as pilot:
            await settle(pilot)
            _fill(
                screen,
                counterparty_name="Synthetic client",
                counterparty_nif="A58818501",
                invoice_number="S-01",
                invoice_date="2025-02-15",
                taxable_base="4000.00",
                iva_rate="21",
                iva_category="domestic_general",
                retention_rate="0.07",
                retention_amount="280.00",
            )
            screen.query_one("#ledger-invoice-kind", Select).value = "issued"
            screen.query_one("#ledger-invoice-review", Button).press()
            await settle(pilot)
            assert screen.flow_state is LedgerFlowState.CONFIRMING, str(
                screen.query_one("#ledger-refusal", Static).render()
            )
            screen.query_one("#ledger-invoice-confirm", Button).press()
            await settle(pilot)
            assert screen.flow_state is LedgerFlowState.SUCCEEDED
    assert len(door.entries) == 1
    category = door.entries[0].iva_category
    assert category is not None
    assert category.value == "domestic_general"


@pytest.mark.asyncio
async def test_invoice_writer_refusal_is_shown_as_the_application_says_it() -> None:
    screen = _invoice_screen(_InvoiceDoor(refuse=True))
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(100, 80)) as pilot:
            await settle(pilot)
            _fill(screen, counterparty_name="X SL", invoice_number="1", invoice_date="2026-01-01", taxable_base="10")
            screen.query_one("#ledger-invoice-review", Button).press()
            await settle(pilot)
            screen.query_one("#ledger-invoice-confirm", Button).press()
            await settle(pilot)
            assert screen.flow_state is LedgerFlowState.FAILED
            refusal = str(screen.query_one("#ledger-refusal", Static).render())
            assert refusal
            assert "application.invoices" not in refusal


class _EvidenceDoor:
    def __init__(self, *, expire_on_confirm: bool = False) -> None:
        self.expire_on_confirm = expire_on_confirm
        self.full_projection: InvoiceDraftProjectionV1 | None = None
        self.records: list[LedgerEvidenceRecordRowV1] = []
        self.added: list[str] = []
        self.extracted: list[str] = []
        self.confirmed: list[LedgerEvidenceConfirmationV1] = []

    def list_records(self) -> tuple[LedgerEvidenceRecordRowV1, ...]:
        return tuple(self.records)

    async def add(self, source_path: str) -> LedgerEvidenceRecordRowV1:
        self.added.append(source_path)
        if not source_path.endswith(".pdf"):
            raise PurchaseInvoiceEvidenceInputError(
                translated_message="errors.refused.refused_ledger_evidence_input",
                context={"source_path": source_path, "resolved_path": source_path},
            )
        record = LedgerEvidenceRecordRowV1(
            evidence_id="8747cbf318cf0adb",
            media_kind="pdf",
            file_name="invoice_A-0003.pdf",
            supplier=None,
            invoice_number=None,
            created_at="2026-09-16",
            status=LedgerEvidenceRecordStatus.AWAITING,
        )
        self.records.append(record)
        return record

    async def extract(self, evidence_id: str) -> LedgerEvidenceDraftV1:
        self.extracted.append(evidence_id)
        return LedgerEvidenceDraftV1(
            evidence_id=evidence_id,
            supplier_name="Hardware Profesional Sur SL",
            supplier_tax_id="B92000090",
            invoice_number="A-0003",
            invoice_date="2026-03-27",
            taxable_base=None,
            iva_rate="21",
            iva_amount=None,
            grand_total=None,
            currency="EUR",
            suggested_kind=InvoiceKind.RECEIVED,
            discrepancies=0,
            full_projection=self.full_projection,
        )

    async def confirm(self, confirmation: LedgerEvidenceConfirmationV1) -> LedgerEvidenceConfirmedV1:
        self.confirmed.append(confirmation)
        if self.expire_on_confirm:
            raise AccountSessionExpiredError()
        return LedgerEvidenceConfirmedV1(
            invoice_id="c" * 64,
            invoice_number="A-0003",
            grand_total=Decimal("1452.00"),
            currency="EUR",
            created=True,
            printed_total_disagrees=False,
        )


def _evidence_screen(door: _EvidenceDoor, refreshes: list[int]) -> LedgerEvidenceScreen:
    projection = ledger_projection()

    def refresh() -> LedgerWorkspaceRefreshV1:
        refreshes.append(1)
        return LedgerWorkspaceRefreshV1(projection=projection, evidence_items=())

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
                refresh=refresh,
            ),
        )
    )


@pytest.mark.asyncio
async def test_evidence_is_added_and_listed() -> None:
    door = _EvidenceDoor()
    refreshes: list[int] = []
    screen = _evidence_screen(door, refreshes)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(100, 60)) as pilot:
            await settle(pilot)
            screen.query_one("#ledger-evidence-path", Input).value = "notes.txt"
            screen.query_one("#ledger-evidence-add", Button).press()
            await settle(pilot)
            assert str(screen.query_one("#ledger-refusal", Static).render())
            assert not refreshes
            screen.query_one("#ledger-evidence-path", Input).value = "C:/synthetic/invoice_A-0003.pdf"
            screen.query_one("#ledger-evidence-add", Button).press()
            await settle(pilot)
            assert door.added[-1] == "C:/synthetic/invoice_A-0003.pdf"
            assert refreshes == [1]
            records = screen.query_one("#ledger-evidence-records", DataTable)
            await settle_until(pilot, lambda: bool(records.ordered_rows), "the refreshed evidence rows")
            assert tuple(row.key.value for row in records.ordered_rows) == ("8747cbf318cf0adb",)
            records.focus()
            records.move_cursor(row=0)
            await pilot.press("enter")
            await settle(pilot)
            assert screen.query_one("#ledger-evidence-confirm", Button).disabled
            screen.query_one("#ledger-evidence-extract", Button).press()
            await settle(pilot)
            assert door.extracted == ["8747cbf318cf0adb"]
            draft = str(screen.query_one("#ledger-evidence-draft", Static).render())
            # An amount the reader could not ground reads as unread, never as zero.
            assert "Base unread" in draft
            assert "0.00" not in draft
            assert screen.query_one("#ledger-evidence-counterparty", Input).value == "Hardware Profesional Sur SL"
            screen.query_one("#ledger-evidence-confirm", Button).press()
            await settle(pilot)
            assert door.confirmed == [
                LedgerEvidenceConfirmationV1(
                    evidence_id="8747cbf318cf0adb",
                    kind=InvoiceKind.RECEIVED,
                    country_code="ES",
                    counterparty_name="Hardware Profesional Sur SL",
                )
            ]
            assert refreshes == [1, 1]


class _RefusedRecordsDoor(_EvidenceDoor):
    def __init__(self, refusal: RefusalError) -> None:
        super().__init__()
        self.refusal = refusal

    @override
    def list_records(self) -> tuple[LedgerEvidenceRecordRowV1, ...]:
        raise self.refusal


@pytest.mark.asyncio
async def test_a_refused_records_load_is_said_on_the_screen() -> None:
    refusal = RefusalError(RefusalCode.DRAINING)
    screen = _evidence_screen(_RefusedRecordsDoor(refusal), [])
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(100, 60)) as pilot:
            detail = screen.query_one("#ledger-evidence-record-detail", Static)
            await settle_until(
                pilot, lambda: str(detail.render()) == resolve_error_message(refusal), "the refused load to be said"
            )
            assert pilot.app.screen is screen
            assert screen.query_one("#ledger-evidence-records", DataTable).row_count == 0


@pytest.mark.asyncio
async def test_confirm_eligibility_is_limited_to_the_currently_reviewed_record() -> None:
    door = _EvidenceDoor()
    first = LedgerEvidenceRecordRowV1(
        evidence_id="8747cbf318cf0adb",
        media_kind="pdf",
        file_name="invoice_A-0003.pdf",
        supplier=None,
        invoice_number=None,
        created_at="2026-09-16",
        status=LedgerEvidenceRecordStatus.UNMEASURED,
    )
    door.records.extend(
        (
            first,
            first.model_copy(update={"evidence_id": "a747cbf318cf0adc", "file_name": "invoice_B-0004.pdf"}),
        )
    )
    screen = _evidence_screen(door, [])
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(100, 60)) as pilot:
            await settle(pilot)
            records = screen.query_one("#ledger-evidence-records", DataTable)
            await settle_until(pilot, lambda: len(records.ordered_rows) == 2, "both evidence rows")
            assert len(records.ordered_rows) == 2
            records.focus()
            records.move_cursor(row=0)
            await pilot.press("enter")
            await settle(pilot)
            confirm = screen.query_one("#ledger-evidence-confirm", Button)
            assert confirm.disabled

            screen.query_one("#ledger-evidence-extract", Button).press()
            await settle(pilot)
            assert not confirm.disabled
            assert screen.draft is not None and screen.draft.evidence_id == first.evidence_id

            records.move_cursor(row=1)
            await pilot.press("enter")
            await settle(pilot)
            assert confirm.disabled
            assert screen.draft is None
            confirm.press()
            await settle(pilot)
            assert not door.confirmed


@pytest.mark.asyncio
async def test_session_expiry_clears_full_draft_and_record_rows() -> None:
    door = _EvidenceDoor(expire_on_confirm=True)
    door.full_projection = InvoiceDraftProjectionV1(supplier_name="private full evidence draft")
    door.records.append(
        LedgerEvidenceRecordRowV1(
            evidence_id="8747cbf318cf0adb",
            media_kind="pdf",
            file_name="invoice_A-0003.pdf",
            supplier=None,
            invoice_number=None,
            created_at="2026-09-16",
            status=LedgerEvidenceRecordStatus.UNMEASURED,
        )
    )
    screen = _evidence_screen(door, [])
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(100, 60)) as pilot:
            await settle(pilot)
            records = screen.query_one("#ledger-evidence-records", DataTable)
            await settle_until(pilot, lambda: bool(records.ordered_rows), "the evidence rows")
            records.focus()
            records.move_cursor(row=0)
            await pilot.press("enter")
            await settle(pilot)

            screen.query_one("#ledger-evidence-extract", Button).press()
            await settle(pilot)
            assert screen.draft is not None and screen.draft.full_projection is not None
            assert "private full evidence draft" in str(screen.query_one("#ledger-evidence-draft", Static).render())

            screen.query_one("#ledger-evidence-confirm", Button).press()
            await settle(pilot)
            assert screen.draft is None
            assert str(screen.query_one("#ledger-evidence-draft", Static).render()) == ""
            assert not records.ordered_rows
            assert screen.selected_record_id is None


@pytest.mark.asyncio
async def test_runtime_evidence_route_needs_no_attachment_review_inventory() -> None:
    projection = ledger_projection()
    door = _EvidenceDoor()
    action = ledger_evidence_action()
    factory = ledger_screen_factory(
        projection,
        review_action=ledger_review_action(),
        evidence_action=action,
        evidence_door=door,
    )
    context = TuiScreenContextV1(destination="workbench.ledger", action_candidate_id=action.action_id)
    screen = cast(LedgerEvidenceScreen, factory(context))

    assert screen.controller.evidence_items is None
    assert screen.controller.refusal_for(LedgerWorkspaceArea.EVIDENCE) is None
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(100, 60)) as pilot:
            await settle(pilot)
            assert isinstance(screen.query_one("#ledger-evidence-records", DataTable), DataTable)
            assert not tuple(screen.query("#ledger-evidence"))


class _ExclusionDoor:
    def __init__(self) -> None:
        self.calls: list[LedgerExclusionSubmissionV1] = []

    async def __call__(self, submission: LedgerExclusionSubmissionV1) -> ManualLedgerTransactionResult:
        self.calls.append(submission)
        return ManualLedgerTransactionResult.model_construct(
            ref=BucketTransactionRef.model_construct(transaction_id=submission.transaction_id),
        )


@pytest.mark.asyncio
async def test_exclude_names_the_entry_withdraws_on_escape_and_writes_once_on_confirm() -> None:
    projection = ledger_projection()
    door = _ExclusionDoor()
    refreshes: list[int] = []

    def refresh() -> LedgerWorkspaceRefreshV1:
        refreshes.append(1)
        return LedgerWorkspaceRefreshV1(projection=projection, evidence_items=None)

    controller = LedgerWorkspaceController(
        ledger_context(),
        projection,
        LedgerWorkspaceInjection(
            review_action=ledger_review_action(),
            review_door=ledger_review_door(projection),
            classify_action=ledger_classify_action(),
            classification_submitter=ClassificationDoor(),
            exclusion_submitter=door,
            refresh=refresh,
        ),
    )
    screen = LedgerReviewScreen(controller)
    first = projection.review_transaction_ids[0]
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(100, 40)) as pilot:
            await settle(pilot)
            assert not screen.query_one("#ledger-exclusion-confirm", Button).display
            review = screen.query_one("#ledger-review", DataTable)
            review.focus()
            review.move_cursor(row=0)
            await pilot.press("x")
            await settle(pilot)
            question = str(screen.query_one("#ledger-exclusion-question", Static).render())
            assert controller.entry_label(first) in question
            assert screen.query_one("#ledger-exclusion-confirm", Button).display
            await pilot.press("escape")
            await settle(pilot)
            assert screen.pending_exclusion is None
            assert not screen.back_requested
            assert not door.calls
            await pilot.press("x")
            await settle(pilot)
            screen.query_one("#ledger-exclusion-confirm", Button).press()
            await settle(pilot)
    assert [call.transaction_id for call in door.calls] == [first]
    assert door.calls[0].action == ledger_classify_action()
    assert refreshes == [1]


class _IdentityExclusionDoor:
    """A runtime-shaped door that answers with the identity it settled."""

    def __init__(self, settled: TransactionId | None = None) -> None:
        self.settled = settled

    async def __call__(self, submission: LedgerExclusionSubmissionV1) -> LedgerExclusionResultV1:
        return LedgerExclusionResultV1(transaction_id=self.settled or submission.transaction_id)


def _exclusion_controller(door: _IdentityExclusionDoor) -> LedgerWorkspaceController:
    return LedgerWorkspaceController(
        ledger_context(),
        ledger_projection(),
        LedgerWorkspaceInjection(
            review_action=ledger_review_action(),
            classify_action=ledger_classify_action(),
            classification_submitter=ClassificationDoor(),
            exclusion_submitter=door,
        ),
    )


@pytest.mark.asyncio
async def test_an_identity_only_exclusion_result_settles_for_the_entry_it_names() -> None:
    controller = _exclusion_controller(_IdentityExclusionDoor())
    target = controller.projection.review_transaction_ids[0]
    result = await controller.submit_exclusion(target, listed=(target,))
    assert result == LedgerExclusionResultV1(transaction_id=target)


@pytest.mark.asyncio
async def test_an_exclusion_result_for_another_entry_is_refused() -> None:
    projection = ledger_projection()
    first, other = projection.review_transaction_ids[0], projection.entries[-1].transaction_id
    assert first != other
    controller = _exclusion_controller(_IdentityExclusionDoor(settled=other))
    with pytest.raises(ValueError, match="identity disagrees"):
        await controller.submit_exclusion(first, listed=(first,))


@pytest.mark.asyncio
async def test_an_exclusion_of_an_entry_the_review_queue_does_not_list_is_refused_before_the_door() -> None:
    door = _ExclusionDoor()
    projection = ledger_projection()
    first, other = projection.review_transaction_ids
    controller = LedgerWorkspaceController(
        ledger_context(),
        projection,
        LedgerWorkspaceInjection(
            review_action=ledger_review_action(),
            classify_action=ledger_classify_action(),
            classification_submitter=ClassificationDoor(),
            exclusion_submitter=door,
        ),
    )
    with pytest.raises(ValueError, match="absent from the visible review list"):
        await controller.submit_exclusion(first, listed=(other,))
    assert not door.calls


def test_exclude_is_not_offered_without_the_classify_authority() -> None:
    controller = LedgerWorkspaceController(
        ledger_context(),
        ledger_projection(),
        LedgerWorkspaceInjection(review_action=ledger_review_action(), exclusion_submitter=_ExclusionDoor()),
    )
    assert not controller.can_exclude()
