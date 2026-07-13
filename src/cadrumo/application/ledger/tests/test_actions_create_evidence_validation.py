"""Manual ledger transaction create tests for evidence validation failures."""

from __future__ import annotations

import pytest

from ._action_test_support import (
    _BUCKET_ID,
    _OTHER_BUCKET_ID,
    UTC,
    Attachment,
    AttachmentKind,
    AttachmentSource,
    AttachmentStore,
    Decimal,
    InvoiceCatalogue,
    InvoiceCatalogueRepository,
    ManualLedgerTransactionCommand,
    SecureObjectRepository,
    TransactionDirection,
    TransactionValidationError,
    _repositories,
    create_manual_transaction,
    date,
    datetime,
    hashlib,
    purchase_invoice,
    secure_objects,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

__all__ = ["secure_objects"]


def test_create_manual_transaction_rejects_missing_purchase_evidence(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    invoice_repository = InvoiceCatalogueRepository(objects=secure_objects)
    invoice_repository.save(InvoiceCatalogue())

    with pytest.raises(TransactionValidationError, match="purchase_invoice_evidence_id"):
        create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id=_BUCKET_ID,
                booked_date=date(2026, 5, 2),
                amount=Decimal("121.00"),
                direction=TransactionDirection.OUTGOING,
                description="material oficina",
                purchase_invoice_evidence_id="missing-purchase-evidence",
            ),
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            invoice_repository=invoice_repository,
            occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
        )

    assert transaction_repository.load().transactions == {}
    assert event_repository.load().events == {}


def test_create_manual_transaction_rejects_missing_attachment_manifest(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    objects = secure_objects

    with pytest.raises(TransactionValidationError, match="attachment_ids"):
        create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id=_BUCKET_ID,
                booked_date=date(2026, 5, 2),
                amount=Decimal("121.00"),
                direction=TransactionDirection.OUTGOING,
                description="material oficina",
                attachment_ids=("a" * 64,),
            ),
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            attachment_store=AttachmentStore(objects=objects),
            occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
        )

    assert transaction_repository.load().transactions == {}
    assert event_repository.load().events == {}


def test_create_manual_transaction_rejects_purchase_evidence_from_other_bucket(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    invoice_repository = InvoiceCatalogueRepository(objects=secure_objects)
    other_bucket_invoice = purchase_invoice().model_copy(update={"bucket_id": _OTHER_BUCKET_ID})
    invoice_repository.save(InvoiceCatalogue.from_invoices((other_bucket_invoice,)))

    with pytest.raises(TransactionValidationError, match="command bucket"):
        create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id=_BUCKET_ID,
                booked_date=date(2026, 5, 2),
                amount=Decimal("121.00"),
                direction=TransactionDirection.OUTGOING,
                description="material oficina",
                purchase_invoice_evidence_id=other_bucket_invoice.invoice_id,
            ),
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            invoice_repository=invoice_repository,
            occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
        )

    assert transaction_repository.load().transactions == {}
    assert event_repository.load().events == {}


def test_create_manual_transaction_rejects_attachment_from_other_bucket(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    objects = secure_objects
    store = AttachmentStore(objects=objects)
    body = b"%PDF-1.4\nother bucket evidence\n%%EOF"
    attachment_id = store.put_bytes(body)
    store.write_manifest(
        Attachment(
            attachment_id=attachment_id,
            kind=AttachmentKind.INVOICE_PDF,
            source=AttachmentSource.LOCAL_FILE,
            source_reference="other-bucket.pdf",
            sha256=hashlib.sha256(body).hexdigest(),
            mime_type="application/pdf",
            bytes_size=len(body),
            captured_at=datetime(2026, 5, 4, 9, 0, tzinfo=UTC),
            bucket_id=_OTHER_BUCKET_ID,
            captured_by="operator-B",
            source_command="aeat app ledger attach",
        ),
    )

    with pytest.raises(TransactionValidationError, match="command bucket"):
        create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id=_BUCKET_ID,
                booked_date=date(2026, 5, 2),
                amount=Decimal("121.00"),
                direction=TransactionDirection.OUTGOING,
                description="material oficina",
                attachment_ids=(attachment_id,),
            ),
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            attachment_store=store,
            occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
        )

    assert transaction_repository.load().transactions == {}
    assert event_repository.load().events == {}
