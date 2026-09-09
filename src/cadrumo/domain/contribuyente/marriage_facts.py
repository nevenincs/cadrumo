"""Marriage-period predicates consumed by Modelo profile bindings."""

from __future__ import annotations

from datetime import date


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


__all__ = [
    "marriage_full_year",
    "marriage_month_start",
]
