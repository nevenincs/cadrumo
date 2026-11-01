"""Resolve the registry filing-period date context shared by cross-dependency tests."""

from __future__ import annotations

from datetime import date

from .....core.period import Period
from ....period import calculation_filing_date


def registry_filing_date(filing_year: int, period: str) -> date:
    """Resolve the calculation date context through the typed period authority.

    ``calculate_registry_snapshot`` documents ``date_context["filing_period"]``
    as the snapshot's typed calculation filing date, and defaults the key to
    ``calculation_filing_date(snapshot.filing_period)`` when a caller omits it.
    A test that supplies the key must therefore resolve it from the same
    authority, or a date-aware registry bracket is selected under a temporal
    context production would never produce.

    This is deliberately NOT the deadline authority's
    ``resolve_filing_window``. Three distinct dates exist for one Modelo 130
    quarter and only one of them is this key's contract: the payment cutoff
    (the 20th of the following month), the plazo voluntario close
    (weekend-adjusted, and 30 January for 4T), and the calculation filing
    period (the quarter end). ``date_context["filing_period"]`` is the third.
    """
    return calculation_filing_date(Period.from_year_and_code(filing_year, period))
