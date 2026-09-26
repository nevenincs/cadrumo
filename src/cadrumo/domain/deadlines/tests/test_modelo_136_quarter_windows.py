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
from ...calculations.registry.applicability import ApplicabilityVerdict, derive_modelo_applicability
from ...calculations.registry.irpf_income_categories import require_irpf_income_category
from ...contribuyente.entity_type import require_entity_type
from ..engine import DeadlineEngine
from ..models import IVARegime, TaxpayerProfile

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]

_M136 = Modelo("136")
_TODAY = date(2025, 1, 2)


def _profile(**facts: object) -> TaxpayerProfile:
    return TaxpayerProfile.model_validate(
        {
            "tax_id": "X1234567L",
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
        premio_loteria_gravamen_especial_trimestres=frozenset({"2025-1T"}),
    )

    assert _m136_periods(profile, 2025) == [Period.from_year_and_code(2025, "1T")]
    assert derive_modelo_applicability(profile, "136", today=_TODAY).verdict is ApplicabilityVerdict.APPLICABLE


def test_a_wrong_quarter_opens_no_row_for_the_undeclared_quarter() -> None:
    profile = _profile(
        premio_loteria_gravamen_especial_sin_retencion=True,
        premio_loteria_gravamen_especial_trimestres=frozenset({"2025-2T"}),
    )

    periods = _m136_periods(profile, 2025)

    assert Period.from_year_and_code(2025, "1T") not in periods
    assert periods == [Period.from_year_and_code(2025, "2T")]


def test_a_quarter_of_another_year_opens_nothing_in_this_year() -> None:
    profile = _profile(
        premio_loteria_gravamen_especial_sin_retencion=True,
        premio_loteria_gravamen_especial_trimestres=frozenset({"2024-4T"}),
    )

    assert _m136_periods(profile, 2025) == []
    assert _m136_periods(profile, 2024) == [Period.from_year_and_code(2024, "4T")]


def test_yes_without_quarters_opens_no_row_and_stays_incomplete() -> None:
    profile = _profile(premio_loteria_gravamen_especial_sin_retencion=True)

    assert _m136_periods(profile, 2025) == []
    result = derive_modelo_applicability(profile, "136", today=_TODAY)
    assert result.verdict is ApplicabilityVerdict.INCOMPLETE
    assert "Periodos sin declarar" in result.reason


def test_no_is_not_applicable_and_opens_no_row() -> None:
    profile = _profile(premio_loteria_gravamen_especial_sin_retencion=False)

    assert _m136_periods(profile, 2025) == []
    assert derive_modelo_applicability(profile, "136", today=_TODAY).verdict is ApplicabilityVerdict.NOT_APPLICABLE


def test_an_unanswered_profile_is_incomplete_and_opens_no_row() -> None:
    profile = _profile()

    assert _m136_periods(profile, 2025) == []
    assert derive_modelo_applicability(profile, "136", today=_TODAY).verdict is ApplicabilityVerdict.INCOMPLETE


def test_the_2026_edition_windows_follow_the_same_quarter_rule() -> None:
    profile = _profile(
        premio_loteria_gravamen_especial_sin_retencion=True,
        premio_loteria_gravamen_especial_trimestres=frozenset({"2026-3T", "2026-4T"}),
    )

    assert _m136_periods(profile, 2026) == [
        Period.from_year_and_code(2026, "3T"),
        Period.from_year_and_code(2026, "4T"),
    ]
