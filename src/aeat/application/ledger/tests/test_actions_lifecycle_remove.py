"""Manual ledger transaction removal lifecycle tests."""

from __future__ import annotations

import pytest

from ._action_test_support import (
    _BUCKET_ID,
    UTC,
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
    events = event_repository.load().for_bucket(_BUCKET_ID)
    assert [event.event_type for event in events] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED,
        BucketEventType.PURCHASE_INVOICE_EVIDENCE_DETACHED,
        BucketEventType.LEDGER_TRANSACTION_REMOVED,
    ]
    assert events[-1].payload["purchase_invoice_evidence_ids"] == purchase_evidence.invoice_id
    assert events[-1].payload["reason"] == "wrong account import"


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
