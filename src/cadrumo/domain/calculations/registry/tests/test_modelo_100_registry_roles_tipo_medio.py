"""Modelo 100 average-rate semantic-role registry tests."""

from __future__ import annotations

import pytest

from ._modelo_100_registry_support import _modelo_100_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_AVERAGE_RATE_SECTION = ("resultados", "calculo_impuesto_res", "gravamenes_res")
_AVERAGE_RATE_ROWS = {
    "0534": (
        "irpf_tipo_medio_gravamen_base_liquidable_general_estatal",
        "[0534] = [0532] x 100 / [0505]",
        "Parte estatal",
        "tipo-medio-gravamen-estatal-base-liquidable-general",
    ),
    "0535": (
        "irpf_tipo_medio_gravamen_general_autonomico",
        "[0535] = [0533] x 100 / [0505]",
        "Parte autonómica",
        "tipo-medio-gravamen-autonomico-base-liquidable-general",
    ),
    "0542": (
        "irpf_tipo_medio_gravamen_ahorro_estatal",
        "[0542] = [0540] x 100 / [0510]",
        "Parte estatal",
        "tipo-medio-gravamen-estatal-base-liquidable-ahorro",
    ),
    "0543": (
        "irpf_tipo_medio_gravamen_ahorro_autonomico",
        "[0543] = [0541] x 100 / [0510]",
        "Parte autonómica",
        "tipo-medio-gravamen-autonomico-base-liquidable-ahorro",
    ),
}


@pytest.mark.parametrize("filing_year", [2020, 2021, 2022, 2023, 2024, 2025])
def test_modelo_100_average_rate_casillas_are_ratio_typed(filing_year: int) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in _AVERAGE_RATE_ROWS}
    formulas_by_id = {formula.id: formula for formula in revision.formulas}

    assert set(casillas_by_id) == set(_AVERAGE_RATE_ROWS)

    for casilla_id, (role, label_formula, label_part, formula_suffix) in _AVERAGE_RATE_ROWS.items():
        casilla = casillas_by_id[casilla_id]
        expected_formula = f"renta-{filing_year}-{formula_suffix}"

        assert tuple(casilla.section) == _AVERAGE_RATE_SECTION
        assert casilla.data_type == "ratio"
        assert casilla.semantic_role == role
        assert casilla.input_kind == "computed"
        assert casilla.formula == expected_formula
        assert label_formula in casilla.label
        assert label_part in casilla.label
        assert "Tipos medios de gravamen" in casilla.label
        assert "ley-35-2006:art-63" in casilla.legal_refs

        formula = formulas_by_id[expected_formula]
        assert formula.target_casilla_id == casilla_id
