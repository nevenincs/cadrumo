"""Closes and domiciliation cutoffs of the retention returns (111, 115, 123), read from independent sources.

RIRPF art. 108.1 closes the monthly and quarterly periods on the twentieth day
of the month after them, and an inhabil close moves to the next business day
(Ley 39/2015 art. 30.5). A window's authored close is therefore checked
against the business-day shift the production resolver applies on the
holiday calendars the registry publishes.

A domiciliacion cutoff is a published fact that no rule reproduces (the
Calendario del Contribuyente moves it by practice, not only by the Anexo II
arithmetic), so it is read from the bundled Calendario of the year it falls in:
the general day is the fifteenth of the month after the period, and the
calendar lists the periods whose day moves. A cutoff in a year whose calendar is
not bundled is unknown. Neither expectation is read from the window under test.
"""

from __future__ import annotations

import json
import re
from datetime import date
from functools import cache
from typing import TYPE_CHECKING, Final

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.deadlines.effective_close import effective_filing_deadline

if TYPE_CHECKING:
    from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation

MONTHLY_PERIODS: Final = tuple(f"{month:02d}" for month in range(1, 13))
QUARTERLY_PERIODS: Final = ("1T", "2T", "3T", "4T")
RETENCION_PERIODS: Final = (*MONTHLY_PERIODS, *QUARTERLY_PERIODS)

_STATUTORY_CLOSE_DAY: Final = 20
_MONTHS_PER_YEAR: Final = 12
_MONTHS_PER_QUARTER: Final = 3


def statutory_close(filing_year: int, period: str) -> date:
    """The twentieth day of the month after a monthly or quarterly period of one exercise."""
    if period in MONTHLY_PERIODS:
        month = int(period) + 1
    else:
        month = QUARTERLY_PERIODS.index(period) * _MONTHS_PER_QUARTER + _MONTHS_PER_QUARTER + 1
    year = filing_year + (1 if month > _MONTHS_PER_YEAR else 0)
    return date(year, (month - 1) % _MONTHS_PER_YEAR + 1, _STATUTORY_CLOSE_DAY)


def expected_close(operation: PinnedAuthorityOperation, modelo: str, filing_year: int, period: str) -> date:
    """The statutory close after the national business-day shift; the nominal day where no calendar is published."""
    return effective_filing_deadline(statutory_close(filing_year, period), modelo=modelo, operation=operation).closes_on


_MONTH_NAMES: Final = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)
_GENERAL_CUTOFF_DAY: Final = 15
_MONTHS = "|".join(_MONTH_NAMES)
_BLOCK_START: Final = "modelos 111, 115, 117"
_BLOCK_END: Final = "modelos 130 y 131"
_TABLE_ANCHOR: Final = "a continuacion, se indican los plazos"
_NUMBERED = re.compile(rf"(\d{{1,2}})([tm]) (\d{{2}}): 1 al (\d{{1,2}}) ?(?:de )?({_MONTHS})")
_NAMED = re.compile(rf"({_MONTHS})(?: (\d{{2}}))?:? 1 al (\d{{1,2}}) (?:de )?({_MONTHS})")
_ITEM = re.compile(f"{_NUMBERED.pattern}|{_NAMED.pattern}")
# A domiciliacion day never reaches the twentieth, where the presentation days of the same table begin.
_DOMICILIATION_LAST_DAY: Final = 17


def _calendar_path(calendar_year: int):
    return bundled_path(
        "manual_corpus_text",
        "aeat_official",
        "calendars",
        "files",
        f"calendario-contribuyente-{calendar_year}.pdf.corpus_text.json",
    )


def calendar_is_bundled(calendar_year: int) -> bool:
    """Whether the Calendario del Contribuyente of one year is part of the bundled corpus."""
    return _calendar_path(calendar_year).is_file()


@cache
def published_cutoff_exceptions(calendar_year: int) -> dict[tuple[int, str], date]:
    """The domiciliacion days one Calendario lists for the retention returns, by period.

    Reads the Anexo II table of the modelos 111, 115, 117, 123, 124, 126, 128 and
    216. A calendar either lists only the periods whose day moves or lists every
    period; both are returned as period to cutoff, and an unlisted period keeps
    the general day.
    """
    text = json.loads(_calendar_path(calendar_year).read_text(encoding="utf-8"))["normalised_text"]
    anchor = text.index(_TABLE_ANCHOR)
    start = text.index(_BLOCK_START, anchor)
    block = text[start : text.index(_BLOCK_END, start)]
    published: dict[tuple[int, str], date] = {}
    for found in _ITEM.finditer(block):
        numbered = _NUMBERED.fullmatch(found.group(0))
        if numbered is not None:
            ordinal, unit, short_year, day, month_name = numbered.groups()
            token = f"{int(ordinal):02d}" if unit == "m" else f"{ordinal}T"
            period_year = 2000 + int(short_year)
            last_month = int(ordinal) * (3 if unit == "t" else 1)
        else:
            named = _NAMED.fullmatch(found.group(0))
            assert named is not None
            period_name, short_year, day, month_name = named.groups()
            last_month = _MONTH_NAMES.index(period_name) + 1
            token = f"{last_month:02d}"
            period_year = 2000 + int(short_year) if short_year else calendar_year
        cutoff_month = _MONTH_NAMES.index(month_name) + 1
        cutoff_year = period_year + (1 if cutoff_month <= last_month else 0)
        if int(day) <= _DOMICILIATION_LAST_DAY and cutoff_month == last_month % 12 + 1:
            published[(period_year, token)] = date(cutoff_year, cutoff_month, int(day))
    return published


def expected_cutoff(filing_year: int, period: str) -> date | None:
    """The domiciliacion cutoff the bundled Calendario publishes for one period, or ``None`` when it is unpublished."""
    closes_on = statutory_close(filing_year, period)
    if not calendar_is_bundled(closes_on.year):
        return None
    cutoff = date(closes_on.year, closes_on.month, _GENERAL_CUTOFF_DAY)
    return published_cutoff_exceptions(closes_on.year).get((filing_year, period), cutoff)
