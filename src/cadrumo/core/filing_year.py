"""The written shape of a year, and nothing about which years exist.

A year on a wire, a form or a persisted record is checked here for being
written with four digits, which refuses a transposed digit or an uninitialised
zero before either can reach revision resolution. Which years the product
serves is the registry's to say: the supported-filing-years declaration and the
canonical temporal selection decide that, projecting from the nearest authored
declaration. No carrier restates a bound of its own, and none here names a year.

Spanish-named fields on AEAT-facing schemas (``ejercicio``, ``año``) keep their
names and take this type; the alias bounds the value, it does not rename the
field.
"""

from __future__ import annotations

from typing import Annotated, Final

from pydantic import Field

YEAR_DIGITS: Final[int] = 4
"""How many digits a year is written with."""

FOUR_DIGIT_YEAR_FIRST: Final[int] = 10 ** (YEAR_DIGITS - 1)
"""The smallest number written with :data:`YEAR_DIGITS` digits."""

FOUR_DIGIT_YEAR_LAST: Final[int] = 10**YEAR_DIGITS - 1
"""The largest number written with :data:`YEAR_DIGITS` digits."""

FourDigitYear = Annotated[int, Field(ge=FOUR_DIGIT_YEAR_FIRST, le=FOUR_DIGIT_YEAR_LAST)]
"""A calendar year written with four digits."""

FilingYear = FourDigitYear
"""The year a declaration is filed for; its coverage belongs to the registry."""


def is_four_digit_year(value: int) -> bool:
    """Return whether ``value`` is written with four digits."""
    return FOUR_DIGIT_YEAR_FIRST <= value <= FOUR_DIGIT_YEAR_LAST


def four_digit_year_in(text: str) -> int | None:
    """Return the year ``text`` writes with four ASCII digits, or ``None``.

    Surrounding blanks are ignored. A sign, underscores and other scripts'
    digits are refused although ``int`` would accept them: none is a year an
    operator types.
    """
    stripped = text.strip()
    if len(stripped) != YEAR_DIGITS or not stripped.isascii() or not stripped.isdigit():
        return None
    return int(stripped)


__all__ = [
    "FOUR_DIGIT_YEAR_FIRST",
    "FOUR_DIGIT_YEAR_LAST",
    "YEAR_DIGITS",
    "FilingYear",
    "FourDigitYear",
    "four_digit_year_in",
    "is_four_digit_year",
]
