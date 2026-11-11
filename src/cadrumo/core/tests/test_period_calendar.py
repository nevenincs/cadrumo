"""The calendar questions the one period model answers: its periods, the period holding a day, neighbours and spans."""

from __future__ import annotations

from datetime import date

import pytest

from ..period import CALENDAR_PERIOD_KINDS, Period, PeriodError, PeriodKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_a_year_lists_only_the_periods_that_are_spans_of_days() -> None:
    codes = [period.code for period in Period.calendar_periods(1986)]

    assert codes == ["0A", "1T", "2T", "3T", "4T", *(f"{month:02d}" for month in range(1, 13))]
    assert all(period.has_date_span() for period in Period.calendar_periods(1986))
    assert [kind for kind in CALENDAR_PERIOD_KINDS] == [PeriodKind.ANNUAL, PeriodKind.QUARTERLY, PeriodKind.MONTHLY]


@pytest.mark.parametrize("year", [0, 999, 10000])
def test_a_year_not_written_with_four_digits_has_no_periods(year: int) -> None:
    with pytest.raises(PeriodError):
        Period.calendar_periods(year)


@pytest.mark.parametrize("kind", [PeriodKind.INSTALMENT, PeriodKind.EXTENDED])
def test_no_period_holds_a_day_by_a_cadence_that_is_not_a_span(kind: PeriodKind) -> None:
    with pytest.raises(PeriodError):
        Period.containing(date(1986, 5, 5), kind)


def test_a_day_before_the_first_writable_year_is_held_by_no_period() -> None:
    with pytest.raises(PeriodError):
        Period.containing(date(999, 12, 31), PeriodKind.ANNUAL)


@pytest.mark.parametrize("code", ["1P", "2P", "EXT-1T", "EVENT-3"])
def test_a_filing_event_cannot_be_stepped(code: str) -> None:
    with pytest.raises(PeriodError):
        Period.from_year_and_code(1986, code).shifted(1)


@pytest.mark.parametrize(
    ("year", "code", "steps", "expected"),
    [
        (1986, "1T", -5, (1984, "4T")),
        (1986, "4T", 9, (1989, "1T")),
        (1986, "03", -15, (1984, "12")),
        (1986, "03", 22, (1988, "01")),
        (1986, "0A", 0, (1986, "0A")),
        (1986, "0A", -26, (1960, "0A")),
    ],
)
def test_a_period_steps_by_many_of_its_own_size(year: int, code: str, steps: int, expected: tuple[int, str]) -> None:
    stepped = Period.from_year_and_code(year, code).shifted(steps)

    assert stepped is not None
    assert (stepped.filing_year, stepped.code) == expected


def test_stepping_beyond_the_writable_years_leaves_no_period() -> None:
    assert Period.from_year_and_code(1000, "0A").shifted(-1) is None
    assert Period.from_year_and_code(9999, "0A").shifted(1) is None


def test_a_span_that_ends_before_it_begins_is_held_by_no_period() -> None:
    with pytest.raises(PeriodError):
        Period.covering(date(1986, 3, 2), date(1986, 3, 1))
