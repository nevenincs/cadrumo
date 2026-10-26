"""Contract tests for the shared euro-cent and free-depreciation fact validation."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ..election import AmortizationMethod, require_euro_cents, require_free_depreciation_facts

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.mark.parametrize("value", [Decimal("0"), Decimal("1"), Decimal("12.34")])
def test_non_negative_cent_exact_amounts_are_accepted(value: Decimal) -> None:
    assert require_euro_cents(value, allow_zero=True) == value


@pytest.mark.parametrize("value", [Decimal("-0.01"), Decimal("1.005"), Decimal("NaN"), Decimal("Infinity")])
def test_negative_sub_cent_and_non_finite_amounts_are_refused(value: Decimal) -> None:
    with pytest.raises(ValueError, match="amount must be"):
        require_euro_cents(value, allow_zero=True)


def test_zero_is_refused_only_when_a_positive_amount_is_required() -> None:
    assert require_euro_cents(Decimal("0.01"), allow_zero=False) == Decimal("0.01")
    with pytest.raises(ValueError, match="claim amount must be a finite positive Decimal"):
        require_euro_cents(Decimal("0"), allow_zero=False, label="claim amount")


def test_low_value_method_requires_every_election_fact() -> None:
    facts = ("election", "evidence", Decimal("300"), Decimal("1000"))
    require_free_depreciation_facts(AmortizationMethod.LOW_VALUE_FREE, facts, subject="claim")
    for index in range(len(facts)):
        incomplete = tuple(None if position == index else fact for position, fact in enumerate(facts))
        with pytest.raises(ValueError, match="free-depreciation claim requires election and annual-cap provenance"):
            require_free_depreciation_facts(AmortizationMethod.LOW_VALUE_FREE, incomplete, subject="claim")


def test_other_methods_carry_no_election_facts() -> None:
    require_free_depreciation_facts(AmortizationMethod.LINEAR, (None, None, None, None), subject="schedule")
    with pytest.raises(ValueError, match="only a low-value schedule carries free-depreciation election facts"):
        require_free_depreciation_facts(AmortizationMethod.LINEAR, (None, "evidence", None, None), subject="schedule")
