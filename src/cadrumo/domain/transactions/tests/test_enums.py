"""Cardinality contracts for transaction-domain enums.

The transaction catalogue depends on a closed set of lifecycle states
and split-lineage roles. Asserting the exact membership here turns the
addition or removal of any member into an explicit, reviewable test
diff rather than silent drift through dependent code paths.
"""

from __future__ import annotations

from enum import StrEnum

import pytest

from ..enums import SplitRole, TransactionDirection, TransactionLifecycleState

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_transaction_enum_contracts_are_closed_and_roundtrip() -> None:
    contracts: tuple[tuple[type[StrEnum], set[StrEnum]], ...] = (
        (
            TransactionDirection,
            {
                TransactionDirection.INCOMING,
                TransactionDirection.OUTGOING,
                TransactionDirection.INTERNAL_TRANSFER,
            },
        ),
        (
            TransactionLifecycleState,
            {
                TransactionLifecycleState.ACTIVE,
                TransactionLifecycleState.ARCHIVED,
                TransactionLifecycleState.STASHED,
                TransactionLifecycleState.SPLIT,
            },
        ),
        (SplitRole, {SplitRole.PARENT, SplitRole.CHILD, SplitRole.MERGED}),
    )

    for enum_cls, expected_members in contracts:
        assert set(enum_cls) == expected_members, enum_cls.__name__
        for member in enum_cls:
            assert enum_cls(member.value) is member, f"{enum_cls.__name__}.{member.name}"
