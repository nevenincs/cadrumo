"""Shift a date by whole calendar years, for legal periods counted *de fecha a fecha*.

Spanish tax provisions count several periods in whole years measured from a date:
the LGT art. 66 prescription horizon, and the LIRPF art. 23.2.c rehabilitation
window that admits a rehabilitation *finalizada en los dos años anteriores a la
fecha de la celebración del contrato*. Both mean the same arithmetic and neither
means a day count.

**A year is not 365 days, and the difference is not academic.** Two calendar years
are 731 days whenever the span contains a 29 February, so a 730-day approximation
falls one day short for roughly one date in four. The rehabilitation window shipped
that way and denied the 60 per cent reducción to filers whose rehabilitation
finished exactly two calendar years before the contract -- a taxpayer detriment
produced entirely by the unit, with every figure in the rule correct.

The leap day itself has no counterpart in a non-leap year, so a boundary landing on
29 February clamps to 28 February. That widens a backwards-looking window by one day
rather than narrowing it, which is the direction that cannot cost a taxpayer a right
they hold.
"""

from __future__ import annotations

from datetime import date

__all__ = ["shift_by_calendar_years"]


def shift_by_calendar_years[CalendarMoment: date](moment: CalendarMoment, years: int) -> CalendarMoment:
    """Return ``moment`` shifted by whole calendar years, preserving its type.

    Accepts a negative ``years`` to look backwards, which is how a lookback window
    expresses "the N years before this date" without any consumer subtracting days.

    Args:
        moment: The date or datetime to shift. The concrete type is preserved, so a
            datetime keeps its time and tzinfo.
        years: Whole calendar years to add; negative shifts backwards.

    Returns:
        The shifted moment, with a 29 February boundary clamped to 28 February when
        the target year is not a leap year.
    """
    try:
        return moment.replace(year=moment.year + years)
    except ValueError:
        return moment.replace(year=moment.year + years, month=2, day=28)
