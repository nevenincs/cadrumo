"""Manual ledger lifecycle refusal tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....domain.buckets.event import BucketEventType
from ....domain.transactions.enums import TransactionDirection, TransactionLifecycleState
from ....domain.transactions.errors import TransactionValidationError
from ..actions_lifecycle import archive_manual_transaction, stash_manual_transaction
from ..actions_manual import create_manual_transaction, update_manual_transaction
from ..models import ManualLedgerTransactionCommand
from .action_fixtures import (
    _BUCKET_ID,
    _repositories,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
__all__ = ["secure_objects"]


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
