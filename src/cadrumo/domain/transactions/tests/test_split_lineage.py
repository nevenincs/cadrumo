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


@pytest.mark.parametrize(
    ("parent_transaction_id", "child_amounts", "child_narratives"),
    (
        (_CHILD_A, (Decimal("10.00"),), ("rent",)),
        (_PARENT, (Decimal("10.01"),), ("rent",)),
        (_PARENT, (Decimal("10.00"),), ("utilities",)),
    ),
)
def test_derive_split_group_id_differs_on_input_change(
    parent_transaction_id: str,
    child_amounts: tuple[Decimal, ...],
    child_narratives: tuple[str, ...],
) -> None:
    baseline = derive_split_group_id(
        parent_transaction_id=_PARENT,
        child_amounts=(Decimal("10.00"),),
        child_narratives=("rent",),
    )

    changed = derive_split_group_id(
        parent_transaction_id=parent_transaction_id,
        child_amounts=child_amounts,
        child_narratives=child_narratives,
    )
    assert baseline != changed


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


@pytest.mark.parametrize(
    ("split_group_id", "role", "sibling_transaction_ids", "expected_match"),
    (
        # split_group_id moved onto the shared Hex64Str identity type, so the
        # refusal is that type's pattern rather than a bespoke phrase. The pattern
        # still states the accepted shape, including the lower-case-only range,
        # which is what these two cases exist to prove.
        ("g" * 64, SplitRole.PARENT, (_CHILD_A,), r"\^\[0-9a-f\]\{64\}\$"),
        ("A" * 64, SplitRole.PARENT, (_CHILD_A,), r"\^\[0-9a-f\]\{64\}\$"),
        ("0" * 64, SplitRole.PARENT, (), "at least one sibling"),
        ("0" * 64, SplitRole.CHILD, (_CHILD_A, _CHILD_A), "unique"),
        ("0" * 64, SplitRole.CHILD, ("abc",), "64-character"),
    ),
)
def test_split_lineage_rejects_invalid_payloads(
    split_group_id: str,
    role: SplitRole,
    sibling_transaction_ids: tuple[str, ...],
    expected_match: str,
) -> None:
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
