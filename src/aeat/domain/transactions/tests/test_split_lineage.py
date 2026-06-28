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


def test_derive_split_group_id_differs_on_parent_change() -> None:
    first = derive_split_group_id(
        parent_transaction_id=_PARENT,
        child_amounts=(Decimal("10.00"),),
        child_narratives=("rent",),
    )
    second = derive_split_group_id(
        parent_transaction_id=_CHILD_A,
        child_amounts=(Decimal("10.00"),),
        child_narratives=("rent",),
    )
    assert first != second


def test_derive_split_group_id_differs_on_amount_change() -> None:
    first = derive_split_group_id(
        parent_transaction_id=_PARENT,
        child_amounts=(Decimal("10.00"),),
        child_narratives=("rent",),
    )
    second = derive_split_group_id(
        parent_transaction_id=_PARENT,
        child_amounts=(Decimal("10.01"),),
        child_narratives=("rent",),
    )
    assert first != second


def test_derive_split_group_id_differs_on_narrative_change() -> None:
    first = derive_split_group_id(
        parent_transaction_id=_PARENT,
        child_amounts=(Decimal("10.00"),),
        child_narratives=("rent",),
    )
    second = derive_split_group_id(
        parent_transaction_id=_PARENT,
        child_amounts=(Decimal("10.00"),),
        child_narratives=("utilities",),
    )
    assert first != second


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


def test_split_lineage_rejects_non_hex_group_id() -> None:
    with pytest.raises(ValidationError, match="lowercase hex"):
        SplitLineage(
            split_group_id="g" * 64,
            role=SplitRole.PARENT,
            sibling_transaction_ids=(_CHILD_A,),
        )


def test_split_lineage_rejects_uppercase_group_id() -> None:
    with pytest.raises(ValidationError, match="lowercase"):
        SplitLineage(
            split_group_id="A" * 64,
            role=SplitRole.PARENT,
            sibling_transaction_ids=(_CHILD_A,),
        )


def test_split_lineage_rejects_empty_siblings() -> None:
    digest = "0" * 64
    with pytest.raises(ValidationError, match="at least one sibling"):
        SplitLineage(
            split_group_id=digest,
            role=SplitRole.PARENT,
            sibling_transaction_ids=(),
        )


def test_split_lineage_rejects_duplicate_siblings() -> None:
    digest = "0" * 64
    with pytest.raises(ValidationError, match="unique"):
        SplitLineage(
            split_group_id=digest,
            role=SplitRole.CHILD,
            sibling_transaction_ids=(_CHILD_A, _CHILD_A),
        )


def test_split_lineage_rejects_short_sibling_id() -> None:
    digest = "0" * 64
    with pytest.raises(ValidationError, match="64-character"):
        SplitLineage(
            split_group_id=digest,
            role=SplitRole.CHILD,
            sibling_transaction_ids=("abc",),
        )


def test_split_lineage_sorts_sibling_ids() -> None:
    digest = "0" * 64
    lineage = SplitLineage(
        split_group_id=digest,
        role=SplitRole.CHILD,
        sibling_transaction_ids=(_CHILD_B, _CHILD_A),
    )
    assert lineage.sibling_transaction_ids == (_CHILD_A, _CHILD_B)
