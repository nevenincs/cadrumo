"""Manual ledger transaction removal lifecycle tests."""

from __future__ import annotations

import pytest

from ._action_test_support import (
    _BUCKET_ID,
    UTC,
    Attachment,
    AttachmentKind,
    AttachmentSource,
    AttachmentStore,
    BucketEventType,
    BusinessClassification,
    Decimal,
    InvoiceCatalogue,
    InvoiceCatalogueRepository,
    ManualLedgerTransactionCommand,
    SecureObjectRepository,
    TransactionDirection,
    _create_manual_row,
    _repositories,
    create_manual_transaction,
    date,
    datetime,
    hashlib,
    purchase_invoice,
    remove_manual_transaction,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_remove_manual_transaction_deletes_row_detaches_purchase_evidence_and_emits_events(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    invoice_repository = InvoiceCatalogueRepository(objects=secure_objects)
    purchase_evidence = purchase_invoice()
    invoice_repository.save(InvoiceCatalogue.from_invoices((purchase_evidence,)))
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 2),
            amount=Decimal("121.00"),
            direction=TransactionDirection.OUTGOING,
            description="material oficina",
            business_classification=BusinessClassification.BUSINESS,
            category_id="office-supplies",
            purchase_invoice_evidence_id=purchase_evidence.invoice_id,
            idempotency_key="remove-linked-row",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        invoice_repository=invoice_repository,
        occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
    )
    invoice_repository.save(
        InvoiceCatalogue.from_invoices(
            (purchase_evidence.model_copy(update={"linked_transaction_ids": (created.ref.transaction_id,)}),),
        ),
    )

    removed = remove_manual_transaction(
        bucket_id=_BUCKET_ID,
        transaction_id=created.ref.transaction_id,
        actor="operator-A",
        reason="wrong account import",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        invoice_repository=invoice_repository,
        occurred_at=datetime(2026, 5, 5, 10, 0, tzinfo=UTC),
    )

    assert removed.removed is True
    assert removed.cascaded_purchase_invoice_evidence_ids == (purchase_evidence.invoice_id,)
    assert transaction_repository.load().transactions == {}
    detached = invoice_repository.load().get(purchase_evidence.invoice_id)
    assert detached is not None
    assert detached.linked_transaction_ids == ()
    # The detach and the removal share the same removal instant, so their
    # relative order is the content-addressed event_id tie-break
    # (bucket_event_order_key), not a meaningful contract — only membership
    # among the two same-instant events is.
    events = event_repository.load().for_bucket(_BUCKET_ID)
    assert events[0].event_type is BucketEventType.LEDGER_TRANSACTION_CREATED
    assert {event.event_type for event in events[1:]} == {
        BucketEventType.PURCHASE_INVOICE_EVIDENCE_DETACHED,
        BucketEventType.LEDGER_TRANSACTION_REMOVED,
    }
    events_by_type = {event.event_type: event for event in events}
    removal = events_by_type[BucketEventType.LEDGER_TRANSACTION_REMOVED]
    assert removal.payload["purchase_invoice_evidence_count"] == "1"
    assert removal.payload["attachment_count"] == "0"
    assert removal.payload["cascade_count"] == "1"
    assert removal.payload["reason"] == "wrong account import"
    # The detached id itself is carried by its own event, not by the summary.
    detachment = events_by_type[BucketEventType.PURCHASE_INVOICE_EVIDENCE_DETACHED]
    assert detachment.object_id == purchase_evidence.invoice_id


def test_remove_manual_transaction_dry_run_reports_without_mutation(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository, created = _create_manual_row(
        secure_objects,
        description="dry run row",
        idempotency_key="remove-dry-run",
    )

    report = remove_manual_transaction(
        bucket_id=_BUCKET_ID,
        transaction_id=created.ref.transaction_id,
        actor="operator-A",
        dry_run=True,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 5, 10, 0, tzinfo=UTC),
    )

    assert report.dry_run is True
    assert report.removed is False
    assert transaction_repository.load().get(created.ref.transaction_id) is not None
    assert [event.event_type for event in event_repository.load().for_bucket(_BUCKET_ID)] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED,
    ]


def _attachment(store: AttachmentStore, index: int) -> str:
    """Store one real attachment and return its content-addressed id."""
    body = f"%PDF-1.4\nreceipt {index}\n%%EOF".encode()
    attachment_id = store.put_bytes(body)
    store.write_manifest(
        Attachment(
            attachment_id=attachment_id,
            kind=AttachmentKind.INVOICE_PDF,
            source=AttachmentSource.LOCAL_FILE,
            source_reference=f"receipt-{index}.pdf",
            sha256=hashlib.sha256(body).hexdigest(),
            mime_type="application/pdf",
            bytes_size=len(body),
            captured_at=datetime(2026, 5, 4, 9, 0, tzinfo=UTC),
            bucket_id=_BUCKET_ID,
            captured_by="operator-A",
            source_command="aeat app ledger attach",
        ),
    )
    return attachment_id


def test_remove_manual_transaction_with_eight_attachments_can_construct_its_own_event(
    secure_objects: SecureObjectRepository,
) -> None:
    """A row carrying eight attachments must still be removable.

    Attachment ids are hex-64, so eight of them joined on commas is
    ``8 * 64 + 7 = 519`` characters, past the 500-character cap on a
    bucket-event payload value. Seven join to 454 and fit, which is why a
    payload that folded the whole id list into one slot passed every existing
    test and bricked removal only for rows with eight or more attachments --
    the row could not construct the event recording its own removal.

    The count and the per-attachment events carry the same information without
    a slot whose width grows with the data.
    """
    transaction_repository, event_repository = _repositories(secure_objects)
    store = AttachmentStore(objects=secure_objects)
    attachment_ids = tuple(_attachment(store, index) for index in range(8))

    # Premise guard: without this the test would silently stop exercising the
    # overflow if id widths ever changed, and would prove nothing.
    assert len(",".join(sorted(attachment_ids))) > 500

    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 2),
            amount=Decimal("121.00"),
            direction=TransactionDirection.OUTGOING,
            description="material oficina",
            business_classification=BusinessClassification.BUSINESS,
            category_id="office-supplies",
            attachment_ids=attachment_ids,
            idempotency_key="remove-eight-attachments",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        attachment_store=store,
        occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
    )

    removed = remove_manual_transaction(
        bucket_id=_BUCKET_ID,
        transaction_id=created.ref.transaction_id,
        actor="operator-A",
        reason="duplicate import",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 5, 10, 0, tzinfo=UTC),
    )

    assert removed.removed is True
    assert transaction_repository.load().transactions == {}
    # The removal summary and the per-attachment detach events share the same
    # removal instant, so their relative order is the content-addressed
    # event_id tie-break (bucket_event_order_key), not a positional contract.
    events = event_repository.load().for_bucket(_BUCKET_ID)
    removal = next(event for event in events if event.event_type is BucketEventType.LEDGER_TRANSACTION_REMOVED)
    assert removal.payload["cascade_count"] == "8"
    # No payload slot may carry the joined list, whatever it is named.
    assert all(len(value) <= 500 for value in removal.payload.values())
    # Every id stays recoverable: each has its own event in this same batch.
    detached = {event.object_id for event in events if event.event_type is BucketEventType.ATTACHMENT_REMOVED}
    assert detached == set(attachment_ids)
