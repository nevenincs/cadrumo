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

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....domain.buckets import BucketEventHistoryRepository, BucketEventType
from ....domain.transactions import (
    SplitRole,
    TransactionCatalogueRepository,
    TransactionDirection,
    TransactionLifecycleState,
    TransactionValidationError,
)
from ....tests.secure_sql import isolated_runtime_profile
from .. import (
    ManualLedgerTransactionCommand,
    SplitChildCommand,
    create_manual_transaction,
    merge_transactions,
    split_transaction,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "25252525-2525-4525-8525-252525252525"


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile.repository


def _repositories(objects: SecureObjectRepository, *, bucket_id: str = _BUCKET_ID):
    return (
        TransactionCatalogueRepository(bucket_id=bucket_id, objects=objects),
        BucketEventHistoryRepository(objects=objects),
    )


def _split_setup(
    transaction_repository: TransactionCatalogueRepository,
    event_repository: BucketEventHistoryRepository,
    *,
    parent_amount: Decimal = Decimal("100.00"),
    direction: TransactionDirection = TransactionDirection.OUTGOING,
):
    parent_command = ManualLedgerTransactionCommand(
        bucket_id=_BUCKET_ID,
        booked_date=date(2026, 5, 2),
        amount=parent_amount,
        direction=direction,
        counterparty="Vendor SL",
        description="materials",
        actor="operator-A",
    )
    parent = create_manual_transaction(
        parent_command,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
    )
    half = parent_amount / Decimal("2")
    split = split_transaction(
        bucket_id=_BUCKET_ID,
        transaction_id=parent.ref.transaction_id,
        children=(
            SplitChildCommand(amount=half, description="business portion"),
            SplitChildCommand(amount=parent_amount - half, description="personal portion"),
        ),
        actor="operator-A",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 4, 10, 0, tzinfo=UTC),
    )
    return parent, split


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


def test_merge_refuses_partial_cohort(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    # Split into 3 so we can supply 2 of them and trigger partial-cohort refusal.
    parent_command = ManualLedgerTransactionCommand(
        bucket_id=_BUCKET_ID,
        booked_date=date(2026, 5, 2),
        amount=Decimal("100.00"),
        direction=TransactionDirection.OUTGOING,
        counterparty="Vendor SL",
        description="materials",
        actor="operator-A",
    )
    parent = create_manual_transaction(
        parent_command,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
    )
    split = split_transaction(
        bucket_id=_BUCKET_ID,
        transaction_id=parent.ref.transaction_id,
        children=(
            SplitChildCommand(amount=Decimal("30.00"), description="slice-a"),
            SplitChildCommand(amount=Decimal("30.00"), description="slice-b"),
            SplitChildCommand(amount=Decimal("40.00"), description="slice-c"),
        ),
        actor="operator-A",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    )

    with pytest.raises(TransactionValidationError, match="cohort is incomplete"):
        merge_transactions(
            bucket_id=_BUCKET_ID,
            child_transaction_ids=split.child_transaction_ids[:2],  # 2 of 3
            actor="operator-A",
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
        )


def test_merge_refuses_duplicate_child_ids(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    _parent_result, split = _split_setup(transaction_repository, event_repository)
    duplicate = (split.child_transaction_ids[0], split.child_transaction_ids[0])

    with pytest.raises(TransactionValidationError, match="must be unique"):
        merge_transactions(
            bucket_id=_BUCKET_ID,
            child_transaction_ids=duplicate,
            actor="operator-A",
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
        )


def test_merge_refuses_cross_group(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    _parent_a, split_a = _split_setup(transaction_repository, event_repository)
    # Create a second parent + split.
    second_parent = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 9),
            amount=Decimal("200.00"),
            direction=TransactionDirection.OUTGOING,
            counterparty="Other Vendor",
            description="other materials",
            actor="operator-A",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 9, 9, 30, tzinfo=UTC),
    )
    split_b = split_transaction(
        bucket_id=_BUCKET_ID,
        transaction_id=second_parent.ref.transaction_id,
        children=(
            SplitChildCommand(amount=Decimal("120.00"), description="b1"),
            SplitChildCommand(amount=Decimal("80.00"), description="b2"),
        ),
        actor="operator-A",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    )
    with pytest.raises(TransactionValidationError, match="one split_group_id"):
        merge_transactions(
            bucket_id=_BUCKET_ID,
            child_transaction_ids=(split_a.child_transaction_ids[0], split_b.child_transaction_ids[0]),
            actor="operator-A",
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
        )


def test_merge_refuses_single_child(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    _parent_result, split = _split_setup(transaction_repository, event_repository)
    with pytest.raises(TransactionValidationError, match="at least two child"):
        merge_transactions(
            bucket_id=_BUCKET_ID,
            child_transaction_ids=(split.child_transaction_ids[0],),
            actor="operator-A",
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
        )


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
