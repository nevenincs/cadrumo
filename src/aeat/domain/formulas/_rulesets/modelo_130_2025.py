"""Modelo 130 ruleset covering the full 2025 fiscal year.

The 2024 and 2025 rulesets are mechanically identical — AEAT RD
439/2007 art. 110 was not amended between the two years (see the
research doc §Mid-year rule changes). The separate ruleset file
simplifies future divergence (e.g., the La Palma 60% reduction from
4T 2025 onwards, which lands in a dedicated territorial
overlay).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ...modelos import ModeloCode
from .._ruleset import ParameterTable, ParameterValue, Ruleset
from ._common import (
    add_op,
    clamp_pos,
    formula,
    lit,
    max_op,
    param,
    percent,
    ref,
    sub_op,
)
from .modelo_130_2024 import (
    _CASILLAS as _CASILLAS_2024,
)
from .modelo_130_2024 import (
    _CITATIONS as _CITATIONS_2024,
)

_EFFECTIVE_FROM = date(2025, 1, 1)
_EFFECTIVE_TO = date(2025, 12, 31)


_FORMULAS = (
    formula(
        casilla_id="03",
        formula_id="modelo_130.2025.rendimiento_neto",
        body=sub_op(ref("01"), ref("02")),
    ),
    formula(
        casilla_id="04",
        formula_id="modelo_130.2025.pago_fraccionado",
        body=clamp_pos(percent(param("irpf.trimestral_rate"), ref("03"))),
    ),
    formula(
        casilla_id="07",
        formula_id="modelo_130.2025.resultado_apartado_i",
        body=sub_op(sub_op(ref("04"), ref("05")), ref("06")),
    ),
    formula(
        casilla_id="09",
        formula_id="modelo_130.2025.pago_fraccionado_agraria",
        body=percent(param("agraria.trimestral_rate"), ref("08")),
    ),
    formula(
        casilla_id="11",
        formula_id="modelo_130.2025.resultado_apartado_ii",
        body=sub_op(ref("09"), ref("10")),
    ),
    formula(
        casilla_id="12",
        formula_id="modelo_130.2025.suma_parciales",
        body=max_op(lit("0"), add_op(ref("07"), ref("11"))),
    ),
    formula(
        casilla_id="14",
        formula_id="modelo_130.2025.neto_tras_minoracion",
        body=sub_op(ref("12"), ref("13")),
    ),
    formula(
        casilla_id="17",
        formula_id="modelo_130.2025.diferencia",
        body=sub_op(sub_op(ref("14"), ref("15")), ref("16")),
    ),
    formula(
        casilla_id="19",
        formula_id="modelo_130.2025.resultado_final",
        body=sub_op(ref("17"), ref("18")),
    ),
)


_PARAMETERS = ParameterTable(
    entries={
        "irpf.trimestral_rate": (
            ParameterValue(
                effective_from=_EFFECTIVE_FROM,
                effective_to=_EFFECTIVE_TO,
                value=Decimal("0.20"),
            ),
        ),
        "agraria.trimestral_rate": (
            ParameterValue(
                effective_from=_EFFECTIVE_FROM,
                effective_to=_EFFECTIVE_TO,
                value=Decimal("0.02"),
            ),
        ),
    }
)


RULESET: Ruleset = Ruleset(
    ruleset_id="modelo_130.2025",
    modelo=ModeloCode.MODELO_130,
    effective_from=_EFFECTIVE_FROM,
    effective_to=_EFFECTIVE_TO,
    casillas=_CASILLAS_2024,
    formulas=_FORMULAS,
    parameters=_PARAMETERS,
    legal_citations=_CITATIONS_2024,
)
