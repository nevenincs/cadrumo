"""Tests for deterministic split child-amount derivation."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ..evidence_split import derive_child_amounts

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_two_way_split_sums_to_parent() -> None:
    parent_amount = Decimal("121.00")
    amounts = derive_child_amounts(parent_amount, [Decimal("0.6"), Decimal("0.4")])
    assert amounts == (Decimal("72.60"), Decimal("48.40"))
    assert sum(amounts) == parent_amount


def test_three_way_split_remainder_lands_on_last_child() -> None:
    amounts = derive_child_amounts(Decimal("100.00"), [Decimal("0.333"), Decimal("0.333"), Decimal("0.334")])
    assert sum(amounts) == Decimal("100.00")
    # First two round to 33.30; the remainder absorbs the rest on the last child.
    assert amounts[0] == round(amounts[0], 2)
    assert amounts[-1] == Decimal("100.00") - amounts[0] - amounts[1]


def test_negative_gross_rejected() -> None:
    with pytest.raises(ValueError, match="non-negative magnitude"):
        derive_child_amounts(Decimal("-50.00"), [Decimal("0.5"), Decimal("0.5")])


def test_single_child_is_the_whole_gross() -> None:
    # The no-split verdict: one child at proportion 1.0 receives the whole gross.
    assert derive_child_amounts(Decimal("10.00"), [Decimal("1.0")]) == (Decimal("10.00"),)


def test_empty_proportions_rejected() -> None:
    with pytest.raises(ValueError, match="at least one child"):
        derive_child_amounts(Decimal("10.00"), [])
