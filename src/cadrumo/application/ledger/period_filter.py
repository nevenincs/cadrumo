"""Application-owned ledger period boundary.

The ledger accepts one strict AEAT token plus a separate year.  This resolver
belongs inward because both an interactive entrypoint and non-CLI consumers
need the same ``Period`` boundary.  Presentation adapters may translate
``LedgerPeriodValidationError`` into their own transport error, but may not
reimplement token acceptance.
"""

from __future__ import annotations

from functools import cache

from ...core.period import Period, PeriodError, StandardPeriodCode

__all__ = [
    "LedgerPeriodValidationError",
    "canonical_ledger_period",
    "ledger_period_accepted_tokens",
    "optional_canonical_ledger_period",
]


class LedgerPeriodValidationError(ValueError):
    """A ledger period token is not a span-shaped canonical AEAT period."""

    def __init__(self, *, raw: str, accepted_period_tokens: tuple[str, ...]) -> None:
        self.raw = raw
        self.accepted_period_tokens = accepted_period_tokens
        super().__init__(f"unrecognised ledger period token: {raw!r}")


def _ledger_aeat_token(token: str) -> str | None:
    """Return a normalized registry token accepted by the ledger, if any."""
    try:
        return StandardPeriodCode(token.strip().upper()).value
    except ValueError:
        return None


@cache
def ledger_period_accepted_tokens() -> tuple[str, ...]:
    """Return all registry tokens that resolve to a ledger date span."""
    accepted: list[str] = []
    for member in StandardPeriodCode:
        normalized = _ledger_aeat_token(member.value)
        if normalized is None:
            continue
        try:
            resolved = Period.from_year_and_code(2024, normalized)
        except PeriodError:
            continue
        if resolved.has_date_span():
            accepted.append(normalized)
    return tuple(accepted)


def canonical_ledger_period(period: str, *, year: int) -> Period:
    """Resolve one strict AEAT token and year into the canonical ``Period``."""
    if not period.strip():
        raise LedgerPeriodValidationError(
            raw=period,
            accepted_period_tokens=ledger_period_accepted_tokens(),
        )

    normalized = _ledger_aeat_token(period)
    if normalized is not None:
        try:
            resolved = Period.from_year_and_code(year, normalized)
        except PeriodError:
            resolved = None
        if resolved is not None and resolved.has_date_span():
            return resolved

    raise LedgerPeriodValidationError(
        raw=period,
        accepted_period_tokens=ledger_period_accepted_tokens(),
    )


def optional_canonical_ledger_period(period: str | None, *, year: int | None) -> Period | None:
    """Resolve an optional period/year pair, requiring year when period is present."""
    if period is None:
        return None
    if year is None:
        raise ValueError(f"ledger period {period.strip()!r} requires a year")
    return canonical_ledger_period(period, year=year)
