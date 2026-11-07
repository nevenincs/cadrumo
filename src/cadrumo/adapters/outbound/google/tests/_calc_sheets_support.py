from __future__ import annotations

from datetime import date

from .....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from .....domain.calculations.registry.tests.published_authority import published_snapshot


def modelo_130_first_quarter_snapshot():
    year = filing_year_envelope().horizon
    return published_snapshot("130", filing_year=year, period="1T", on=date(year, 4, 1))
