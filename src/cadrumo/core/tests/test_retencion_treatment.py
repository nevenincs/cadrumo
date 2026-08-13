"""Structural retención-treatment taxonomy for rendimientos-del-trabajo schemes.

``WorkIncomeRetencionTreatment`` carries only the STRUCTURAL fact of which
procedure a scheme follows (personalised progressive vs fixed statutory rate);
the fixed-rate VALUES themselves are registry data covered by
``domain/transactions/tests/test_administrador_retencion_parameters.py``, not
here (``aeat-registry-authority-flow``: this ``core`` layer is imported BY the
registry schema and must not import back from it).
"""

from __future__ import annotations

import pytest

from ..aggregation import RetencionScheme, WorkIncomeRetencionTreatment, work_income_retencion_treatment

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_director_scheme_is_distinct_from_empleado_scheme() -> None:
    """clave A (empleado) and clave E (administrador) are separate closed-axis members."""
    assert RetencionScheme.WORK_INCOME.value == "rendimientos_trabajo"
    assert RetencionScheme.WORK_INCOME_DIRECTOR.value == "rendimientos_trabajo_administrador"
    assert RetencionScheme.WORK_INCOME != RetencionScheme.WORK_INCOME_DIRECTOR


def test_work_income_treatment_matches_statutory_scheme() -> None:
    """Trabajo schemes preserve the art. 101.1 progressive and art. 101.2 fixed-rate split."""
    cases: tuple[tuple[str, RetencionScheme, bool], ...] = (
        ("administrador-fixed-art-101-2", RetencionScheme.WORK_INCOME_DIRECTOR, True),
        ("empleado-progressive-art-101-1", RetencionScheme.WORK_INCOME, False),
    )

    for case_id, scheme, is_fixed_rate in cases:
        treatment = work_income_retencion_treatment(scheme)
        assert isinstance(treatment, WorkIncomeRetencionTreatment), case_id
        assert treatment.is_fixed_rate is is_fixed_rate, case_id


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
