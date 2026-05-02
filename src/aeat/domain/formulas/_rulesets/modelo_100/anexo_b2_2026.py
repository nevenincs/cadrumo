"""Modelo 100 Anexo B2 — rendimientos del capital mobiliario (ejercicio 2026).

LIRPF arts. 25-26 and 101.4 are unchanged for 2026 at the BOE
consolidated-text consult of 2026-02-28. The 2026 ruleset inherits the
2025 surface from :mod:`.anexo_b2_2025`; any 2026-specific delta is
added when the 2026 Orden HAC publishes.
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

EFFECTIVE_FROM = date(2026, 1, 1)
EFFECTIVE_TO = date(2026, 12, 31)


FORMULAS = (
    formula(
        casilla_id="0048",
        formula_id="modelo_100.2026.b2.rendimiento_neto_previo",
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
        formula_id="modelo_100.2026.b2.rendimiento_neto_reducido",
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
