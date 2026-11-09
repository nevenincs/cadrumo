"""Calendar shapes found by search, so a test names a weekday pattern and never a year.

A deadline scenario is worked by hand against a calendar shape: a close that
falls on a Sunday, a leap February that ends on a Tuesday, a 1 January on a
Monday. The shape recurs every few years, so these helpers walk forward from
the published support floor (or any starting year) to the first year that has
it. The scenario is then stated in terms of that year, and the hand-worked
dates stay true wherever the shape lands.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
from itertools import count

from ....core.filing_year import FOUR_DIGIT_YEAR_LAST
from ...calculations.registry.tests.authored_editions import filing_year_envelope
from ..festivos import Holiday, HolidayCalendar, HolidayJurisdiction

#: The statutory fixed national holidays, as (month, day); Viernes Santo moves with Easter.
_FIXED_NATIONAL_HOLIDAYS: tuple[tuple[int, int], ...] = (
    (1, 1),
    (1, 6),
    (5, 1),
    (8, 15),
    (10, 12),
    (11, 1),
    (12, 6),
    (12, 8),
    (12, 25),
)


def first_year_where(shape: Callable[[int], bool], *, start: int | None = None) -> int:
    """Return the first year from ``start`` (default the support floor) whose calendar has ``shape``."""
    for year in count(filing_year_envelope().floor if start is None else start):
        if year > FOUR_DIGIT_YEAR_LAST:
            break
        if shape(year):
            return year
    raise AssertionError("no year has the requested calendar shape")


def easter_sunday(year: int) -> date:
    """Return Easter Sunday of ``year`` (Gregorian computus of Meeus, Jones and Butcher)."""
    century, remainder = divmod(year, 100)
    leap_cycle = (century - century // 4 - (8 * century + 13) // 25 + 19 * (year % 19) + 15) % 30
    weekday_offset = (32 + 2 * (century % 4) + 2 * (remainder // 4) - leap_cycle - remainder % 4) % 7
    correction = (year % 19 + 11 * leap_cycle + 22 * weekday_offset) // 451
    month, day = divmod(leap_cycle + weekday_offset - 7 * correction + 114, 31)
    return date(year, month, day + 1)


def statutory_national_calendar(year: int, *extra_days: tuple[int, int]) -> HolidayCalendar:
    """Return a national calendar of the statutory fixed holidays, Viernes Santo and any ``extra_days``.

    Days that fall on a weekend are listed too: a walk skips weekends first, so
    they change no close. A Sunday holiday the State moves to the Monday is the
    one case this does not model.
    """
    good_friday = easter_sunday(year) - timedelta(days=2)
    days = {date(year, month, day) for month, day in (*_FIXED_NATIONAL_HOLIDAYS, *extra_days)} | {good_friday}
    return HolidayCalendar(
        year=year,
        boe_ref=f"test-national-{year}",
        national=tuple(
            Holiday(holiday_date=day, jurisdiction=HolidayJurisdiction.NATIONAL, name="fiesta") for day in sorted(days)
        ),
    )
