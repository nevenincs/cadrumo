"""Modelo 100 Anexo E — ganancias y pérdidas patrimoniales (ejercicio 2024).

Re-exports ``CASILLAS`` and ``CITATIONS`` from :mod:`.anexo_e_2025`;
only ``FORMULAS`` (year-scoped formula IDs) and the effective-date
constants are year-specific.
"""

from __future__ import annotations

from datetime import date

from ..._ruleset import ParameterTable
from .._common import formula, ref, sub_op
from .anexo_e_2025 import CASILLAS, CITATIONS

EFFECTIVE_FROM = date(2024, 1, 1)
EFFECTIVE_TO = date(2024, 12, 31)


FORMULAS = (
    formula(
        casilla_id="0405",
        formula_id="modelo_100.2024.e.saldo_neto_patrimonial",
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
