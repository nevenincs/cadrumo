"""The text shapes the year gate reads in every language: years, dates, periods and edition ids.

A year is four decimal digits of the filing century; a date, an instant, a
filing period and a revision id are text built around one. Both the Python
and the TypeScript reader match these shapes, so each has one definition here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

#: A year is written as these four digits. The shape is matched on the source
#: text, so ``0x2027``, ``2_027`` and ``2027.0`` are not years.
YEAR_SOURCE: Final[re.Pattern[str]] = re.compile(r"^20\d\d$")

#: Text that is exactly a year.
YEAR_TEXT: Final[re.Pattern[str]] = re.compile(r"^20\d\d$")
#: A year written somewhere inside a text.
YEAR_IN_TEXT: Final[re.Pattern[str]] = re.compile(r"(?<!\d)20\d\d(?!\d)")
_ISO_DATE_TEXT = re.compile(r"^20\d\d-\d\d-\d\d$")
_DAY = r"(?:0[1-9]|[12]\d|3[01])"
_MONTH = r"(?:0[1-9]|1[0-2])"
#: Text that is exactly a date or an instant of the filing century: an ISO
#: year-month, date or timestamp with or without seconds, fraction and offset,
#: or a day-first or slashed date.
DATE_TEXT: Final[re.Pattern[str]] = re.compile(
    rf"^(?:20\d\d-{_MONTH}(?:-{_DAY}(?:[T ](?:[01]\d|2[0-3])(?::[0-5]\d(?::[0-5]\d(?:[.,]\d+)?)?)?"
    rf"(?:Z|[+-]\d\d(?::?\d\d)?)?)?)?"
    rf"|{_DAY}[/.-]{_MONTH}[/.-]20\d\d|20\d\d/{_MONTH}/{_DAY})$"
)
#: The start of an f-string that writes a date of the filing century, such as ``f"2026-04-{day}"``.
DATE_TEXT_START: Final[re.Pattern[str]] = re.compile(rf"^20\d\d-{_MONTH}(?:-|$)")
_PERIOD_CODE_TEXT = r"(?:[1-4][TP]|0A|Q[1-4]|T[1-4]|EXT-[1-4]T|EVENT-\d+)"
#: Text that is exactly a filing period of the filing century: a year and a period
#: code (``1T``-``4T``, ``1P``-``4P``, ``0A``, ``EXT-1T``, ``EVENT-3``, and the
#: refused calendar spellings ``Q1``/``T1``) joined directly or by a dash, space,
#: underscore, colon, slash or dot, or a year and a month joined by a space,
#: underscore, colon or slash (``2026 03``; ``2026-03`` is already date text).
PERIOD_TEXT: Final[re.Pattern[str]] = re.compile(
    rf"^20\d\d(?:[-_ :/.]?{_PERIOD_CODE_TEXT}|[_ :/]{_MONTH})$", re.IGNORECASE
)
#: The start of a template that writes a period: a year and a period code, or a
#: year with at most a separator before the first interpolation (``f"2026-{code}"``).
_PERIOD_TEXT_START = re.compile(rf"^20\d\d[-_ :/.]?{_PERIOD_CODE_TEXT}(?![0-9A-Za-z])", re.IGNORECASE)
_YEAR_BEFORE_VALUE = re.compile(r"^20\d\d[-_ :/.]?$")
_EDITION_ID = re.compile(r"^20\d\d(?:-[0-9a-z]+)+$")
#: A revision id, or a revision path, written inside a text.
EDITION_IN_TEXT: Final[re.Pattern[str]] = re.compile(
    r"(?:revisions[/\\]20\d\d(?:-[0-9a-z]+)*)|\b20\d\d(?:-[0-9a-z]+)*-(?:y-siguientes|hasta-[0-9a-z-]+|desde-[0-9a-z-]+)\b"
)


@dataclass(frozen=True, slots=True, order=True)
class Finding:
    """One year written into code."""

    path: str
    line: int
    rule: str
    text: str


def is_edition_id(text: str) -> bool:
    """Whether ``text`` is a revision id: a year with a range, window or edition word after it."""
    if _ISO_DATE_TEXT.match(text):
        return False
    if not _EDITION_ID.match(text):
        return False
    rest = text[4:]
    return any(char.isalpha() for char in rest) or re.match(r"^-20\d\d$", rest) is not None


def starts_period(literal: str, *, followed_by_value: bool) -> bool:
    """Whether a template's first literal part starts writing a filing period."""
    return bool(_PERIOD_TEXT_START.match(literal)) or (followed_by_value and bool(_YEAR_BEFORE_VALUE.match(literal)))
