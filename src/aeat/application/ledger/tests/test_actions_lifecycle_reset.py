"""Manual ledger transaction reset lifecycle tests."""

from __future__ import annotations

import pytest

from ._action_test_support import (
    _BUCKET_ID,
    UTC,
    BucketEventType,
    Decimal,
    InvoiceCatalogue,
    InvoiceCatalogueRepository,
    ManualLedgerTransactionCommand,
    SecureObjectRepository,
    TransactionDirection,
    _repositories,
    create_manual_transaction,
    date,
    datetime,
    purchase_invoice,
    reset_ledger_catalogue,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_reset_ledger_catalogue_clears_bucket_when_unblocked_and_emits_event(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    invoice_repository = InvoiceCatalogueRepository(objects=secure_objects)
    purchase_evidence = purchase_invoice()
    invoice_repository.save(InvoiceCatalogue.from_invoices((purchase_evidence,)))
    first = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 2),
            amount=Decimal("25.00"),
            direction=TransactionDirection.OUTGOING,
            description="first reset row",
            purchase_invoice_evidence_id=purchase_evidence.invoice_id,
            idempotency_key="reset-first",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        invoice_repository=invoice_repository,
        occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
    )
    second = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 3),
            amount=Decimal("30.00"),
            direction=TransactionDirection.OUTGOING,
            description="second reset row",
            idempotency_key="reset-second",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 4, 9, 31, tzinfo=UTC),
    )
    invoice_repository.save(
        InvoiceCatalogue.from_invoices(
            (purchase_evidence.model_copy(update={"linked_transaction_ids": (first.ref.transaction_id,)}),),
        ),
    )

    report = reset_ledger_catalogue(
        bucket_id=_BUCKET_ID,
        actor="operator-A",
        reason="contaminated import batch",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        invoice_repository=invoice_repository,
        occurred_at=datetime(2026, 5, 5, 10, 0, tzinfo=UTC),
    )

    assert report.reset is True
    assert report.removed_transaction_ids == tuple(sorted((first.ref.transaction_id, second.ref.transaction_id)))
    assert report.cascaded_purchase_invoice_evidence_ids == (purchase_evidence.invoice_id,)
    assert transaction_repository.load().transactions == {}
    detached = invoice_repository.load().get(purchase_evidence.invoice_id)
    assert detached is not None
    assert detached.linked_transaction_ids == ()
    events = event_repository.load().for_bucket(_BUCKET_ID)
    assert [event.event_type for event in events] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED,
        BucketEventType.LEDGER_TRANSACTION_CREATED,
        BucketEventType.PURCHASE_INVOICE_EVIDENCE_DETACHED,
        BucketEventType.LEDGER_TRANSACTION_REMOVED,
        BucketEventType.LEDGER_TRANSACTION_REMOVED,
        BucketEventType.LEDGER_CATALOGUE_RESET,
    ]
    assert events[-1].event_type is BucketEventType.LEDGER_CATALOGUE_RESET
    assert events[-1].payload["removed_transaction_count"] == "2"
    assert events[-1].payload["reason"] == "contaminated import batch"


def test_reset_ledger_catalogue_clears_a_large_ledger_without_payload_overflow(
    secure_objects: SecureObjectRepository,
) -> None:
    """A reset on a realistic (10+ row) ledger must succeed and clear every row."""
    transaction_repository, event_repository = _repositories(secure_objects)
    row_count = 12
    created_ids: list[str] = []
    for index in range(row_count):
        created = create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id=_BUCKET_ID,
                booked_date=date(2026, 5, 1),
                amount=Decimal("10.00") + Decimal(index),
                direction=TransactionDirection.OUTGOING,
                description=f"bulk reset row {index}",
                idempotency_key=f"bulk-reset-{index}",
            ),
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            occurred_at=datetime(2026, 5, 4, 9, index, tzinfo=UTC),
        )
        created_ids.append(created.ref.transaction_id)

    assert len(transaction_repository.load().transactions) == row_count

    report = reset_ledger_catalogue(
        bucket_id=_BUCKET_ID,
        actor="operator-A",
        reason="bulk wipe",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 5, 10, 0, tzinfo=UTC),
    )

    assert report.reset is True
    assert report.removed_transaction_ids == tuple(sorted(created_ids))
    assert transaction_repository.load().transactions == {}
    reset_events = [
        event
        for event in event_repository.load().for_bucket(_BUCKET_ID)
        if event.event_type is BucketEventType.LEDGER_CATALOGUE_RESET
    ]
    assert len(reset_events) == 1
    assert reset_events[0].payload["removed_transaction_count"] == str(row_count)
    removed_events = [
        event
        for event in event_repository.load().for_bucket(_BUCKET_ID)
        if event.event_type is BucketEventType.LEDGER_TRANSACTION_REMOVED
    ]
    assert {event.object_id for event in removed_events} == set(created_ids)
