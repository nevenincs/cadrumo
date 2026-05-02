"""Define the Modelo 100 Anexo N ruleset for the 2026 ejercicio.

For 2026 only Andalucía has published its 2026 Ley de Presupuestos
(Ley 8/2025); the other fourteen ordinary CCAAs use 2025 amounts as
the conservative baseline pending each Comunidad's 2026 publication.
The structural surface is inherited from
:mod:`aeat.domain.formulas._rulesets.modelo_100.anexo_n_2025` — that
module defines :data:`CASILLAS` and :data:`CITATIONS`. Only the
year-scoped :data:`FORMULAS` and effective-date constants are
redeclared here.
"""

from __future__ import annotations

from datetime import date

from ..._ruleset import ParameterTable
from .._common import add_op, formula, ref
from .anexo_n_2025 import CASILLAS, CITATIONS

EFFECTIVE_FROM = date(2026, 1, 1)
"""First day of the ejercicio in which this Anexo N ruleset applies."""

EFFECTIVE_TO = date(2026, 12, 31)
"""Last day of the ejercicio in which this Anexo N ruleset applies."""


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
"""Engine formula bindings for the 2026 Anexo N computed casillas."""


PARAMETERS = ParameterTable(entries={})
"""Anexo N declares no parametric tables."""


__all__ = [
    "CASILLAS",
    "CITATIONS",
    "EFFECTIVE_FROM",
    "EFFECTIVE_TO",
    "FORMULAS",
    "PARAMETERS",
]
