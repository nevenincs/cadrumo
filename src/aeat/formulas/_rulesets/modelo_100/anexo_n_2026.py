"""Modelo 100 Anexo N — deducciones autonomicas (ejercicio 2026).

For 2026 only Andalucia has published its 2026 Ley de Presupuestos
(Ley 8/2025) at retrieval 2026-04-27. The other 14 ordinary CCAAs use
2025 amounts as the conservative baseline; per-CCAA refresh follow-up
issues open post-merge as each Comunidad publishes its 2026 Ley.
"""

from __future__ import annotations

from datetime import date

from ..._ruleset import ParameterTable
from .._common import add_op, formula, ref
from .anexo_n_2025 import CASILLAS, CITATIONS

EFFECTIVE_FROM = date(2026, 1, 1)
EFFECTIVE_TO = date(2026, 12, 31)


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
        formula_id="modelo_100.2026.n.total_deducciones_autonomicas",
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
