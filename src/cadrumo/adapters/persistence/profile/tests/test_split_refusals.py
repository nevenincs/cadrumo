"""Refusal paths for the split_transaction action."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.adapters.persistence.profile.tests.ledger_action_create_support import ledger_ports_for_test
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.ledger.actions_lifecycle import archive_manual_transaction
from cadrumo.application.ledger.actions_split_merge import split_transaction
from cadrumo.application.ledger.models import SplitChildCommand
from cadrumo.domain.transactions.errors import TransactionValidationError

from ._split_test_support import _BUCKET_ID, _create_parent, _repositories

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def test_split_refuses_non_active_parent(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    parent_result = _create_parent(secure_objects, transaction_repository, event_repository)
    with ledger_ports_for_test(
        bucket_id=_BUCKET_ID,
        objects=secure_objects,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    ) as ports:
        archive_manual_transaction(
            bucket_id=_BUCKET_ID,
            transaction_id=parent_result.ref.transaction_id,
            actor="operator-A",
            source_command="aeat app ledger archive",
            ports=ports,
        )
    with pytest.raises(TransactionValidationError, match="only active"):
        with ledger_ports_for_test(
            bucket_id=_BUCKET_ID,
            objects=secure_objects,
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
        ) as ports:
            split_transaction(
                bucket_id=_BUCKET_ID,
                transaction_id=parent_result.ref.transaction_id,
                children=(
                    SplitChildCommand(amount=Decimal("60.00"), description="a"),
                    SplitChildCommand(amount=Decimal("40.00"), description="b"),
                ),
                actor="operator-A",
                ports=ports,
            )


def test_split_refuses_sum_mismatch(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    parent_result = _create_parent(secure_objects, transaction_repository, event_repository)
    with pytest.raises(TransactionValidationError, match="sum to the parent amount exactly"):
        with ledger_ports_for_test(
            bucket_id=_BUCKET_ID,
            objects=secure_objects,
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
        ) as ports:
            split_transaction(
                bucket_id=_BUCKET_ID,
                transaction_id=parent_result.ref.transaction_id,
                children=(
                    SplitChildCommand(amount=Decimal("60.00"), description="a"),
                    SplitChildCommand(amount=Decimal("50.00"), description="b"),
                ),
                actor="operator-A",
                ports=ports,
            )


def test_split_refuses_single_child(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    parent_result = _create_parent(secure_objects, transaction_repository, event_repository)
    with pytest.raises(TransactionValidationError, match="at least two children"):
        with ledger_ports_for_test(
            bucket_id=_BUCKET_ID,
            objects=secure_objects,
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
        ) as ports:
            split_transaction(
                bucket_id=_BUCKET_ID,
                transaction_id=parent_result.ref.transaction_id,
                children=(SplitChildCommand(amount=Decimal("100.00"), description="only one"),),
                actor="operator-A",
                ports=ports,
            )


def test_split_refuses_negative_magnitude_child(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    parent_result = _create_parent(secure_objects, transaction_repository, event_repository)
    with pytest.raises(TransactionValidationError, match="non-negative magnitude"):
        with ledger_ports_for_test(
            bucket_id=_BUCKET_ID,
            objects=secure_objects,
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
        ) as ports:
            split_transaction(
                bucket_id=_BUCKET_ID,
                transaction_id=parent_result.ref.transaction_id,
                children=(
                    SplitChildCommand(amount=Decimal("-30.00"), description="a"),
                    SplitChildCommand(amount=Decimal("130.00"), description="b"),
                ),
                actor="operator-A",
                ports=ports,
            )


def test_split_refuses_zero_child_amount(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    parent_result = _create_parent(secure_objects, transaction_repository, event_repository)
    with pytest.raises(TransactionValidationError, match="must not be zero"):
        with ledger_ports_for_test(
            bucket_id=_BUCKET_ID,
            objects=secure_objects,
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
        ) as ports:
            split_transaction(
                bucket_id=_BUCKET_ID,
                transaction_id=parent_result.ref.transaction_id,
                children=(
                    SplitChildCommand(amount=Decimal("100.00"), description="a"),
                    SplitChildCommand(amount=Decimal("0.00"), description="b"),
                ),
                actor="operator-A",
                ports=ports,
            )
