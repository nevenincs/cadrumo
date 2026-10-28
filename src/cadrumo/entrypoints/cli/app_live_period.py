"""Parse AEAT live observation periods."""

from __future__ import annotations

import typer

from ...core.period import Period, PeriodError


def live_period_option(period: str | None, *, year: int) -> Period | None:
    """Parse an optional period for the selected year."""
    if period is None:
        return None
    try:
        return Period.from_year_and_code(year, period)
    except PeriodError as exc:
        raise typer.BadParameter(f"invalid AEAT period {period!r} for year {year}") from exc


def required_live_period_option(period: str, *, year: int) -> Period:
    """Parse a required period for the selected year."""
    parsed = live_period_option(period, year=year)
    if parsed is None:
        raise typer.BadParameter("--period is required")
    return parsed
