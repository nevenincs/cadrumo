"""Focused mounted behavior for canonical Ledger record detail routes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import cast, override

import pytest
from textual.widgets import Button, DataTable, Input, Static

from .....application.invoices.catalogue_lifecycle import CatalogueInvoicePatch
from .....application.ledger.models import ManualLedgerTransactionPatch
from .....core.config import override_settings
from .....domain.invoices.enums import IvaRate
from .....domain.invoices.models import Invoice, InvoiceLine
from .....domain.iva.classification import InvoiceKind
from .....domain.transactions.enums import TransactionDirection
from .....domain.transactions.errors import TransactionValidationError
from .....domain.transactions.models import Transaction
from .....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..controller import LedgerWorkspaceController
from ..record_doors import LedgerRecordDoors
from ..record_views import LedgerInvoiceCatalogueScreen, LedgerInvoiceDetailScreen, LedgerTransactionDetailScreen
from ..workspace_injection import LedgerWorkspaceInjection
from .test_ledger_selection_journey import _WorkspaceHostApp
from .workspace_fixtures import ledger_context, ledger_projection, ledger_review_action

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]


@dataclass
class _RecordDoor:
    invoice_record: Invoice
    writes: int = 0

    async def invoices(self) -> tuple[Invoice, ...]:
        return (self.invoice_record,)

    async def invoice(self, invoice_id: str) -> Invoice:
        assert invoice_id == self.invoice_record.invoice_id
        return self.invoice_record

    async def update_invoice(self, baseline: Invoice, patch: CatalogueInvoicePatch) -> Invoice:
        assert baseline == self.invoice_record
        assert patch.model_fields_set == {"notes"}
        self.writes += 1
        self.invoice_record = self.invoice_record.model_copy(update={"notes": patch.notes})
        return self.invoice_record

    async def transaction(self, transaction_id: str) -> Transaction:
        raise AssertionError(transaction_id)

    async def update_transaction(self, baseline: Transaction, patch: ManualLedgerTransactionPatch) -> Transaction:
        raise AssertionError((baseline, patch))


def _invoice() -> Invoice:
    return Invoice.model_construct(
        bucket_id="synthetic-bucket",
        invoice_id="c" * 64,
        kind=InvoiceKind.ISSUED,
        invoice_number="S-01",
        issued_at=date(2025, 3, 15),
        counterparty_name="Synthetic customer",
        counterparty_tax_id="A58818501",
        base_total=Decimal("100.00"),
        iva_total=Decimal("21.00"),
        grand_total=Decimal("121.00"),
        currency="EUR",
        # Every persisted invoice carries its printed lines; the detail view
        # renders them, so a fixture without any is not an invoice it can meet.
        lines=(
            InvoiceLine.model_construct(
                description="Synthetic service",
                quantity=Decimal(1),
                unit_price=Decimal("100.00"),
                subtotal=Decimal("100.00"),
                iva_rate=IvaRate.from_registry("RATE_21"),
                iva_amount=Decimal("21.00"),
            ),
        ),
        linked_transaction_ids=("t" * 64,),
        notes="before",
        provenance=None,
    )


def _controller(door: _RecordDoor) -> LedgerWorkspaceController:
    return LedgerWorkspaceController(
        ledger_context(),
        ledger_projection(),
        LedgerWorkspaceInjection(review_action=ledger_review_action(), record_doors=cast(LedgerRecordDoors, door)),
    )


@pytest.mark.asyncio
async def test_invoice_catalogue_opens_canonical_detail_and_saves_reviewed_notes() -> None:
    door = _RecordDoor(_invoice())
    screen = LedgerInvoiceCatalogueScreen(_controller(door), cast(LedgerRecordDoors, door))
    with override_settings(cadrumo_output_language="en"):
        async with _WorkspaceHostApp(screen).run_test(size=(110, 55)) as pilot:
            await pilot.app.workers.wait_for_complete()
            await pilot.pause()
            table = screen.query_one("#ledger-invoice-catalogue", DataTable)
            assert table.row_count == 1
            table.focus()
            table.move_cursor(row=0)
            await pilot.press("enter")
            await pilot.app.workers.wait_for_complete()
            detail = pilot.app.screen
            assert isinstance(detail, LedgerInvoiceDetailScreen)
            rendered = str(detail.query_one("#ledger-record-detail", Static).render())
            assert "121.00" in rendered
            assert "1. Synthetic service · 1 × 100.00 = 100.00 · IVA RATE_21 21.00" in rendered
            detail.query_one("#ledger-invoice-notes", Input).value = "after"
            detail.query_one("#ledger-invoice-edit-review", Button).press()
            await pilot.pause()
            assert door.writes == 0
            detail.query_one("#ledger-invoice-edit-save", Button).press()
            await pilot.app.workers.wait_for_complete()
            await pilot.pause()
            assert door.writes == 1
            assert door.invoice_record.notes == "after"
            assert detail.baseline == door.invoice_record


class _LinkedRecordDoor(_RecordDoor):
    def __init__(self, invoice_record: Invoice, transaction: Transaction) -> None:
        super().__init__(invoice_record)
        self.linked_transaction = transaction

    @override
    async def transaction(self, transaction_id: str) -> Transaction:
        assert transaction_id == self.linked_transaction.transaction_id
        return self.linked_transaction

    @override
    async def update_transaction(self, baseline: Transaction, patch: ManualLedgerTransactionPatch) -> Transaction:
        assert baseline == self.linked_transaction
        assert patch.description == "changed description"
        self.writes += 1
        raise TransactionValidationError("linked transaction identity cannot change without updating its invoice link")


@pytest.mark.asyncio
async def test_linked_transaction_detail_shows_refusal_without_claiming_a_save() -> None:
    invoice = _invoice()
    transaction = Transaction.model_construct(
        transaction_id="t" * 64,
        direction=TransactionDirection.INCOMING,
        invoice_id=invoice.invoice_id,
        raw=RawTransaction.model_construct(
            booked_date=date(2025, 3, 18),
            amount=Decimal("121.00"),
            currency="EUR",
            description="original description",
            provenance=RawProvenance.model_construct(
                source_path=Path("synthetic-statement.csv"), source_row_index=1, source_format=SourceFormat.CSV
            ),
        ),
    )
    door = _LinkedRecordDoor(invoice, transaction)
    screen = LedgerTransactionDetailScreen(_controller(door), cast(LedgerRecordDoors, door), transaction.transaction_id)
    with override_settings(cadrumo_output_language="en"):
        async with _WorkspaceHostApp(screen).run_test(size=(110, 55)) as pilot:
            await pilot.app.workers.wait_for_complete()
            screen.query_one("#ledger-transaction-description", Input).value = "changed description"
            screen.query_one("#ledger-transaction-edit-review", Button).press()
            await pilot.pause()
            screen.query_one("#ledger-transaction-edit-save", Button).press()
            await pilot.app.workers.wait_for_complete()
            await pilot.pause()
            assert "identity cannot change" in str(screen.query_one("#ledger-refusal", Static).render())
            assert screen.baseline == transaction
            assert door.linked_transaction == transaction


@pytest.mark.asyncio
async def test_imported_record_details_show_stored_filename_and_row() -> None:
    provenance = RawProvenance.model_construct(
        source_path=Path("march-statement.csv"), source_row_index=7, source_format=SourceFormat.CSV
    )
    invoice = _invoice().model_copy(update={"provenance": provenance})
    transaction = Transaction.model_construct(
        transaction_id="t" * 64,
        created_event_id=None,
        direction=TransactionDirection.INCOMING,
        invoice_id=None,
        raw=RawTransaction.model_construct(
            booked_date=date(2025, 3, 18),
            amount=Decimal("10.00"),
            currency="EUR",
            description="imported description",
            provenance=provenance,
        ),
    )
    door = _LinkedRecordDoor(invoice, transaction)
    controller = _controller(door)
    with override_settings(cadrumo_output_language="en"):
        invoice_screen = LedgerInvoiceDetailScreen(controller, cast(LedgerRecordDoors, door), invoice.invoice_id)
        async with _WorkspaceHostApp(invoice_screen).run_test(size=(110, 55)) as pilot:
            await pilot.app.workers.wait_for_complete()
            assert "march-statement.csv:7" in str(invoice_screen.query_one("#ledger-record-detail", Static).render())
        transaction_screen = LedgerTransactionDetailScreen(
            controller, cast(LedgerRecordDoors, door), transaction.transaction_id
        )
        async with _WorkspaceHostApp(transaction_screen).run_test(size=(110, 55)) as pilot:
            await pilot.app.workers.wait_for_complete()
            assert "march-statement.csv:7" in str(
                transaction_screen.query_one("#ledger-record-detail", Static).render()
            )
