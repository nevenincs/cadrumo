"""Tripwires for the paired activity-asset amortization authority."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema_formula import ParameterDefinition
from cadrumo.domain.calculations.registry.tests.authored_editions import newest_authored_edition, revision_covering

from ..compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: The newest authored edition and the one exercise it governs.
_EXERCISE = newest_authored_edition("100")
_EDITION = str(revision_covering("100", _EXERCISE).id)


def _parameters() -> dict[str, ParameterDefinition]:
    revision = load_modelo_directory(bundled_path("registry", "aeat", "modelos", "100")).revisions[_EDITION]
    return {parameter.id: parameter for parameter in revision.parameters}


def test_linear_authority_tables_are_paired_and_in_force_for_the_newest_edition() -> None:
    """Both linear tables state the same asset classes, each row in force across the whole of 2025.

    The tables run open from the first edition stating them, so a row may begin
    before 2025; what the 2025 edition must not carry is a row that ends within it.
    """
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
            assert row.valid_from is not None
            assert row.valid_from <= date(_EXERCISE, 1, 1)
            assert row.valid_to is None or row.valid_to >= date(_EXERCISE, 12, 31)


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
