"""Modelo 100 Anexo C — rendimientos del capital inmobiliario (ejercicio 2024).

Ejercicio 2024 is the first year on which Ley 12/2023
(BOE-A-2023-12203) applies for contracts celebrados desde 26/5/2023 —
the tiered 50/60/70/90 % art. 23.2 reducción supersedes the prior flat
60 % régime. ``CASILLAS`` and ``CITATIONS`` are re-exported from
:mod:`.anexo_c_2025`; year-scoped ``FORMULAS`` and effective dates are
declared here.
"""

from __future__ import annotations

from datetime import date

from ..._ruleset import ParameterTable
from .._common import (
    clamp_pos,
    formula,
    ref,
    sub_op,
)
from .anexo_c_2025 import CASILLAS, CITATIONS

EFFECTIVE_FROM = date(2024, 1, 1)
EFFECTIVE_TO = date(2024, 12, 31)


FORMULAS = (
    formula(
        casilla_id="0106",
        formula_id="modelo_100.2024.c.rendimiento_neto_previo",
        body=clamp_pos(
            sub_op(
                sub_op(ref("0061"), ref("0066")),
                ref("0072"),
            ),
        ),
    ),
    formula(
        casilla_id="0107",
        formula_id="modelo_100.2024.c.rendimiento_neto_reducido",
        body=clamp_pos(sub_op(ref("0106"), ref("0078"))),
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
