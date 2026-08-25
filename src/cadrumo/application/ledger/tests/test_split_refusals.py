"""Refusal paths for the split_transaction action."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....domain.transactions import TransactionValidationError
from ..models import SplitChildCommand
from ..actions_lifecycle import archive_manual_transaction
from ..actions_split_merge import split_transaction
from ._split_test_support import _BUCKET_ID, _create_parent, _repositories

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_split_refuses_non_active_parent(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    parent_result = _create_parent(transaction_repository, event_repository)
    archive_manual_transaction(
        bucket_id=_BUCKET_ID,
        transaction_id=parent_result.ref.transaction_id,
        actor="operator-A",
        source_command="aeat app ledger archive",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    )
    with pytest.raises(TransactionValidationError, match="only active"):
        split_transaction(
            bucket_id=_BUCKET_ID,
            transaction_id=parent_result.ref.transaction_id,
            children=(
                SplitChildCommand(amount=Decimal("60.00"), description="a"),
                SplitChildCommand(amount=Decimal("40.00"), description="b"),
            ),
            actor="operator-A",
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
        )


def test_split_refuses_sum_mismatch(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    parent_result = _create_parent(transaction_repository, event_repository)
    with pytest.raises(TransactionValidationError, match="sum to the parent amount exactly"):
        split_transaction(
            bucket_id=_BUCKET_ID,
            transaction_id=parent_result.ref.transaction_id,
            children=(
                SplitChildCommand(amount=Decimal("60.00"), description="a"),
                SplitChildCommand(amount=Decimal("50.00"), description="b"),
            ),
            actor="operator-A",
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
        )


def test_split_refuses_single_child(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    parent_result = _create_parent(transaction_repository, event_repository)
    with pytest.raises(TransactionValidationError, match="at least two children"):
        split_transaction(
            bucket_id=_BUCKET_ID,
            transaction_id=parent_result.ref.transaction_id,
            children=(SplitChildCommand(amount=Decimal("100.00"), description="only one"),),
            actor="operator-A",
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
        )


def test_split_refuses_negative_magnitude_child(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    parent_result = _create_parent(transaction_repository, event_repository)
    with pytest.raises(TransactionValidationError, match="non-negative magnitude"):
        split_transaction(
            bucket_id=_BUCKET_ID,
            transaction_id=parent_result.ref.transaction_id,
            children=(
                SplitChildCommand(amount=Decimal("-30.00"), description="a"),
                SplitChildCommand(amount=Decimal("130.00"), description="b"),
            ),
            actor="operator-A",
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
        )


def test_split_refuses_zero_child_amount(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    parent_result = _create_parent(transaction_repository, event_repository)
    with pytest.raises(TransactionValidationError, match="must not be zero"):
        split_transaction(
            bucket_id=_BUCKET_ID,
            transaction_id=parent_result.ref.transaction_id,
            children=(
                SplitChildCommand(amount=Decimal("100.00"), description="a"),
                SplitChildCommand(amount=Decimal("0.00"), description="b"),
            ),
            actor="operator-A",
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
        )
