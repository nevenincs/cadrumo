"""Real ledger ports over an isolated profile, and the rows the ledger-writer origin tests build on them."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.attachment import AttachmentStore
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.ledger.action_ports import LedgerActionPorts
from cadrumo.application.ledger.actions_manual import (
    attach_manual_transaction_evidence,
    update_manual_transaction_fields,
)
from cadrumo.application.ledger.models import ManualLedgerTransactionCommand, ManualLedgerTransactionPatch
from cadrumo.domain.attachments.enums import AttachmentKind, AttachmentSource
from cadrumo.domain.attachments.service import AttachmentBytesContent, AttachmentIngestionRequest, add_attachment
from cadrumo.domain.invoices.enums import IvaRate, PaymentStatus
from cadrumo.domain.invoices.models import Invoice, InvoiceLine
from cadrumo.domain.iva.classification import InvoiceKind
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection
from cadrumo.domain.transactions.models import Transaction

from .....application.ledger.tests.manual_transaction_support import create_manual_transaction
from .ledger_action_create_support import ledger_ports_for_test

BUCKET_ID = "43434343-4343-4343-8343-434343434343"
PERSON = "synthetic-person"
AGENT = f"agent:mcp.attended.{UUID('5aa00000-0000-4000-8000-0000000000dd')}"
NOW_DATE = date(2025, 1, 21)
PDF_BYTES = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\norigin-at-the-writers\n%%EOF\n"
BUSINESS = BusinessClassification.BUSINESS


@dataclass(frozen=True, slots=True)
class Ledger:
    """One isolated profile's real ledger ports and the repositories a test reads back through."""

    ports: LedgerActionPorts
    objects: SecureObjectRepository
    transactions: TransactionCatalogueRepository
    events: BucketEventHistoryRepository
    invoices: InvoiceCatalogueRepository
    attachments: AttachmentStore

    def row(self, transaction_id: str) -> Transaction:
        stored = self.transactions.load().get(transaction_id)
        assert stored is not None
        return stored

    def stored(self) -> tuple[dict[str, Transaction], frozenset[str]]:
        """Every stored row and event id: what a refused write must leave exactly as it was."""
        return dict(self.transactions.load().transactions), frozenset(self.events.load().events)


@contextmanager
def composed_ledger(tmp_path: Path) -> Generator[Ledger]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID) as profile:
        objects = profile.repository
        transactions = TransactionCatalogueRepository(bucket_id=BUCKET_ID, objects=objects)
        events = BucketEventHistoryRepository(objects=objects)
        invoices = InvoiceCatalogueRepository(bucket_id=BUCKET_ID, objects=objects)
        attachments = AttachmentStore(objects=objects)
        with ledger_ports_for_test(
            bucket_id=BUCKET_ID,
            objects=objects,
            transaction_repository=transactions,
            bucket_event_repository=events,
            invoice_repository=invoices,
            attachment_store=attachments,
        ) as ports:
            yield Ledger(
                ports=ports,
                objects=objects,
                transactions=transactions,
                events=events,
                invoices=invoices,
                attachments=attachments,
            )


def add_row(
    ledger: Ledger,
    *,
    description: str,
    actor: str = PERSON,
    classification: BusinessClassification = BusinessClassification.NOT_YET_PROCESSED,
) -> str:
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=BUCKET_ID,
            booked_date=NOW_DATE,
            amount=Decimal("121.00"),
            direction=TransactionDirection.OUTGOING,
            description=description,
            business_classification=classification,
            actor=actor,
        ),
        ports=ledger.ports,
    )
    return created.ref.transaction_id


def classify_row(
    ledger: Ledger,
    transaction_id: str,
    *,
    actor: str,
    stamp: str | None = None,
    to: BusinessClassification = BUSINESS,
) -> None:
    update_manual_transaction_fields(
        bucket_id=BUCKET_ID,
        transaction_id=transaction_id,
        patch=ManualLedgerTransactionPatch(business_classification=to),
        actor=actor,
        source_command="aeat app ledger classify",
        classified_by_override=stamp,
        ports=ledger.ports,
    )


def add_row_classified_by_a_rule(ledger: Ledger, *, description: str) -> str:
    transaction_id = add_row(ledger, description=description)
    classify_row(ledger, transaction_id, actor=PERSON, stamp="rule:synthetic")
    return transaction_id


def store_attachment(ledger: Ledger, marker: bytes) -> str:
    attachment = add_attachment(
        ledger.attachments,
        content=AttachmentBytesContent(data=PDF_BYTES + marker),
        request=AttachmentIngestionRequest(
            kind=AttachmentKind.INVOICE_PDF,
            source=AttachmentSource.LOCAL_FILE,
            source_reference="synthetic-evidence",
            mime_type="application/pdf",
            captured_at=datetime(2025, 1, 21, tzinfo=UTC),
            bucket_id=BUCKET_ID,
        ),
    )
    return attachment.attachment_id


def attach_attachment(ledger: Ledger, transaction_id: str, attachment_id: str, *, actor: str) -> None:
    attach_manual_transaction_evidence(
        bucket_id=BUCKET_ID,
        transaction_id=transaction_id,
        actor=actor,
        attachment_ids=(attachment_id,),
        ports=ledger.ports,
    )


def synthetic_invoice(number: str) -> Invoice:
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.RECEIVED,
            "bucket_id": BUCKET_ID,
            "invoice_number": number,
            "issued_at": NOW_DATE,
            "counterparty_name": "Synthetic Supplier",
            "counterparty_tax_id": "A58818501",
            "counterparty_country": "ES",
            "base_total": Decimal("100.00"),
            "iva_total": Decimal("21.00"),
            "grand_total": Decimal("121.00"),
            "currency": "EUR",
            "payment_status": PaymentStatus.PENDING,
            "lines": (
                InvoiceLine.model_validate(
                    {
                        "description": "synthetic expense",
                        "quantity": Decimal("1"),
                        "unit_price": Decimal("100.00"),
                        "subtotal": Decimal("100.00"),
                        "iva_rate": IvaRate.from_registry("RATE_21"),
                        "iva_amount": Decimal("21.00"),
                    },
                ),
            ),
        },
    )
