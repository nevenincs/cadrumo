"""Define the Modelo 100 Anexo E ruleset for the 2026 ejercicio.

Ejercicio 2026 inherits the structural surface from
:mod:`aeat.domain.formulas._rulesets.modelo_100.anexo_e_2025` because
LIRPF arts. 33-39 (ganancias y pérdidas patrimoniales) remain unchanged
in the consolidated BOE text. Only the year-scoped formula bindings
and effective-date constants are redeclared here.
"""

from __future__ import annotations

from datetime import date

from ..._ruleset import ParameterTable
from .._common import formula, ref, sub_op
from .anexo_e_2025 import CASILLAS, CITATIONS

EFFECTIVE_FROM = date(2026, 1, 1)
"""First day of the ejercicio in which this Anexo E ruleset applies."""

EFFECTIVE_TO = date(2026, 12, 31)
"""Last day of the ejercicio in which this Anexo E ruleset applies."""


FORMULAS = (
    formula(
        casilla_id="0405",
        formula_id="modelo_100.2026.e.saldo_neto_patrimonial",
        body=sub_op(ref("0306"), ref("0307")),
    ),
)
"""Engine formula bindings for the 2026 Anexo E computed casillas."""


PARAMETERS = ParameterTable(entries={})
"""Anexo E declares no parametric tables."""


__all__ = [
    "CASILLAS",
    "CITATIONS",
    "EFFECTIVE_FROM",
    "EFFECTIVE_TO",
    "FORMULAS",
    "PARAMETERS",
]
