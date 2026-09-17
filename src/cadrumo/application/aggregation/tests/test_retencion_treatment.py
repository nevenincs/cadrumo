"""Dated registry-backed treatment mapping for work-income withholding."""

from __future__ import annotations

from datetime import date

import pytest

from ....core.aggregation import RetencionScheme, WorkIncomeRetencionTreatment
from ..retenciones import registry_work_income_retencion_treatments

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


def test_work_income_treatment_matches_statutory_scheme() -> None:
    treatments = registry_work_income_retencion_treatments(date(2025, 12, 31))
    cases: tuple[tuple[str, RetencionScheme, bool], ...] = (
        ("administrador-fixed-art-101-2", RetencionScheme("rendimientos_trabajo_administrador"), True),
        ("empleado-progressive-art-101-1", RetencionScheme("rendimientos_trabajo"), False),
    )
    for case_id, scheme, is_fixed_rate in cases:
        treatment = treatments[scheme]
        assert isinstance(treatment, WorkIncomeRetencionTreatment), case_id
        assert treatment.is_fixed_rate is is_fixed_rate, case_id


def test_non_work_income_schemes_have_no_trabajo_treatment() -> None:
    treatments = registry_work_income_retencion_treatments(date(2025, 12, 31))
    for scheme in (
        RetencionScheme("actividades_economicas"),
        RetencionScheme("actividades_profesionales"),
        RetencionScheme("premios"),
        RetencionScheme("arrendamiento_urbano"),
        RetencionScheme("intereses"),
    ):
        assert scheme not in treatments
