"""No modelo the calendar finds applicable is left without a deadline or a named open question.

The calendar reported Modelo 303 as "applicable, but Cadrumo has no filing
deadline" for a general-regime autónomo who had answered the four IVA setup
questions: the large-company condition (RIVA art. 71.3) decides the 303
cadence and was never asked, so neither the quarterly nor the monthly schedule
matched and the windows vanished. Every supported year is checked through the
real calendar build, before and after the condition is stated.
"""

from datetime import date

import pytest

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.deadlines.profiles import taxpayer_profile_from_mapping
from ..calendar import build_overview_calendar
from ..calendar_models import OverviewCalendar, OverviewCalendarRange
from ..coverage import CoverageAdviceReason

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_LARGE_COMPANY = "enrollment.large_company"
_FACTS: dict[str, object] = {
    "identity.tax_id": "12345678Z",
    "activities.description": "consultoría",
    "taxpayer_type.entity_type": "natural_person",
    "taxpayer_type.irpf_income_categories": "actividad_economica",
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


def _calendar(year: int, operation: PinnedAuthorityOperation, **extra: object) -> OverviewCalendar:
    values = {**_FACTS, **extra}
    return build_overview_calendar(
        taxpayer_profile_from_mapping(values, tax_id_default="12345678Z"),
        OverviewCalendarRange(from_date=date(year, 1, 1), to_date=date(year + 1, 1, 31)),
        operation=operation,
        today=date(year, 6, 1),
        raw_values=values,
    )


def _window_missing(calendar: OverviewCalendar) -> set[str]:
    return {
        item.modelo
        for item in calendar.coverage.advised
        if item.reason is CoverageAdviceReason.APPLICABLE_WINDOW_MISSING
    }


@pytest.mark.parametrize("year", _SUPPORTED_YEARS)
def test_a_stated_cadence_puts_every_303_quarter_on_the_calendar(
    year: int, authority_operation: PinnedAuthorityOperation
) -> None:
    calendar = _calendar(year, authority_operation, **{_LARGE_COMPANY: "false"})

    assert _window_missing(calendar) == set()
    quarters = {entry.period.registry_token for entry in calendar.entries if entry.modelo == "303"}
    assert quarters == {"1T", "2T", "3T", "4T"}


@pytest.mark.parametrize("year", _SUPPORTED_YEARS)
def test_an_unstated_cadence_names_the_question_instead_of_a_missing_deadline(
    year: int, authority_operation: PinnedAuthorityOperation
) -> None:
    calendar = _calendar(year, authority_operation)

    assert _window_missing(calendar) == set()
    assert "303" in calendar.coverage.advised_modelos
    question = next(warning for warning in calendar.warnings if warning.code == _LARGE_COMPANY)
    assert "303" in question.affected_modelos
