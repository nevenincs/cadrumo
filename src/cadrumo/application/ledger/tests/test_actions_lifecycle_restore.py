"""Manual ledger transaction restore lifecycle tests."""

from __future__ import annotations

import pytest

from ._action_test_support import (
    _BUCKET_ID,
    UTC,
    BucketEventType,
    Decimal,
    ManualLedgerTransactionCommand,
    SecureObjectRepository,
    TransactionDirection,
    TransactionLifecycleState,
    _repositories,
    archive_manual_transaction,
    create_manual_transaction,
    date,
    datetime,
    restore_manual_transaction,
    stash_manual_transaction,
    summarize_manual_transactions,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_restore_stashed_transaction_returns_it_to_active_with_event_and_lineage(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 1),
            amount=Decimal("50.00"),
            direction=TransactionDirection.OUTGOING,
            description="stashed by mistake",
            idempotency_key="restore-stash-row",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )
    stash_manual_transaction(
        bucket_id=_BUCKET_ID,
        transaction_id=created.ref.transaction_id,
        actor="operator-A",
        reason="needs supporting statement",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    stashed_summary = summarize_manual_transactions(bucket_id=_BUCKET_ID, transaction_repository=transaction_repository)
    assert stashed_summary.active_count == 0
    assert stashed_summary.stashed_count == 1

    restored = restore_manual_transaction(
        bucket_id=_BUCKET_ID,
        transaction_id=created.ref.transaction_id,
        actor="operator-B",
        reason="stashed by mistake",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 3, 9, 0, tzinfo=UTC),
    )

    persisted = transaction_repository.load().get(created.ref.transaction_id)
    assert persisted is not None
    assert persisted.lifecycle_state is TransactionLifecycleState.ACTIVE
    assert persisted.lifecycle_lineage[-1].previous_state is TransactionLifecycleState.STASHED
    assert persisted.lifecycle_lineage[-1].state is TransactionLifecycleState.ACTIVE
    assert persisted.lifecycle_lineage[-1].reason == "stashed by mistake"
    assert persisted.lifecycle_lineage[-1].bucket_event_id == restored.bucket_event_ids[0]

    restored_summary = summarize_manual_transactions(
        bucket_id=_BUCKET_ID,
        transaction_repository=transaction_repository,
    )
    assert restored_summary.active_count == 1
    assert restored_summary.stashed_count == 0

    events = event_repository.load().for_bucket(_BUCKET_ID)
    assert [event.event_type for event in events] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED,
        BucketEventType.LEDGER_TRANSACTION_STASHED,
        BucketEventType.LEDGER_TRANSACTION_RESTORED,
    ]
    assert events[-1].payload["previous_lifecycle_state"] == "STASHED"
    assert events[-1].payload["lifecycle_state"] == "ACTIVE"
    assert events[-1].payload["reason"] == "stashed by mistake"


def test_restore_archived_transaction_returns_it_to_active(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 1),
            amount=Decimal("72.50"),
            direction=TransactionDirection.OUTGOING,
            description="archived by mistake",
            idempotency_key="restore-archive-row",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )
    archive_manual_transaction(
        bucket_id=_BUCKET_ID,
        transaction_id=created.ref.transaction_id,
        actor="operator-A",
        reason="wrong row archived",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    restored = restore_manual_transaction(
        bucket_id=_BUCKET_ID,
        transaction_id=created.ref.transaction_id,
        actor="operator-B",
        reason="archived by mistake",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 3, 9, 0, tzinfo=UTC),
    )

    persisted = transaction_repository.load().get(created.ref.transaction_id)
    assert persisted is not None
    assert persisted.lifecycle_state is TransactionLifecycleState.ACTIVE
    assert persisted.lifecycle_lineage[-1].previous_state is TransactionLifecycleState.ARCHIVED
    assert persisted.lifecycle_lineage[-1].state is TransactionLifecycleState.ACTIVE
    assert persisted.lifecycle_lineage[-1].bucket_event_id == restored.bucket_event_ids[0]
    events = event_repository.load().for_bucket(_BUCKET_ID)
    assert [event.event_type for event in events] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED,
        BucketEventType.LEDGER_TRANSACTION_ARCHIVED,
        BucketEventType.LEDGER_TRANSACTION_RESTORED,
    ]
    assert events[-1].payload["previous_lifecycle_state"] == "ARCHIVED"
