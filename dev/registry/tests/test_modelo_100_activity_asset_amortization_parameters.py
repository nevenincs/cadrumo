"""Tripwires for the paired 2025 activity-asset amortization authority."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema_formula import ParameterDefinition

from ..compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _parameters() -> dict[str, ParameterDefinition]:
    revision = load_modelo_directory(bundled_path("registry", "aeat", "modelos", "100")).revisions["2025"]
    return {parameter.id: parameter for parameter in revision.parameters}


def test_linear_authority_tables_are_paired_and_2025_only() -> None:
    parameters = _parameters()
    for regime in ("normal", "simplificada"):
        prefix = f"renta-actividad-inmovilizado-amortizacion-{regime}"
        coefficients = parameters[f"{prefix}-coeficiente-lineal-maximo"]
        periods = parameters[f"{prefix}-periodo-maximo-anos"]
        coefficient_rows = {row.key: row for row in coefficients.keyed_brackets}
        period_rows = {row.key: row for row in periods.keyed_brackets}

        assert coefficient_rows.keys() == period_rows.keys()
        assert coefficient_rows
        for row in (*coefficient_rows.values(), *period_rows.values()):
            assert row.valid_from == date(2025, 1, 1)
            assert row.valid_to == date(2025, 12, 31)


def test_material_and_intangible_authority_remain_distinct_and_grounded() -> None:
    parameters = _parameters()
    normal = parameters["renta-actividad-inmovilizado-amortizacion-normal-coeficiente-lineal-maximo"]
    normal_rows = {row.key: row.value for row in normal.keyed_brackets}

    assert normal_rows["edificio-industrial"] == Decimal("3")
    assert normal_rows["equipo-proceso-informacion"] == Decimal("25")
    assert normal_rows["intangible-software"] == Decimal("33")
    assert parameters["renta-actividad-inmovilizado-intangible-vida-util-no-estimable-limite-anual"].values[
        0
    ].value == Decimal("5")
    assert parameters["renta-actividad-inmovilizado-material-nuevo-libertad-amortizacion-umbral-unitario"].values[
        0
    ].value == Decimal("300")
