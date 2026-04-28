"""Modelo 100 Anexo E — ganancias y perdidas patrimoniales (2026)."""

from __future__ import annotations

from datetime import date

from ..._ruleset import ParameterTable
from .._common import formula, ref, sub_op
from .anexo_e_2025 import CASILLAS, CITATIONS

EFFECTIVE_FROM = date(2026, 1, 1)
EFFECTIVE_TO = date(2026, 12, 31)


FORMULAS = (
    formula(
        casilla_id="0405",
        formula_id="modelo_100.2026.e.saldo_neto_patrimonial",
        body=sub_op(ref("0306"), ref("0307")),
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
