"""Modelo 100 Anexo N — deducciones autonomicas (ejercicio 2024).

Per LIRPF art. 46 bis + Ley 22/2009 (cesion de tributos), each CCAA
sets its own deductions. Inherits CASILLAS + CITATIONS from the 2025
reference; year-scoped FORMULAS + effective dates declared here.
"""

from __future__ import annotations

from datetime import date

from ..._ruleset import ParameterTable
from .._common import add_op, formula, ref
from .anexo_n_2025 import CASILLAS, CITATIONS

EFFECTIVE_FROM = date(2024, 1, 1)
EFFECTIVE_TO = date(2024, 12, 31)


_CCAA_REFS = tuple(
    ref(cid)
    for cid in (
        "1101",
        "1102",
        "1103",
        "1104",
        "1105",
        "1106",
        "1107",
        "1108",
        "1109",
        "1110",
        "1111",
        "1112",
        "1113",
        "1114",
        "1115",
    )
)


FORMULAS = (
    formula(
        casilla_id="0622",
        formula_id="modelo_100.2024.n.total_deducciones_autonomicas",
        body=add_op(*_CCAA_REFS),
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
