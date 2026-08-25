"""Refusal paths for the merge_transactions action."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....domain.transactions import TransactionDirection, TransactionValidationError
from ..models import ManualLedgerTransactionCommand, SplitChildCommand
from ..actions_manual import create_manual_transaction
from ..actions_split_merge import merge_transactions, split_transaction
from ._merge_test_support import _BUCKET_ID, _repositories, _split_setup

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_merge_refuses_partial_cohort(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    # Split into 3 so supplying only 2 proves partial-cohort refusal.
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
            child_transaction_ids=split.child_transaction_ids[:2],
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
