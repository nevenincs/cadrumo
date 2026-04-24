"""Conversion from :class:`aeat.formulas.FiscalPeriod` to AEAT period strings.

The AEAT filing-history surface identifies periods with the
compact string form ``"2025-1T"`` / ``"2025-2T"`` / ... / ``"2025"``
(annual). :class:`aeat.formulas.FiscalPeriod` is the typed
representation every in-tree consumer already uses. This module
bridges the two so the fetchers under :mod:`aeat.remote.filings` can
accept a strongly-typed period and speak the AEAT surface on the wire
without re-hardcoding the format convention.
"""

from __future__ import annotations

from ...formulas import FiscalPeriod, Quarter

_QUARTER_TOKEN: dict[Quarter, str] = {
    Quarter.Q1: "1T",
    Quarter.Q2: "2T",
    Quarter.Q3: "3T",
    Quarter.Q4: "4T",
}


def format_aeat_period(period: FiscalPeriod) -> str:
    """Return the AEAT-wire string for ``period``.

    Args:
        period: A typed :class:`aeat.formulas.FiscalPeriod`.
            Quarterly periods render as ``"{year}-{q}T"``; annual
            periods (``period.quarter is None``) render as the bare
            year.

    Returns:
        The AEAT period string, e.g. ``"2025-1T"`` for Q1 2025 or
        ``"2025"`` for the full-year summary.
    """
    if period.quarter is None:
        return str(period.year)
    return f"{period.year}-{_QUARTER_TOKEN[period.quarter]}"


__all__ = ["format_aeat_period"]
