"""Tests for :class:`FiscalPeriod`."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from ._codes import Quarter
from ._period import FiscalPeriod

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


@pytest.mark.unit
def test_annual_period_spans_full_year() -> None:
    """A year-only period covers 1 Jan → 31 Dec."""
    period = FiscalPeriod(year=2024)
    assert period.start == date(2024, 1, 1)
    assert period.end == date(2024, 12, 31)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("quarter", "start_month", "start_day", "end_month", "end_day"),
    [
        (Quarter.Q1, 1, 1, 3, 31),
        (Quarter.Q2, 4, 1, 6, 30),
        (Quarter.Q3, 7, 1, 9, 30),
        (Quarter.Q4, 10, 1, 12, 31),
    ],
)
def test_quarter_spans_are_exact(
    quarter: Quarter,
    start_month: int,
    start_day: int,
    end_month: int,
    end_day: int,
) -> None:
    """Every quarter maps to the expected 3-month window."""
    period = FiscalPeriod(year=2024, quarter=quarter)
    assert period.start == date(2024, start_month, start_day)
    assert period.end == date(2024, end_month, end_day)


@pytest.mark.unit
def test_contains_boundary_dates() -> None:
    """The contains helper is inclusive on both ends."""
    period = FiscalPeriod(year=2025, quarter=Quarter.Q2)
    assert period.contains(date(2025, 4, 1)) is True
    assert period.contains(date(2025, 6, 30)) is True
    assert period.contains(date(2025, 3, 31)) is False
    assert period.contains(date(2025, 7, 1)) is False


@pytest.mark.unit
def test_year_out_of_range_rejected() -> None:
    """Years before 1990 or after 2100 fail validation."""
    with pytest.raises(ValidationError):
        FiscalPeriod(year=1989)
    with pytest.raises(ValidationError):
        FiscalPeriod(year=2101)
