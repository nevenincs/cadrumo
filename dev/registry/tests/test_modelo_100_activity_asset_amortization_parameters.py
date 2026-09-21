"""Tripwires for the paired 2025 activity-asset amortization authority."""

from __future__ import annotations

import tomllib
from datetime import date
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_SOURCE = (
    Path(__file__).parents[3]
    / "src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/parameters/0002-activity-asset-amortization.toml"
)


def _parameters() -> dict[str, dict[str, object]]:
    document = tomllib.loads(_SOURCE.read_text(encoding="utf-8"))
    parameters = document["revisions"]["2025"]["parameters"]
    return {parameter["id"]: parameter for parameter in parameters}


def test_linear_authority_tables_are_paired_and_2025_only() -> None:
    parameters = _parameters()
    for regime in ("normal", "simplificada"):
        prefix = f"renta-actividad-inmovilizado-amortizacion-{regime}"
        coefficients = parameters[f"{prefix}-coeficiente-lineal-maximo"]
        periods = parameters[f"{prefix}-periodo-maximo-anos"]
        coefficient_rows = {row["key"]: row for row in coefficients["keyed_brackets"]}
        period_rows = {row["key"]: row for row in periods["keyed_brackets"]}

        assert coefficient_rows.keys() == period_rows.keys()
        assert coefficient_rows
        for row in (*coefficient_rows.values(), *period_rows.values()):
            assert row["valid_from"] == date(2025, 1, 1)
            assert row["valid_to"] == date(2025, 12, 31)


def test_material_and_intangible_authority_remain_distinct_and_grounded() -> None:
    parameters = _parameters()
    normal = parameters["renta-actividad-inmovilizado-amortizacion-normal-coeficiente-lineal-maximo"]
    normal_rows = {row["key"]: row["value"] for row in normal["keyed_brackets"]}

    assert normal_rows["edificio-industrial"] == "3"
    assert normal_rows["equipo-proceso-informacion"] == "25"
    assert normal_rows["intangible-software"] == "33"
    assert parameters["renta-actividad-inmovilizado-intangible-vida-util-no-estimable-limite-anual"]["values"][
        0
    ]["value"] == "5"
    assert parameters["renta-actividad-inmovilizado-material-nuevo-libertad-amortizacion-umbral-unitario"][
        "values"
    ][0]["value"] == "300"
