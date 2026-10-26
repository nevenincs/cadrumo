"""Stored quarter-set tokens for profile facts that name filing quarters.

A profile fact that lists quarters stores them as one string of
``|``-delimited ``YYYY-nT`` tokens (for example ``2025-1T|2025-3T``). Each
token is validated through :class:`~cadrumo.core.period.Period`, so only the
four ordinary quarters of a supported filing year are accepted, and the set is
re-emitted in one canonical order.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Final

from ...core.period import Period, PeriodError

QUARTER_SET_SEPARATOR: Final[str] = "|"
"""Delimiter between stored quarter tokens."""

_QUARTER_TOKEN: Final = re.compile(r"(?P<year>\d{4})-(?P<code>[1-4]T)")


def quarter_token(period: Period) -> str:
    """Return the stored ``YYYY-nT`` token for one ordinary quarter.

    Raises:
        ValueError: When ``period`` is not one of the four ordinary quarters.
    """
    if not period.is_quarterly:
        raise ValueError(f"period {period} is not an ordinary quarter")
    return f"{period.filing_year}-{period.registry_token}"


def parse_quarter_set(raw: str) -> frozenset[str] | None:
    """Parse a stored quarter set; a blank value is an undeclared set.

    Raises:
        ValueError: When a token is not ``YYYY-nT`` for an ordinary quarter of
            a supported filing year, or a token repeats.
    """
    stripped = raw.strip()
    if not stripped:
        return None
    tokens: list[str] = []
    for part in stripped.split(QUARTER_SET_SEPARATOR):
        match = _QUARTER_TOKEN.fullmatch(part.strip())
        if match is None:
            raise ValueError(f"quarter token {part.strip()!r} must have the form YYYY-nT, for example 2025-1T")
        try:
            period = Period.from_year_and_code(int(match.group("year")), match.group("code"))
        except PeriodError as exc:
            raise ValueError(f"quarter token {part.strip()!r} is not a supported filing quarter") from exc
        tokens.append(quarter_token(period))
    if len(set(tokens)) != len(tokens):
        raise ValueError(f"quarter set {raw!r} repeats a quarter")
    return frozenset(tokens)


def format_quarter_set(tokens: Iterable[str]) -> str:
    """Return the canonical stored string for a set of quarter tokens."""
    return QUARTER_SET_SEPARATOR.join(sorted(tokens))


__all__ = [
    "QUARTER_SET_SEPARATOR",
    "format_quarter_set",
    "parse_quarter_set",
    "quarter_token",
]
