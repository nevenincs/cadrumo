"""Shape and balance rules for base-imponible-negativa stock."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ..bin_carry_forward import BinCohortStock, BinStock
from ..errors import BinCohortShapeError


def _prior(year: int, opening: str, applied: str, future: str) -> BinCohortStock:
    return BinCohortStock(
        generation_year=year,
        pending_opening_amount=Decimal(opening),
        applied_amount=Decimal(applied),
        pending_future_amount=Decimal(future),
    )


def _current(year: int, opening: str) -> BinCohortStock:
    return BinCohortStock(
        generation_year=year,
        pending_opening_amount=Decimal(opening),
        pending_future_amount=Decimal(opening),
    )


def test_prior_cohort_legs_balance_and_totals_sum() -> None:
    stock = BinStock(
        filing_year=2025,
        cohorts=(
            _prior(2019, "1000", "400", "600"),
            _prior(2022, "500", "0", "500"),
            _current(2025, "250"),
        ),
    )

    assert stock.total_pending_opening_amount == Decimal("1750")
    assert stock.total_applied_amount == Decimal("400")
    assert stock.total_pending_future_amount == Decimal("1350")


def test_legs_that_do_not_balance_are_refused() -> None:
    with pytest.raises(BinCohortShapeError):
        _prior(2019, "1000", "400", "500")


def test_current_period_cohort_carries_no_applied_leg() -> None:
    cohort = _current(2025, "250")

    assert cohort.is_current_period_cohort
    assert cohort.applied_amount is None


def test_applying_the_current_period_cohort_is_refused() -> None:
    """LIS art. 26.1 compensates only losses from earlier periods.

    The detector tooth for the campaign's central distinction: a forbidden leg
    must be refused, not accepted as zero. If this passes, a value the law
    forbids can reach casilla [00547] and reduce the tax.
    """
    forbidden = BinCohortStock(
        generation_year=2025,
        pending_opening_amount=Decimal("250"),
        applied_amount=Decimal("100"),
        pending_future_amount=Decimal("150"),
    )

    with pytest.raises(BinCohortShapeError, match="current-period cohort"):
        BinStock(filing_year=2025, cohorts=(forbidden,))


def test_zero_applied_is_not_the_same_as_not_applicable() -> None:
    """A proven zero and a legally impossible leg must stay distinguishable."""
    applied_nothing = _prior(2022, "500", "0", "500")
    not_applicable = _current(2025, "250")

    assert applied_nothing.applied_amount == Decimal("0")
    assert not applied_nothing.is_current_period_cohort
    assert not_applicable.applied_amount is None
    assert not_applicable.is_current_period_cohort


def test_prior_cohort_omitting_its_applied_leg_is_refused() -> None:
    with pytest.raises(BinCohortShapeError, match="must state its applied_amount"):
        BinStock(filing_year=2025, cohorts=(_current(2019, "1000"),))


def test_cohort_generated_after_the_filing_year_is_refused() -> None:
    with pytest.raises(BinCohortShapeError, match="after the filing year"):
        BinStock(filing_year=2024, cohorts=(_current(2025, "100"),))


def test_duplicate_generation_years_are_refused() -> None:
    with pytest.raises(BinCohortShapeError, match="unique on generation_year"):
        BinStock(
            filing_year=2025,
            cohorts=(_prior(2019, "100", "0", "100"), _prior(2019, "200", "0", "200")),
        )


def test_negative_amounts_are_refused() -> None:
    with pytest.raises(ValueError):
        BinCohortStock(
            generation_year=2019,
            pending_opening_amount=Decimal("-1"),
            applied_amount=Decimal("0"),
            pending_future_amount=Decimal("-1"),
        )
