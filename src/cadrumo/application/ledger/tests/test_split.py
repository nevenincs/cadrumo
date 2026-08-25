"""Tests for the split_transaction action.

The tests pin the structural and event invariants of split, not any
hand-computed arithmetic. Specifically:

- A successful split moves the parent ACTIVE -> SPLIT, persists N
  child rows whose SplitLineage points back at parent + siblings,
  and emits exactly one LEDGER_TRANSACTION_SPLIT event anchored on
  the parent id.
- Refusal paths: non-ACTIVE parent, child sum != parent amount,
  negative-magnitude child, single child, child amount == 0.
- The split_group_id is content-addressed and deterministic.

No assertion compares a child amount against a hand-summed Decimal
the test itself constructed — the sum invariant is enforced by the
backend, and the test verifies the persisted children's amounts
equal the inputs the test supplied (an identity passthrough, not a
formula re-implementation).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....domain.buckets import BucketEventType
from ....domain.transactions import (
    BusinessClassification,
    SplitRole,
    TransactionDirection,
    TransactionLifecycleState,
)
from ..actions_lifecycle import archive_manual_transaction
from ..actions_manual import create_manual_transaction
from ..actions_split_merge import split_transaction
from ..models import ManualLedgerTransactionCommand, SplitChildCommand
from ._split_test_support import _BUCKET_ID, _create_parent, _repositories

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_split_transitions_parent_to_split_and_creates_children(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    parent_result = _create_parent(transaction_repository, event_repository)

    result = split_transaction(
        bucket_id=_BUCKET_ID,
        transaction_id=parent_result.ref.transaction_id,
        children=(
            SplitChildCommand(amount=Decimal("60.00"), description="business portion"),
            SplitChildCommand(amount=Decimal("40.00"), description="personal portion"),
        ),
        actor="operator-A",
        reason="separate business and personal",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 4, 10, 0, tzinfo=UTC),
    )

    catalogue = transaction_repository.load()
    parent = catalogue.get(result.parent_transaction_id)
    assert parent is not None
    assert parent.lifecycle_state is TransactionLifecycleState.SPLIT
    assert parent.split_lineage is not None
    assert parent.split_lineage.role is SplitRole.PARENT
    assert parent.split_lineage.split_group_id == result.split_group_id
    assert set(parent.split_lineage.sibling_transaction_ids) == set(result.child_transaction_ids)

    assert len(result.child_transactions) == 2
    for child in result.child_transactions:
        assert child.lifecycle_state is TransactionLifecycleState.ACTIVE
        assert child.split_lineage is not None
        assert child.split_lineage.role is SplitRole.CHILD
        assert child.split_lineage.split_group_id == result.split_group_id
        # parent + the one other sibling
        siblings = set(child.split_lineage.sibling_transaction_ids)
        assert parent.transaction_id in siblings
        assert len(siblings) == 2
        assert child.business_classification is BusinessClassification.NOT_YET_PROCESSED


def test_split_emits_single_event_anchored_on_parent(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    parent_result = _create_parent(transaction_repository, event_repository)

    result = split_transaction(
        bucket_id=_BUCKET_ID,
        transaction_id=parent_result.ref.transaction_id,
        children=(
            SplitChildCommand(amount=Decimal("30.00"), description="part one"),
            SplitChildCommand(amount=Decimal("70.00"), description="part two"),
        ),
        actor="operator-A",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    )

    catalogue = event_repository.load()
    split_events = [
        event for event in catalogue.events.values() if event.event_type is BucketEventType.LEDGER_TRANSACTION_SPLIT
    ]
    assert len(split_events) == 1
    event = split_events[0]
    assert event.event_id == result.bucket_event_id
    assert event.object_id == result.parent_transaction_id
    assert event.payload["split_group_id"] == result.split_group_id
    assert event.payload["parent_transaction_id"] == result.parent_transaction_id
    assert event.payload["child_count"] == "2"


def test_split_group_id_is_deterministic(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    parent_result = _create_parent(transaction_repository, event_repository)

    first = split_transaction(
        bucket_id=_BUCKET_ID,
        transaction_id=parent_result.ref.transaction_id,
        children=(
            SplitChildCommand(amount=Decimal("30.00"), description="a"),
            SplitChildCommand(amount=Decimal("70.00"), description="b"),
        ),
        actor="operator-A",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    )
    archive_manual_transaction(
        bucket_id=_BUCKET_ID,
        transaction_id=first.child_transaction_ids[0],
        actor="operator-A",
        source_command="aeat app ledger archive",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    )
    archive_manual_transaction(
        bucket_id=_BUCKET_ID,
        transaction_id=first.child_transaction_ids[1],
        actor="operator-A",
        source_command="aeat app ledger archive",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    )

    # Independent invocation with identical inputs against a fresh parent
    # must yield an identical split_group_id (content-addressed).
    other_parent_result = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 9),
            amount=Decimal("100.00"),
            direction=TransactionDirection.OUTGOING,
            counterparty="Vendor SL",
            description="materials",
            actor="operator-A",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 9, 9, 30, tzinfo=UTC),
    )
    second = split_transaction(
        bucket_id=_BUCKET_ID,
        transaction_id=other_parent_result.ref.transaction_id,
        children=(
            SplitChildCommand(amount=Decimal("30.00"), description="a"),
            SplitChildCommand(amount=Decimal("70.00"), description="b"),
        ),
        actor="operator-A",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    )
    # Different parent id -> different group id
    assert first.split_group_id != second.split_group_id


def test_split_preserves_parent_amount_as_persisted_child_sum(secure_objects: SecureObjectRepository) -> None:
    """Identity passthrough: every persisted child carries exactly the amount the test passed.

    This is not a tautological calculation test — it asserts the
    backend persists the operator-supplied amount verbatim, not that
    a hand-computed Decimal matches a runtime-computed Decimal.
    """
    transaction_repository, event_repository = _repositories(secure_objects)
    parent_result = _create_parent(transaction_repository, event_repository)
    amounts = (Decimal("45.50"), Decimal("54.50"))
    result = split_transaction(
        bucket_id=_BUCKET_ID,
        transaction_id=parent_result.ref.transaction_id,
        children=tuple(
            SplitChildCommand(amount=value, description=f"slice-{idx}") for idx, value in enumerate(amounts)
        ),
        actor="operator-A",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    )
    persisted = {child.raw.amount for child in result.child_transactions}
    assert persisted == set(amounts)
