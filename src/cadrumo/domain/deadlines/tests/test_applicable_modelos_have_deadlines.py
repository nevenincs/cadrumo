"""A general-regime IVA filer gets a Modelo 303 deadline, or is told which answer decides it.

The quarterly and monthly 303 schedules both read the large-company condition
(RIVA art. 71.3: monthly liquidation above the LIVA art. 121 volume). Before it
is stated, neither cadence matched and the windows vanished, so the calendar
reported 303 as applicable with no deadline. An unanswered cadence fact is
neither answer: every 303 window must then be undetermined and name it.

The quarterly closes are checked against the official calendar rule rather
than the registry's own dates: the self-assessment of a quarter is filed by the
20th of the following month, the fourth quarter's by 30 January (RIVA art.
71.4), and a close falling on a Saturday or Sunday moves to the next Monday.
"""

from datetime import date, timedelta

import pytest

from ...calculations.registry.tests.authored_editions import filing_year_envelope
from ..engine import DeadlineEngine
from ..models import TaxpayerProfile
from ..profiles import taxpayer_profile_from_mapping

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]

_LARGE_COMPANY = "enrollment.large_company"
_FACTS = {
    "identity.tax_id": "12345678Z",
    "activities.description": "consultoría",
    "tax_residence.jurisdiction_scope": "common_regime",
    "iva.regime": "GENERAL",
    "iva.m303_regime_composition": "general",
    "iva.roi_enrolled": "false",
    "iva.redeme_enrolled": "false",
    "iva.cash_accounting_regime_enrolled": "false",
    "iva.voluntary_sii_enrolled": "false",
    "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
}
_SUPPORTED_YEARS = tuple(range(filing_year_envelope().floor, filing_year_envelope().horizon + 1))


def _profile(**extra: str) -> TaxpayerProfile:
    return taxpayer_profile_from_mapping({**_FACTS, **extra}, tax_id_default="12345678Z")


def _next_weekday(day: date) -> date:
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


def _official_quarterly_closes(year: int) -> dict[str, date]:
    return {
        "1T": _next_weekday(date(year, 4, 20)),
        "2T": _next_weekday(date(year, 7, 20)),
        "3T": _next_weekday(date(year, 10, 20)),
        "4T": _next_weekday(date(year + 1, 1, 30)),
    }


@pytest.mark.parametrize("year", _SUPPORTED_YEARS)
def test_a_stated_small_company_files_303_quarterly_by_the_official_closes(year: int) -> None:
    schedule = DeadlineEngine().compute(_profile(**{_LARGE_COMPANY: "false"}), year, today=date(year, 6, 1))

    closes = {o.period.registry_token: o.closes_on for o in schedule.obligations if str(o.modelo) == "303"}

    assert closes == _official_quarterly_closes(year)
    assert not [item for item in schedule.undetermined if str(item.modelo) == "303"]


@pytest.mark.parametrize("year", _SUPPORTED_YEARS)
def test_a_stated_large_company_files_303_monthly(year: int) -> None:
    schedule = DeadlineEngine().compute(_profile(**{_LARGE_COMPANY: "true"}), year, today=date(year, 6, 1))

    periods = {o.period.registry_token for o in schedule.obligations if str(o.modelo) == "303"}

    assert periods
    assert all(token.isdigit() for token in periods)


@pytest.mark.parametrize("year", _SUPPORTED_YEARS)
def test_an_unanswered_large_company_leaves_every_303_window_undetermined_by_it(year: int) -> None:
    schedule = DeadlineEngine().compute(_profile(), year, today=date(year, 6, 1))

    undetermined = [item for item in schedule.undetermined if str(item.modelo) == "303"]

    assert not [o for o in schedule.obligations if str(o.modelo) == "303"]
    assert {item.period.registry_token for item in undetermined} >= set(_official_quarterly_closes(year))
    assert all(_LARGE_COMPANY in item.deciding_paths for item in undetermined)
