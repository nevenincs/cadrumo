"""Modelo 136 deadline rows open only for the quarters the profile declares.

Orden HAP/70/2013 art. 7 ties each Modelo 136 filing to the prizes cashed in
the natural quarter immediately before it, so each window requires the
profile's quarter set to include that window's own quarter.
"""

from __future__ import annotations

from datetime import date

import pytest

from ....core.modelo import Modelo
from ....core.period import Period
from ...calculations.registry.applicability import derive_modelo_applicability
from ...calculations.registry.applicability_models import ApplicabilityVerdict
from ...calculations.registry.irpf_income_categories import require_irpf_income_category
from ...calculations.registry.tests.authored_editions import filing_year_envelope
from ...calculations.registry.tests.published_authority import PublishedGovernedFactSource
from ...contribuyente.entity_type import require_entity_type
from ..engine import DeadlineEngine
from ..models import IVARegime, TaxpayerProfile

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]

_M136 = Modelo("136")
_YEAR = filing_year_envelope().horizon
_TODAY = date(_YEAR, 1, 2)


def _profile(**facts: object) -> TaxpayerProfile:
    return TaxpayerProfile.model_validate(
        {
            "tax_id": "X0001500M",
            "entity_type": require_entity_type("natural_person"),
            "irpf_income_categories": frozenset({require_irpf_income_category("actividad_economica")}),
            "iva_regime": IVARegime("GENERAL"),
            **facts,
        },
    )


def _m136_periods(profile: TaxpayerProfile, year: int) -> list[Period]:
    schedule = DeadlineEngine().compute(profile, year, today=_TODAY)
    return [obligation.period for obligation in schedule.obligations if obligation.modelo == _M136]


def test_a_declared_quarter_opens_exactly_its_own_window() -> None:
    profile = _profile(
        premio_loteria_gravamen_especial_sin_retencion=True,
        premio_loteria_gravamen_especial_trimestres=frozenset({f"{_YEAR}-1T"}),
    )

    assert _m136_periods(profile, _YEAR) == [Period.from_year_and_code(_YEAR, "1T")]
    assert (
        derive_modelo_applicability(profile, "136", reference_date=date(_TODAY.year, 12, 31)).verdict
        is ApplicabilityVerdict.APPLICABLE
    )


def test_a_wrong_quarter_opens_no_row_for_the_undeclared_quarter() -> None:
    profile = _profile(
        premio_loteria_gravamen_especial_sin_retencion=True,
        premio_loteria_gravamen_especial_trimestres=frozenset({f"{_YEAR}-2T"}),
    )

    periods = _m136_periods(profile, _YEAR)

    assert Period.from_year_and_code(_YEAR, "1T") not in periods
    assert periods == [Period.from_year_and_code(_YEAR, "2T")]


def test_a_quarter_of_another_year_opens_nothing_in_this_year() -> None:
    profile = _profile(
        premio_loteria_gravamen_especial_sin_retencion=True,
        premio_loteria_gravamen_especial_trimestres=frozenset({f"{_YEAR - 1}-4T"}),
    )

    assert _m136_periods(profile, _YEAR) == []
    assert _m136_periods(profile, _YEAR - 1) == [Period.from_year_and_code(_YEAR - 1, "4T")]


def test_yes_without_quarters_opens_no_row_and_stays_incomplete() -> None:
    profile = _profile(premio_loteria_gravamen_especial_sin_retencion=True)

    assert _m136_periods(profile, _YEAR) == []
    result = derive_modelo_applicability(profile, "136", reference_date=date(_TODAY.year, 12, 31))
    assert result.verdict is ApplicabilityVerdict.INCOMPLETE
    assert "Periodos sin declarar" in result.reason


def test_no_is_not_applicable_and_opens_no_row() -> None:
    profile = _profile(premio_loteria_gravamen_especial_sin_retencion=False)

    assert _m136_periods(profile, _YEAR) == []
    assert (
        derive_modelo_applicability(profile, "136", reference_date=date(_TODAY.year, 12, 31)).verdict
        is ApplicabilityVerdict.NOT_APPLICABLE
    )


def test_an_unanswered_profile_is_incomplete_and_opens_no_row() -> None:
    profile = _profile()

    assert _m136_periods(profile, _YEAR) == []
    assert (
        derive_modelo_applicability(profile, "136", reference_date=date(_TODAY.year, 12, 31)).verdict
        is ApplicabilityVerdict.INCOMPLETE
    )


@pytest.mark.parametrize("year", PublishedGovernedFactSource().supported_filing_years().years)
def test_every_supported_edition_follows_the_same_quarter_rule(year: int) -> None:
    profile = _profile(
        premio_loteria_gravamen_especial_sin_retencion=True,
        premio_loteria_gravamen_especial_trimestres=frozenset({f"{year}-3T", f"{year}-4T"}),
    )

    assert _m136_periods(profile, year) == [
        Period.from_year_and_code(year, "3T"),
        Period.from_year_and_code(year, "4T"),
    ]
