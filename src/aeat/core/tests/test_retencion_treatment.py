"""Statutory retención treatment for rendimientos-del-trabajo schemes.

The administrador/consejero figures are grounded in LIRPF art. 101.2 (Ley 35/2006,
BOE-A-2006-20764), developed by RIRPF art. 80.1.3.º (RD 439/2007): the fixed general
rate is 35 % and it drops to 19 % when the paying entity's importe neto de la cifra de
negocios is below 100.000 euros. The expected values here are read from that statutory
text (the bundled consolidated LIRPF art-101 corpus), not derived from any registry
formula under test.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ..aggregation import (
    ADMINISTRADOR_RETENCION_RATE,
    ADMINISTRADOR_RETENCION_REDUCED_INCN_THRESHOLD_EUR,
    ADMINISTRADOR_RETENCION_REDUCED_RATE,
    RetencionScheme,
    WorkIncomeRetencionTreatment,
    work_income_retencion_treatment,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_administrador_statutory_rates_match_art_101_2() -> None:
    """The fixed administrador rates equal the LIRPF art. 101.2 figures (35 % / 19 %, 100.000 €)."""
    assert Decimal("0.35") == ADMINISTRADOR_RETENCION_RATE
    assert Decimal("0.19") == ADMINISTRADOR_RETENCION_REDUCED_RATE
    assert Decimal("100000") == ADMINISTRADOR_RETENCION_REDUCED_INCN_THRESHOLD_EUR


def test_director_scheme_is_distinct_from_empleado_scheme() -> None:
    """clave A (empleado) and clave E (administrador) are separate closed-axis members."""
    assert RetencionScheme.WORK_INCOME.value == "rendimientos_trabajo"
    assert RetencionScheme.WORK_INCOME_DIRECTOR.value == "rendimientos_trabajo_administrador"
    assert RetencionScheme.WORK_INCOME != RetencionScheme.WORK_INCOME_DIRECTOR


def test_director_treatment_carries_fixed_art_101_2_rates() -> None:
    """The administrador treatment is the fixed art. 101.2 rate, not the progressive escala."""
    treatment = work_income_retencion_treatment(RetencionScheme.WORK_INCOME_DIRECTOR)
    assert isinstance(treatment, WorkIncomeRetencionTreatment)
    assert treatment.is_fixed_rate is True
    assert treatment.fixed_rate == Decimal("0.35")
    assert treatment.fixed_reduced_rate == Decimal("0.19")
    assert treatment.fixed_reduced_incn_threshold_eur == Decimal("100000")
    assert "ley-35-2006:art-101" in treatment.legal_refs
    assert "rd-439-2007:art-80" in treatment.legal_refs


def test_empleado_treatment_is_progressive_with_no_fixed_rate() -> None:
    """The ordinary empleado treatment is the personalised progressive procedure (art. 101.1)."""
    treatment = work_income_retencion_treatment(RetencionScheme.WORK_INCOME)
    assert isinstance(treatment, WorkIncomeRetencionTreatment)
    assert treatment.is_fixed_rate is False
    assert treatment.fixed_rate is None
    assert treatment.fixed_reduced_rate is None
    assert treatment.fixed_reduced_incn_threshold_eur is None
    assert "ley-35-2006:art-101" in treatment.legal_refs


def test_non_work_income_schemes_have_no_trabajo_treatment() -> None:
    """Actividades, premios, capital, and arrendamiento are not art. 101.1/101.2 trabajo."""
    for scheme in (
        RetencionScheme.ECONOMIC_ACTIVITY,
        RetencionScheme.PROFESSIONAL,
        RetencionScheme.PRIZE,
        RetencionScheme.URBAN_RENTAL,
        RetencionScheme.CAPITAL_INTEREST,
    ):
        assert work_income_retencion_treatment(scheme) is None
