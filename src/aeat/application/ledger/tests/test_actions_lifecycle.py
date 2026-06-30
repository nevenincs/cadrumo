"""Manual ledger transaction application tests split by workflow."""

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
    TransactionValidationError,
    _repositories,
    archive_manual_transaction,
    create_manual_transaction,
    date,
    datetime,
    stash_manual_transaction,
    update_manual_transaction,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_archive_manual_transaction_records_lifecycle_lineage_and_event(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 1),
            amount=Decimal("50.00"),
            direction=TransactionDirection.OUTGOING,
            description="wrong account import",
            idempotency_key="archive-row",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )

    archived = archive_manual_transaction(
        bucket_id=_BUCKET_ID,
        transaction_id=created.ref.transaction_id,
        actor="operator-A",
        reason="wrong account import",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    persisted = transaction_repository.load().get(created.ref.transaction_id)
    assert persisted is not None
    assert persisted.lifecycle_state is TransactionLifecycleState.ARCHIVED
    assert persisted.lifecycle_lineage[-1].previous_state is TransactionLifecycleState.ACTIVE
    assert persisted.lifecycle_lineage[-1].state is TransactionLifecycleState.ARCHIVED
    assert persisted.lifecycle_lineage[-1].reason == "wrong account import"
    assert persisted.lifecycle_lineage[-1].bucket_event_id == archived.bucket_event_ids[0]
    events = event_repository.load().for_bucket(_BUCKET_ID)
    assert [event.event_type for event in events] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED,
        BucketEventType.LEDGER_TRANSACTION_ARCHIVED,
    ]
    assert events[-1].payload["previous_lifecycle_state"] == "ACTIVE"
    assert events[-1].payload["lifecycle_state"] == "ARCHIVED"
    assert events[-1].payload["reason"] == "wrong account import"


def test_update_manual_transaction_rejects_archived_row_without_reactivating_it(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 1),
            amount=Decimal("50.00"),
            direction=TransactionDirection.OUTGOING,
            description="wrong account import",
            idempotency_key="archived-edit-refusal",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )
    archived = archive_manual_transaction(
        bucket_id=_BUCKET_ID,
        transaction_id=created.ref.transaction_id,
        actor="operator-A",
        reason="wrong account import",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    with pytest.raises(TransactionValidationError, match="can be edited"):
        update_manual_transaction(
            transaction_id=created.ref.transaction_id,
            command=ManualLedgerTransactionCommand(
                bucket_id=_BUCKET_ID,
                booked_date=date(2026, 5, 1),
                amount=Decimal("60.00"),
                direction=TransactionDirection.OUTGOING,
                description="attempt to edit archived row",
                actor="operator-B",
                source_command="aeat app ledger update",
            ),
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            occurred_at=datetime(2026, 5, 3, 10, 0, tzinfo=UTC),
        )

    persisted = transaction_repository.load().get(created.ref.transaction_id)
    assert persisted is not None
    assert persisted.lifecycle_state is TransactionLifecycleState.ARCHIVED
    assert persisted.lifecycle_lineage[-1].bucket_event_id == archived.bucket_event_ids[0]
    assert [event.event_type for event in event_repository.load().for_bucket(_BUCKET_ID)] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED,
        BucketEventType.LEDGER_TRANSACTION_ARCHIVED,
    ]


def test_stash_manual_transaction_records_lifecycle_lineage_and_event(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 1),
            amount=Decimal("50.00"),
            direction=TransactionDirection.OUTGOING,
            description="hold for later classification",
            idempotency_key="stash-row",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )

    stashed = stash_manual_transaction(
        bucket_id=_BUCKET_ID,
        transaction_id=created.ref.transaction_id,
        actor="operator-A",
        reason="needs supporting statement",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    persisted = transaction_repository.load().get(created.ref.transaction_id)
    assert persisted is not None
    assert persisted.lifecycle_state is TransactionLifecycleState.STASHED
    assert persisted.lifecycle_lineage[-1].state is TransactionLifecycleState.STASHED
    assert persisted.lifecycle_lineage[-1].bucket_event_id == stashed.bucket_event_ids[0]
    events = event_repository.load().for_bucket(_BUCKET_ID)
    assert [event.event_type for event in events] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED,
        BucketEventType.LEDGER_TRANSACTION_STASHED,
    ]
    assert events[-1].payload["lifecycle_state"] == "STASHED"


def test_archive_and_stash_refuse_invalid_lifecycle_transitions(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 1),
            amount=Decimal("50.00"),
            direction=TransactionDirection.OUTGOING,
            description="wrong account import",
            idempotency_key="archive-stash-refusal",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )
    archive_manual_transaction(
        bucket_id=_BUCKET_ID,
        transaction_id=created.ref.transaction_id,
        actor="operator-A",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    with pytest.raises(TransactionValidationError, match="already archived"):
        archive_manual_transaction(
            bucket_id=_BUCKET_ID,
            transaction_id=created.ref.transaction_id,
            actor="operator-A",
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            occurred_at=datetime(2026, 5, 3, 10, 0, tzinfo=UTC),
        )
    with pytest.raises(TransactionValidationError, match="cannot be stashed"):
        stash_manual_transaction(
            bucket_id=_BUCKET_ID,
            transaction_id=created.ref.transaction_id,
            actor="operator-A",
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            occurred_at=datetime(2026, 5, 3, 10, 0, tzinfo=UTC),
        )

    assert [event.event_type for event in event_repository.load().for_bucket(_BUCKET_ID)] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED,
        BucketEventType.LEDGER_TRANSACTION_ARCHIVED,
    ]


