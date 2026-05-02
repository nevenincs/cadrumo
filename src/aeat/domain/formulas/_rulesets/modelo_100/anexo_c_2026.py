"""Modelo 100 Anexo C — rendimientos del capital inmobiliario (ejercicio 2026).

LIRPF arts. 22-24 and 85 are unchanged for 2026 at the BOE
consolidated-text consult of 2026-02-28. The Ley 12/2023 tiered art.
23.2 reducción remains in force. The 2026 ruleset inherits the 2025
surface from :mod:`.anexo_c_2025`; any 2026-specific delta is added
when the 2026 Orden HAC publishes.
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

EFFECTIVE_FROM = date(2026, 1, 1)
EFFECTIVE_TO = date(2026, 12, 31)


FORMULAS = (
    formula(
        casilla_id="0106",
        formula_id="modelo_100.2026.c.rendimiento_neto_previo",
        body=clamp_pos(
            sub_op(
                sub_op(ref("0061"), ref("0066")),
                ref("0072"),
            ),
        ),
    ),
    formula(
        casilla_id="0107",
        formula_id="modelo_100.2026.c.rendimiento_neto_reducido",
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
