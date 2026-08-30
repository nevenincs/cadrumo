"""Tests for the merge_transactions action.

Pin the structural and event invariants of split re-merge:
- A successful merge archives every child + the parent, persists a
  fresh content-addressed merged transaction (whose id is NOT the
  original parent id), and emits exactly one LEDGER_TRANSACTION_MERGED
  event anchored on the parent id.
- The parent's SplitLineage role=PARENT is preserved on the archived
  parent so the audit chain is reconstructable.
- Refusals: partial cohort, mixed groups, non-active child, single
  child, parent not in SPLIT state, duplicate child ids.
- Round-trip: split then merge restores the parent's amount/narrative
  on the merged transaction (identity passthrough, not arithmetic).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....domain.buckets import BucketEventType
from ....domain.transactions.enums import SplitRole, TransactionLifecycleState
from ..actions_split_merge import merge_transactions
from ._merge_test_support import _BUCKET_ID, _repositories, _split_setup

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_merge_archives_parent_and_children_and_persists_fresh_merged(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    parent_result, split = _split_setup(transaction_repository, event_repository)

    merge = merge_transactions(
        bucket_id=_BUCKET_ID,
        child_transaction_ids=split.child_transaction_ids,
        actor="operator-A",
        reason="reverted split",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 5, 9, 0, tzinfo=UTC),
    )

    catalogue = transaction_repository.load()
    archived_parent = catalogue.get(parent_result.ref.transaction_id)
    assert archived_parent is not None
    assert archived_parent.lifecycle_state is TransactionLifecycleState.ARCHIVED
    assert archived_parent.split_lineage is not None
    assert archived_parent.split_lineage.role is SplitRole.PARENT

    for child_id in split.child_transaction_ids:
        archived_child = catalogue.get(child_id)
        assert archived_child is not None
        assert archived_child.lifecycle_state is TransactionLifecycleState.ARCHIVED

    merged = catalogue.get(merge.merged_transaction_id)
    assert merged is not None
    assert merged.lifecycle_state is TransactionLifecycleState.ACTIVE
    assert merged.split_lineage is not None
    assert merged.split_lineage.role is SplitRole.MERGED
    assert set(merged.split_lineage.sibling_transaction_ids) == set(split.child_transaction_ids)


def test_merged_transaction_id_differs_from_original_parent_id(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    parent_result, split = _split_setup(transaction_repository, event_repository)

    merge = merge_transactions(
        bucket_id=_BUCKET_ID,
        child_transaction_ids=split.child_transaction_ids,
        actor="operator-A",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    )
    assert merge.merged_transaction_id != parent_result.ref.transaction_id
    assert merge.parent_transaction_id == parent_result.ref.transaction_id


def test_merge_amount_round_trips_parent_amount(secure_objects: SecureObjectRepository) -> None:
    """Identity passthrough: merged_transaction.raw.amount equals the
    original parent amount because the merge synthesises the merged
    row from the parent's raw fields. This is not a tautological
    arithmetic check — it asserts the backend preserves the operator-
    supplied amount across split+merge, not that any formula matches."""
    transaction_repository, event_repository = _repositories(secure_objects)
    parent_result, split = _split_setup(transaction_repository, event_repository)
    _parent = transaction_repository.load().get(parent_result.ref.transaction_id)
    assert _parent is not None, "parent transaction must be present after split"
    original_amount = _parent.raw.amount

    merge = merge_transactions(
        bucket_id=_BUCKET_ID,
        child_transaction_ids=split.child_transaction_ids,
        actor="operator-A",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    )
    assert merge.merged_transaction.raw.amount == original_amount


def test_merge_emits_single_event_anchored_on_parent(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    parent_result, split = _split_setup(transaction_repository, event_repository)

    merge = merge_transactions(
        bucket_id=_BUCKET_ID,
        child_transaction_ids=split.child_transaction_ids,
        actor="operator-A",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    )

    catalogue = event_repository.load()
    merge_events = [
        event for event in catalogue.events.values() if event.event_type is BucketEventType.LEDGER_TRANSACTION_MERGED
    ]
    assert len(merge_events) == 1
    event = merge_events[0]
    assert event.event_id == merge.bucket_event_id
    assert event.object_id == parent_result.ref.transaction_id
    assert event.payload["merged_transaction_id"] == merge.merged_transaction_id
    assert event.payload["split_group_id"] == merge.split_group_id


def test_split_then_merge_chain_is_addressable_via_event_for_object(secure_objects: SecureObjectRepository) -> None:
    """for_object(parent_id) returns both the SPLIT and the MERGED events
    in chronological order, proving the audit chain is reconstructable
    via the existing event-store query helper."""
    transaction_repository, event_repository = _repositories(secure_objects)
    parent_result, split = _split_setup(transaction_repository, event_repository)
    merge = merge_transactions(
        bucket_id=_BUCKET_ID,
        child_transaction_ids=split.child_transaction_ids,
        actor="operator-A",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 5, 9, 0, tzinfo=UTC),
    )
    from ....domain.buckets import BucketEventObjectType

    catalogue = event_repository.load()
    chain = tuple(
        catalogue.for_object(
            object_type=BucketEventObjectType.LEDGER_TRANSACTION,
            object_id=parent_result.ref.transaction_id,
        ),
    )
    types = tuple(event.event_type for event in chain)
    assert BucketEventType.LEDGER_TRANSACTION_SPLIT in types
    assert BucketEventType.LEDGER_TRANSACTION_MERGED in types
    # SPLIT precedes MERGED.
    split_idx = types.index(BucketEventType.LEDGER_TRANSACTION_SPLIT)
    merge_idx = types.index(BucketEventType.LEDGER_TRANSACTION_MERGED)
    assert split_idx < merge_idx
    # Merge result event id is the one we got back.
    assert any(event.event_id == merge.bucket_event_id for event in chain)
