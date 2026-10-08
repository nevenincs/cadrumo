"""Parse operator-attested ``YYYY:PERIOD`` profile tokens into validated period keys."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Final

from ...core.period import Period, PeriodError

_TOKEN_RE: Final = re.compile(r"^(?P<year>\d{4}):(?P<period>[A-Z0-9]+)$")


def parse_attested_period_keys(
    raw: str | None,
    *,
    accepts: Callable[[Period], bool] | None = None,
) -> frozenset[tuple[int, str]]:
    """Return the ``(filing_year, registry_token)`` keys of every well-formed token in ``raw``.

    Tokens are comma, semicolon or whitespace separated. A malformed token, an
    unknown period, or a period the optional ``accepts`` predicate refuses
    attests nothing: parsing fails closed so an unclear declaration never
    suppresses a dependency or manufactures a zero.
    """
    if raw is None:
        return frozenset[tuple[int, str]]()
    periods: set[tuple[int, str]] = set()
    for token in re.split(r"[,;\s]+", raw.strip().upper()):
        match = _TOKEN_RE.fullmatch(token) if token else None
        if match is None:
            continue
        try:
            period = Period.from_year_and_code(int(match.group("year")), match.group("period"))
        except (PeriodError, ValueError):
            continue
        if accepts is not None and not accepts(period):
            continue
        periods.add((period.filing_year, period.registry_token))
    return frozenset(periods)
