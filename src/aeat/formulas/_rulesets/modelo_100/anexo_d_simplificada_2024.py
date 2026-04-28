"""Modelo 100 Anexo D — E.D. simplificada (2024). RIRPF art. 30 stable."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ..._formula import Literal, MinFormula, MulFormula
from ..._ruleset import ParameterTable
from .._common import (
    clamp_pos,
    formula,
    lit,
    ref,
    sub_op,
)
from .anexo_d_simplificada_2025 import CASILLAS, CITATIONS

EFFECTIVE_FROM = date(2024, 1, 1)
EFFECTIVE_TO = date(2024, 12, 31)


_GASTOS_DIFICIL_BODY = MinFormula(
    operands=(
        MulFormula(operands=(Literal(value=Decimal("0.05")), ref("0220"))),
        lit("2000.00"),
    ),
)


FORMULAS = (
    formula(
        casilla_id="0220",
        formula_id="modelo_100.2024.d_simplificada.rendimiento_neto_pre_cap",
        body=clamp_pos(sub_op(ref("0210"), ref("0215"))),
    ),
    formula(
        casilla_id="0225",
        formula_id="modelo_100.2024.d_simplificada.gastos_dificil_justificacion",
        body=_GASTOS_DIFICIL_BODY,
    ),
    formula(
        casilla_id="0230",
        formula_id="modelo_100.2024.d_simplificada.rendimiento_neto_previo",
        body=clamp_pos(sub_op(ref("0220"), ref("0225"))),
    ),
    formula(
        casilla_id="0240",
        formula_id="modelo_100.2024.d_simplificada.rendimiento_neto_reducido",
        body=clamp_pos(sub_op(ref("0230"), ref("0235"))),
    ),
)


PARAMETERS = ParameterTable(entries={})


__all__ = [
    "CASILLAS",
    "CITATIONS",
    "EFFECTIVE_FROM",
    "EFFECTIVE_TO",
    "FORMULAS",
    "PARAMETERS",
]
