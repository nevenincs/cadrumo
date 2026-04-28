"""Modelo 100 Anexo D — E.D. normal (2024). LIS arts. 12-14 + 17 stable."""

from __future__ import annotations

from datetime import date

from ..._ruleset import ParameterTable
from .._common import (
    add_op,
    clamp_pos,
    formula,
    ref,
    sub_op,
)
from .anexo_d_normal_2025 import CASILLAS, CITATIONS

EFFECTIVE_FROM = date(2024, 1, 1)
EFFECTIVE_TO = date(2024, 12, 31)


_TOTAL_GASTOS_BODY = sub_op(
    add_op(
        add_op(ref("0150"), ref("0165")),
        add_op(
            ref("0170"),
            add_op(ref("0173"), ref("0180")),
        ),
    ),
    ref("0155"),
)


FORMULAS = (
    formula(
        casilla_id="0190",
        formula_id="modelo_100.2024.d_normal.total_gastos",
        body=_TOTAL_GASTOS_BODY,
    ),
    formula(
        casilla_id="0195",
        formula_id="modelo_100.2024.d_normal.rendimiento_neto_previo",
        body=clamp_pos(sub_op(ref("0140"), ref("0190"))),
    ),
    formula(
        casilla_id="0205",
        formula_id="modelo_100.2024.d_normal.rendimiento_neto_reducido",
        body=clamp_pos(sub_op(ref("0195"), ref("0200"))),
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
