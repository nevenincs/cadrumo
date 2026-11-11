"""Anti-double-count continuity invariant for the shared period boundary.

This proves the fully-closed ``[start, end]`` boundary is gap-free and overlap-free:
for every adjacent quarter pair and every adjacent month pair across at least two
years, ``prior.end_date + one day == next.start_date`` and no real calendar date is
contained by both periods.

The test is non-tautological: the *expected* boundary days are derived from the
:mod:`calendar` and :mod:`datetime` stdlib (the true first/last calendar day),
NOT by re-running the :class:`Period` boundary formula under test. A regression
that introduced a one-day overlap or gap in :meth:`Period.end_date` /
:meth:`Period.start_date` would fail here against the independent calendar oracle.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from itertools import pairwise

import pytest

from ....core.period import Period

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_YEARS = (2024, 2025, 2026)  # 2024 is a leap year: exercises Feb-29 month ends.
_QUARTER_TOKENS = ("1T", "2T", "3T", "4T")


def _quarter_period(year: int, quarter_index: int) -> Period:
    """Build the Period for quarter ``quarter_index`` (1-4) of ``year``."""
    return Period.from_year_and_code(year, f"{quarter_index}T")


def _month_period(year: int, month: int) -> Period:
    """Build the Period for ``month`` (1-12) of ``year``."""
    return Period.from_year_and_code(year, f"{month:02d}")


# --- Independent calendar oracle (does NOT call Period) -----------------------


def _calendar_quarter_bounds(year: int, quarter_index: int) -> tuple[date, date]:
    """Return (first, last) calendar dates of a quarter, computed from stdlib."""
    first_month = 3 * (quarter_index - 1) + 1
    last_month = first_month + 2
    last_day = calendar.monthrange(year, last_month)[1]
    return date(year, first_month, 1), date(year, last_month, last_day)


def _calendar_month_bounds(year: int, month: int) -> tuple[date, date]:
    """Return (first, last) calendar dates of a month, computed from stdlib."""
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


# --- Period bounds match the independent calendar oracle ----------------------


def test_quarter_bounds_match_calendar_oracle() -> None:
    """Period quarter start/end dates equal the stdlib-derived calendar bounds."""
    for year in _YEARS:
        for quarter_index in (1, 2, 3, 4):
            period = _quarter_period(year, quarter_index)
            expected_start, expected_end = _calendar_quarter_bounds(year, quarter_index)
            assert period.start_date == expected_start, (year, quarter_index)
            assert period.end_date == expected_end, (year, quarter_index)


def test_month_bounds_match_calendar_oracle() -> None:
    """Period month start/end dates equal the stdlib-derived calendar bounds."""
    for year in _YEARS:
        for month in range(1, 13):
            period = _month_period(year, month)
            expected_start, expected_end = _calendar_month_bounds(year, month)
            assert period.start_date == expected_start, (year, month)
            assert period.end_date == expected_end, (year, month)


# --- Continuity: no gap, no overlap between adjacent periods ------------------


def test_adjacent_quarters_are_gap_free_and_overlap_free() -> None:
    """Every adjacent quarter pair across the year span abuts with no gap/overlap.

    Walks Q1..Q4 within each year and across the year boundary (Q4->next Q1) so
    every consecutive quarter pair over ``_YEARS`` is covered.
    """
    quarters: list[tuple[int, int]] = [(year, q) for year in _YEARS for q in (1, 2, 3, 4)]
    for (prior_year, prior_q), (next_year, next_q) in pairwise(quarters):
        prior = _quarter_period(prior_year, prior_q)
        nxt = _quarter_period(next_year, next_q)

        # No gap, no overlap: the day after prior.end_date is exactly next.start_date.
        assert prior.end_date + timedelta(days=1) == nxt.start_date, (prior_year, prior_q, next_year, next_q)

        # No real date is contained by both periods (anti-double-count).
        assert not nxt.contains(prior.end_date)
        assert not prior.contains(nxt.start_date)


def test_adjacent_months_are_gap_free_and_overlap_free() -> None:
    """Every adjacent month pair across the year span abuts with no gap/overlap.

    Walks 01..12 within each year and across the year boundary (Dec->next Jan).
    """
    months: list[tuple[int, int]] = [(year, m) for year in _YEARS for m in range(1, 13)]
    for (prior_year, prior_m), (next_year, next_m) in pairwise(months):
        prior = _month_period(prior_year, prior_m)
        nxt = _month_period(next_year, next_m)

        assert prior.end_date + timedelta(days=1) == nxt.start_date, (prior_year, prior_m, next_year, next_m)
        assert not nxt.contains(prior.end_date)
        assert not prior.contains(nxt.start_date)


def test_quarter_covers_its_three_constituent_months_exactly() -> None:
    """A quarter's span equals the union of its three calendar months, no slop.

    Cross-checks the two granularities against each other: a quarter's start is
    its first month's start, its end is its third month's end, and every day of
    the three months is contained by the quarter while no day outside is.
    """
    for year in _YEARS:
        for quarter_index in (1, 2, 3, 4):
            quarter = _quarter_period(year, quarter_index)
            first_month = 3 * (quarter_index - 1) + 1
            constituent = [_month_period(year, first_month + offset) for offset in range(3)]

            assert quarter.start_date == constituent[0].start_date
            assert quarter.end_date == constituent[-1].end_date

            # Every constituent-month boundary day is inside the quarter.
            for month_period in constituent:
                assert quarter.contains(month_period.start_date)
                assert quarter.contains(month_period.end_date)

            # The day before the quarter and the day after are outside.
            assert not quarter.contains(quarter.start_date - timedelta(days=1))
            assert not quarter.contains(quarter.end_date + timedelta(days=1))
