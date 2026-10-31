"""Seed content-addressed attachments and manual transactions for attachment-link tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from cadrumo.adapters.persistence.storage.attachment import AttachmentStore
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.ledger.models import ManualLedgerTransactionCommand
from cadrumo.domain.attachments.enums import AttachmentKind, AttachmentSource
from cadrumo.domain.attachments.service import (
    AttachmentBytesContent,
    AttachmentIngestionRequest,
    add_attachment,
)
from cadrumo.domain.transactions.enums import TransactionDirection

from .....application.ledger.tests.manual_transaction_support import create_manual_transaction
from .ledger_action_create_support import ledger_ports_for_test
from .ledger_action_persistence_support import BUCKET_ID, repositories

__all__ = ["attachment_store", "seed_attachment", "seed_manual_transaction"]


def attachment_store(secure_objects: SecureObjectRepository) -> AttachmentStore:
    return AttachmentStore(objects=secure_objects)


def seed_attachment(secure_objects: SecureObjectRepository, *, pdf_bytes: bytes, marker: bytes) -> str:
    """Store ``pdf_bytes + marker`` as an invoice PDF attachment and return its digest id."""
    attachment = add_attachment(
        attachment_store(secure_objects),
        content=AttachmentBytesContent(data=pdf_bytes + marker),
        request=AttachmentIngestionRequest(
            kind=AttachmentKind.INVOICE_PDF,
            source=AttachmentSource.LOCAL_FILE,
            source_reference="operator-evidence",
            mime_type="application/pdf",
            captured_at=datetime(2026, 8, 1, tzinfo=UTC),
            bucket_id=BUCKET_ID,
        ),
    )
    return attachment.attachment_id


def seed_manual_transaction(secure_objects: SecureObjectRepository, *, idempotency_key: str) -> str:
    """Create the 121.00 outgoing office-material transaction and return its id."""
    transaction_repository, event_repository = repositories(secure_objects)
    with ledger_ports_for_test(
        bucket_id=BUCKET_ID,
        objects=secure_objects,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        attachment_store=attachment_store(secure_objects),
    ) as ports:
        created = create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id=BUCKET_ID,
                booked_date=date(2026, 5, 1),
                amount=Decimal("121.00"),
                direction=TransactionDirection.OUTGOING,
                description="material oficina",
                idempotency_key=idempotency_key,
            ),
            ports=ports,
        )
    return created.transaction.transaction_id
