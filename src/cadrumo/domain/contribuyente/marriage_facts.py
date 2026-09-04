"""Helpers for persisting and reloading marriage_date as profile facts.

``marriage_date`` is stored as a single profile fact under
``renta_taxpayer.marriage_date``.  Three derived integer facts are
stored alongside it so the registry binding resolver can look them up
by a simple ``profile_key`` selector without a date-channel binding:

  renta_taxpayer.marriage_date           ISO-8601 date string
  renta_taxpayer.marriage_month_start    month int (1-12) when year == filing_year
  renta_taxpayer.marriage_month_end      12 (always, when married)
  renta_taxpayer.marriage_full_year      1 when date.year < filing_year, else 0

When ``marital_status != 2`` (CASADO) no marriage_date is stored.

The derived fact paths exposed here are consumed by registry bindings:
  renta-20XX-profile-marriage-month-start → casilla 0246
  renta-20XX-profile-marriage-month-end   → casilla 0247
  renta-20XX-profile-marriage-full-year   → casilla 0245
"""

from __future__ import annotations

from datetime import date

from ...core.errors.hierarchy import ProfileAnswerTypeError
from ...core.parsing.dates import parse_iso8601_date as _parse_iso8601_date

_MARRIAGE_DATE_PATH = "renta_taxpayer.marriage_date"
_MONTH_START_PATH = "renta_taxpayer.marriage_month_start"
_MONTH_END_PATH = "renta_taxpayer.marriage_month_end"
_FULL_YEAR_PATH = "renta_taxpayer.marriage_full_year"


def marriage_full_year(marriage_date: date, filing_year: int) -> bool:
    """True when the marriage predates the filing year (vigente todo el año)."""
    return marriage_date.year < filing_year


def marriage_month_start(marriage_date: date, filing_year: int) -> int | None:
    """Return the first month married in *filing_year*, or None when full-year.

    When the marriage occurred *before* the filing year the form's
    casilla 0246 is left at 1 (the standard primer-mes for a full-year
    marriage).  When the marriage occurred *during* the filing year the
    actual month is returned.  When the marriage occurred *after* the
    filing year (future date) None is returned and no fact is written.
    """
    if marriage_date.year < filing_year:
        return 1
    if marriage_date.year == filing_year:
        return marriage_date.month
    return None


def marriage_derived_facts(
    marriage_date: date,
    filing_year: int,
) -> list[tuple[str, str]]:
    """Return ``(path, canonical-value-string)`` pairs for all marriage facts.

    The caller converts these to
    :class:`domain.user_profile.values.UserProfileFact` records.  All
    four facts are always emitted when a marriage_date is present;
    downstream binding resolution ignores facts that no formula
    consumes.
    """
    facts: list[tuple[str, str]] = [
        (_MARRIAGE_DATE_PATH, marriage_date.isoformat()),
    ]
    full_year = marriage_full_year(marriage_date, filing_year)
    month_start = marriage_month_start(marriage_date, filing_year)
    if month_start is not None:
        facts.append((_FULL_YEAR_PATH, "1" if full_year else "0"))
        facts.append((_MONTH_START_PATH, str(month_start)))
        facts.append((_MONTH_END_PATH, "12"))
    return facts


def marriage_date_from_facts(facts: dict[str, str]) -> date | None:
    """Reconstruct the marriage date from a flat profile-fact dict.

    Returns None when ``renta_taxpayer.marriage_date`` is absent.
    """
    raw = facts.get(_MARRIAGE_DATE_PATH)
    if not raw:
        return None
    return _parse_iso8601_date(raw)


def parse_marriage_date_flag(raw: str) -> date:
    """Parse a ``--taxpayer-marriage-date YYYY-MM-DD`` flag value.

    Returns a validated :class:`datetime.date`.  Raises ``ValueError``
    on invalid ISO-8601 format.
    """
    stripped = raw.strip()
    try:
        result = _parse_iso8601_date(stripped)
    except ValueError as exc:
        raise ProfileAnswerTypeError(f"--taxpayer-marriage-date must be YYYY-MM-DD; got: {raw!r}") from exc
    if result is None:
        raise ProfileAnswerTypeError(f"--taxpayer-marriage-date must be YYYY-MM-DD; got: {raw!r}")
    return result


__all__ = [
    "marriage_date_from_facts",
    "marriage_derived_facts",
    "marriage_full_year",
    "marriage_month_start",
    "parse_marriage_date_flag",
]
