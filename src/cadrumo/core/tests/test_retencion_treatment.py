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
    for case_id, actual, expected in (
        ("general-rate", ADMINISTRADOR_RETENCION_RATE, Decimal("0.35")),
        ("reduced-rate", ADMINISTRADOR_RETENCION_REDUCED_RATE, Decimal("0.19")),
        ("reduced-incn-threshold", ADMINISTRADOR_RETENCION_REDUCED_INCN_THRESHOLD_EUR, Decimal("100000")),
    ):
        assert actual == expected, case_id


def test_director_scheme_is_distinct_from_empleado_scheme() -> None:
    """clave A (empleado) and clave E (administrador) are separate closed-axis members."""
    assert RetencionScheme.WORK_INCOME.value == "rendimientos_trabajo"
    assert RetencionScheme.WORK_INCOME_DIRECTOR.value == "rendimientos_trabajo_administrador"
    assert RetencionScheme.WORK_INCOME != RetencionScheme.WORK_INCOME_DIRECTOR


def test_work_income_treatment_matches_statutory_scheme() -> None:
    """Trabajo schemes preserve the art. 101.1 progressive and art. 101.2 fixed-rate split."""
    cases: tuple[
        tuple[
            str,
            RetencionScheme,
            bool,
            Decimal | None,
            Decimal | None,
            Decimal | None,
            tuple[str, ...],
        ],
        ...,
    ] = (
        (
            "administrador-fixed-art-101-2",
            RetencionScheme.WORK_INCOME_DIRECTOR,
            True,
            Decimal("0.35"),
            Decimal("0.19"),
            Decimal("100000"),
            ("ley-35-2006:art-101", "rd-439-2007:art-80"),
        ),
        (
            "empleado-progressive-art-101-1",
            RetencionScheme.WORK_INCOME,
            False,
            None,
            None,
            None,
            ("ley-35-2006:art-101",),
        ),
    )

    for (
        case_id,
        scheme,
        is_fixed_rate,
        fixed_rate,
        fixed_reduced_rate,
        fixed_reduced_incn_threshold_eur,
        legal_refs,
    ) in cases:
        treatment = work_income_retencion_treatment(scheme)
        assert isinstance(treatment, WorkIncomeRetencionTreatment), case_id
        assert treatment.is_fixed_rate is is_fixed_rate, case_id
        assert treatment.fixed_rate == fixed_rate, case_id
        assert treatment.fixed_reduced_rate == fixed_reduced_rate, case_id
        assert treatment.fixed_reduced_incn_threshold_eur == fixed_reduced_incn_threshold_eur, case_id
        for legal_ref in legal_refs:
            assert legal_ref in treatment.legal_refs, case_id


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
