"""Modelo 100 Anexo B2 — rendimientos del capital mobiliario (ejercicio 2024).

LIRPF arts. 25-26 and 101.4 are stable across 2024, 2025 and 2026.
This module re-exports ``CASILLAS`` and ``CITATIONS`` from
:mod:`.anexo_b2_2025` and declares year-scoped ``FORMULAS`` and
effective-date constants.
"""

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
from .anexo_b2_2025 import CASILLAS, CITATIONS

EFFECTIVE_FROM = date(2024, 1, 1)
EFFECTIVE_TO = date(2024, 12, 31)


FORMULAS = (
    formula(
        casilla_id="0048",
        formula_id="modelo_100.2024.b2.rendimiento_neto_previo",
        body=clamp_pos(
            sub_op(
                add_op(
                    add_op(ref("0028"), ref("0029")),
                    add_op(ref("0030"), ref("0031")),
                ),
                ref("0035"),
            ),
        ),
    ),
    formula(
        casilla_id="0049",
        formula_id="modelo_100.2024.b2.rendimiento_neto_reducido",
        body=clamp_pos(sub_op(ref("0048"), ref("0032"))),
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
