"""The registry filing-date context agrees with the engine default and stays in the filing year."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from ....period import calculation_filing_date
from ..schema import RegistrySnapshot
from .authored_editions import filing_year_envelope
from .registry_filing_date_support import registry_filing_date

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]


@pytest.mark.parametrize("period", ("1T", "2T", "3T", "4T"))
def test_registry_filing_date_matches_the_engine_default_date_context(
    period: str,
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    """The date context this module supplies must equal the engine's own default.

    DISCRIMINATING for all four quarters: restoring the retired
    twentieth-of-the-following-month map fails every parametrisation
    (2025-04-20 != 2025-03-31, and so on through 4T).

    ``calculate_registry_snapshot`` defaults ``date_context["filing_period"]``
    to ``calculation_filing_date(snapshot.filing_period)``. A test that supplies
    the key by hand therefore has exactly one correct value — the one the engine
    would have chosen — and any other value silently selects date-aware registry
    brackets under a temporal context no production call can produce.

    The expected value is read from the loaded snapshot, not restated here, so
    this asserts agreement with the authority rather than a copied literal.
    """
    filing_year = filing_year_envelope().horizon
    snapshot = registry_snapshot("130", filing_year, period)
    assert snapshot.filing_period is not None, "M130 snapshot must carry a typed filing period"

    assert registry_filing_date(filing_year, period) == calculation_filing_date(snapshot.filing_period)


@pytest.mark.parametrize("period", ("1T", "2T", "3T", "4T"))
def test_registry_filing_date_stays_inside_the_filing_year(period: str) -> None:
    """A quarterly context must never fall in the following calendar year.

    DISCRIMINATING for 4T only, and SUPPORTING for 1T/2T/3T: the retired map
    kept those three inside the filing year and failed only on 4T, whose
    2026-01-20 crossed into the next year. The three passing parametrisations
    are context, not proof.

    Modelo 130's 4T payment cutoff and plazo voluntario close both land in
    January of the FOLLOWING year. Supplying either as the calculation date
    context moves a year-keyed registry bracket onto the wrong year's law for
    every 4T filing, which is the drift this module's date routing exists to
    prevent.
    """
    filing_year = filing_year_envelope().horizon

    assert registry_filing_date(filing_year, period).year == filing_year
