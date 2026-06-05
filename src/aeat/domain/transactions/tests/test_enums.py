"""Cardinality contracts for transaction-domain enums.

The transaction catalogue depends on a closed set of lifecycle states
and split-lineage roles. Asserting the exact membership here turns the
addition or removal of any member into an explicit, reviewable test
diff rather than silent drift through dependent code paths.
"""

from __future__ import annotations

import pytest

from .._enums import SplitRole, TransactionDirection, TransactionLifecycleState

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_transaction_direction_members_are_closed() -> None:
    assert set(TransactionDirection) == {
        TransactionDirection.INCOMING,
        TransactionDirection.OUTGOING,
        TransactionDirection.INTERNAL_TRANSFER,
    }


def test_transaction_lifecycle_state_members_are_closed() -> None:
    assert set(TransactionLifecycleState) == {
        TransactionLifecycleState.ACTIVE,
        TransactionLifecycleState.ARCHIVED,
        TransactionLifecycleState.STASHED,
        TransactionLifecycleState.SPLIT,
    }


def test_split_role_members_are_closed() -> None:
    assert set(SplitRole) == {SplitRole.PARENT, SplitRole.CHILD, SplitRole.MERGED}


def test_lifecycle_state_str_values_round_trip() -> None:
    for state in TransactionLifecycleState:
        assert TransactionLifecycleState(state.value) is state


def test_split_role_str_values_round_trip() -> None:
    for role in SplitRole:
        assert SplitRole(role.value) is role
