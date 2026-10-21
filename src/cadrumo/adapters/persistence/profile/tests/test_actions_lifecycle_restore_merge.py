"""Restoring rows a merge archived must not count the same money twice."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.ledger.actions_lifecycle import archive_manual_transaction, restore_manual_transaction
from cadrumo.application.ledger.actions_split_merge import merge_transactions
from cadrumo.domain.buckets.event import BucketEventType
from cadrumo.domain.transactions.enums import TransactionLifecycleState
from cadrumo.domain.transactions.errors import TransactionValidationError

from ._merge_test_support import _BUCKET_ID, _repositories, _split_setup
from .ledger_action_create_support import ledger_ports_for_test

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def _merged_state(secure_objects: SecureObjectRepository):
    transaction_repository, event_repository = _repositories(secure_objects)
    parent, split = _split_setup(secure_objects, transaction_repository, event_repository)
    with ledger_ports_for_test(
        bucket_id=_BUCKET_ID,
        objects=secure_objects,
        bucket_event_repository=event_repository,
        transaction_repository=transaction_repository,
    ) as ports:
        merge = merge_transactions(
            bucket_id=_BUCKET_ID,
            child_transaction_ids=split.child_transaction_ids,
            actor="operator-A",
            ports=ports,
            occurred_at=datetime(2026, 5, 5, 9, 0, tzinfo=UTC),
        )
    return transaction_repository, event_repository, parent.ref.transaction_id, split, merge.merged_transaction_id


def _restore(secure_objects, transaction_repository, event_repository, transaction_id: str, *, day: int = 6) -> None:
    with ledger_ports_for_test(
        bucket_id=_BUCKET_ID,
        objects=secure_objects,
        bucket_event_repository=event_repository,
        transaction_repository=transaction_repository,
    ) as ports:
        restore_manual_transaction(
            bucket_id=_BUCKET_ID,
            transaction_id=transaction_id,
            actor="operator-B",
            ports=ports,
            occurred_at=datetime(2026, 5, day, 9, 0, tzinfo=UTC),
        )


def _archive(secure_objects, transaction_repository, event_repository, transaction_id: str, *, day: int = 6) -> None:
    with ledger_ports_for_test(
        bucket_id=_BUCKET_ID,
        objects=secure_objects,
        bucket_event_repository=event_repository,
        transaction_repository=transaction_repository,
    ) as ports:
        archive_manual_transaction(
            bucket_id=_BUCKET_ID,
            transaction_id=transaction_id,
            actor="operator-B",
            ports=ports,
            occurred_at=datetime(2026, 5, day, 9, 0, tzinfo=UTC),
        )


def test_restoring_a_child_a_merge_archived_is_refused_while_the_merged_row_is_active(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository, _, split, merged_id = _merged_state(secure_objects)
    child_id = split.child_transaction_ids[0]
    before_catalogue = transaction_repository.load()
    before_events = event_repository.load().for_bucket(_BUCKET_ID)

    with pytest.raises(TransactionValidationError, match=merged_id) as raised:
        _restore(secure_objects, transaction_repository, event_repository, child_id)

    assert raised.value.context is not None
    assert raised.value.context["transaction_ids"] == merged_id
    assert raised.value.context["transaction_id"] == child_id
    assert transaction_repository.load() == before_catalogue
    assert event_repository.load().for_bucket(_BUCKET_ID) == before_events
    persisted = transaction_repository.load().get(child_id)
    assert persisted is not None
    assert persisted.lifecycle_state is TransactionLifecycleState.ARCHIVED


def test_restoring_the_split_parent_a_merge_archived_is_refused_while_the_merged_row_is_active(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository, parent_id, _, merged_id = _merged_state(secure_objects)

    with pytest.raises(TransactionValidationError, match=merged_id):
        _restore(secure_objects, transaction_repository, event_repository, parent_id)

    persisted = transaction_repository.load().get(parent_id)
    assert persisted is not None
    assert persisted.lifecycle_state is TransactionLifecycleState.ARCHIVED


def test_originals_restore_once_the_merged_row_is_archived(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository, parent_id, split, merged_id = _merged_state(secure_objects)
    _archive(secure_objects, transaction_repository, event_repository, merged_id)

    for offset, original_id in enumerate((parent_id, *split.child_transaction_ids)):
        _restore(secure_objects, transaction_repository, event_repository, original_id, day=7 + offset)

    catalogue = transaction_repository.load()
    for original_id in (parent_id, *split.child_transaction_ids):
        restored = catalogue.get(original_id)
        assert restored is not None
        assert restored.lifecycle_state is TransactionLifecycleState.ACTIVE
    restored_events = [
        event
        for event in event_repository.load().for_bucket(_BUCKET_ID)
        if event.event_type is BucketEventType.LEDGER_TRANSACTION_RESTORED
    ]
    assert len(restored_events) == 3


def test_the_merged_row_is_not_restorable_beside_active_originals(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository, _, split, merged_id = _merged_state(secure_objects)
    child_id = split.child_transaction_ids[0]
    _archive(secure_objects, transaction_repository, event_repository, merged_id)
    _restore(secure_objects, transaction_repository, event_repository, child_id, day=7)

    with pytest.raises(TransactionValidationError, match=child_id):
        _restore(secure_objects, transaction_repository, event_repository, merged_id, day=8)

    persisted = transaction_repository.load().get(merged_id)
    assert persisted is not None
    assert persisted.lifecycle_state is TransactionLifecycleState.ARCHIVED


def test_a_child_archived_on_its_own_restores_when_its_group_was_never_merged(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    _, split = _split_setup(secure_objects, transaction_repository, event_repository)
    child_id = split.child_transaction_ids[0]
    _archive(secure_objects, transaction_repository, event_repository, child_id)

    _restore(secure_objects, transaction_repository, event_repository, child_id, day=7)

    persisted = transaction_repository.load().get(child_id)
    assert persisted is not None
    assert persisted.lifecycle_state is TransactionLifecycleState.ACTIVE
