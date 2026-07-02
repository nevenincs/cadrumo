"""Contract tests for the :class:`SplitLineage` record and the
deterministic :func:`derive_split_group_id` helper.

These tests pin three properties:
- ``derive_split_group_id`` is content-addressed: identical inputs yield
  identical digests, and amount / narrative ordering is irrelevant.
- Different inputs (different parent id, different amount, different
  narrative) yield distinct digests.
- ``SplitLineage`` rejects malformed group ids, sibling ids, and the
  empty-sibling case.

We deliberately do not assert the digest equals a hand-computed SHA-256
of any concrete payload — that would re-implement the formula in the
test and provide no external authority. Equality and inequality between
two helper invocations is the structural property we own.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from .._enums import SplitRole
from .._models import SplitLineage, derive_split_group_id

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PARENT = "a" * 64
_CHILD_A = "b" * 64
_CHILD_B = "c" * 64


def test_derive_split_group_id_returns_lowercase_sha256() -> None:
    digest = derive_split_group_id(
        parent_transaction_id=_PARENT,
        child_amounts=(Decimal("10.00"), Decimal("15.00")),
        child_narratives=("rent", "utilities"),
    )

    assert len(digest) == 64
    assert digest == digest.lower()
    int(digest, 16)  # raises on non-hex


def test_derive_split_group_id_is_amount_order_independent() -> None:
    first = derive_split_group_id(
        parent_transaction_id=_PARENT,
        child_amounts=(Decimal("10.00"), Decimal("15.00")),
        child_narratives=("rent", "utilities"),
    )
    second = derive_split_group_id(
        parent_transaction_id=_PARENT,
        child_amounts=(Decimal("15.00"), Decimal("10.00")),
        child_narratives=("utilities", "rent"),
    )
    assert first == second


def test_derive_split_group_id_differs_on_input_change() -> None:
    baseline = derive_split_group_id(
        parent_transaction_id=_PARENT,
        child_amounts=(Decimal("10.00"),),
        child_narratives=("rent",),
    )
    cases: tuple[tuple[str, str, tuple[Decimal, ...], tuple[str, ...]], ...] = (
        ("parent", _CHILD_A, (Decimal("10.00"),), ("rent",)),
        ("amount", _PARENT, (Decimal("10.01"),), ("rent",)),
        ("narrative", _PARENT, (Decimal("10.00"),), ("utilities",)),
    )

    for label, parent_transaction_id, child_amounts, child_narratives in cases:
        changed = derive_split_group_id(
            parent_transaction_id=parent_transaction_id,
            child_amounts=child_amounts,
            child_narratives=child_narratives,
        )
        assert baseline != changed, label


def test_split_lineage_constructs_parent_role() -> None:
    digest = derive_split_group_id(
        parent_transaction_id=_PARENT,
        child_amounts=(Decimal("10.00"), Decimal("15.00")),
        child_narratives=("rent", "utilities"),
    )
    lineage = SplitLineage(
        split_group_id=digest,
        role=SplitRole.PARENT,
        sibling_transaction_ids=(_CHILD_A, _CHILD_B),
    )

    assert lineage.role is SplitRole.PARENT
    assert lineage.sibling_transaction_ids == (_CHILD_A, _CHILD_B)  # sorted


def test_split_lineage_rejects_invalid_payloads() -> None:
    cases: tuple[tuple[str, str, SplitRole, tuple[str, ...], str], ...] = (
        ("non-hex-group-id", "g" * 64, SplitRole.PARENT, (_CHILD_A,), "lowercase hex"),
        ("uppercase-group-id", "A" * 64, SplitRole.PARENT, (_CHILD_A,), "lowercase"),
        ("empty-siblings", "0" * 64, SplitRole.PARENT, (), "at least one sibling"),
        ("duplicate-siblings", "0" * 64, SplitRole.CHILD, (_CHILD_A, _CHILD_A), "unique"),
        ("short-sibling-id", "0" * 64, SplitRole.CHILD, ("abc",), "64-character"),
    )

    for _label, split_group_id, role, sibling_transaction_ids, expected_match in cases:
        with pytest.raises(ValidationError, match=expected_match):
            SplitLineage(
                split_group_id=split_group_id,
                role=role,
                sibling_transaction_ids=sibling_transaction_ids,
            )


def test_split_lineage_sorts_sibling_ids() -> None:
    digest = "0" * 64
    lineage = SplitLineage(
        split_group_id=digest,
        role=SplitRole.CHILD,
        sibling_transaction_ids=(_CHILD_B, _CHILD_A),
    )
    assert lineage.sibling_transaction_ids == (_CHILD_A, _CHILD_B)
