"""Modelo 100 Anexo B1 — rendimientos del trabajo (ejercicio 2026).

Ejercicio 2026 inherits the LIRPF art. 17-20 numerical surface from
2025 — no posterior law has modified arts. 17-20 between Real Decreto-
Ley 4/2024 (vigent 1/1/2024) and 2026-02-28 (BOE consolidated-text
consult date for this authoring). The 2026 Orden HAC del Modelo 100
has not yet been published at retrieval 2026-04-27 (precedent: feb-mar
2027); this Anexo B1 module ships with 2025 values as the conservative
baseline. Any 2026-specific delta lands as a follow-up issue when the
2026 Orden HAC publishes.

Anexo B1 casillas + citations are imported from the 2025 reference
module; only ``FORMULAS`` (year-scoped formula IDs) and the effective-
date constants are year-specific.
"""

from __future__ import annotations

from datetime import date

from ..._ruleset import ParameterTable
from .._common import (
    clamp_pos,
    formula,
    lit,
    max_op,
    min_op,
    mul_op,
    ref,
    sub_op,
)
from .anexo_b1_2025 import CASILLAS, CITATIONS

EFFECTIVE_FROM = date(2026, 1, 1)
EFFECTIVE_TO = date(2026, 12, 31)


_REDUCCION_ART20_BODY = min_op(
    ref("0020"),
    max_op(
        clamp_pos(
            sub_op(
                lit("7302.00"),
                mul_op(
                    lit("1.75"),
                    clamp_pos(sub_op(ref("0020"), lit("14852.00"))),
                ),
            ),
        ),
        clamp_pos(
            sub_op(
                lit("2364.34"),
                mul_op(
                    lit("1.14"),
                    clamp_pos(sub_op(ref("0020"), lit("17673.52"))),
                ),
            ),
        ),
    ),
)


FORMULAS = (
    formula(
        casilla_id="0020",
        formula_id="modelo_100.2026.b1.rendimiento_neto_previo",
        body=clamp_pos(
            sub_op(
                sub_op(
                    sub_op(
                        sub_op(ref("0001"), ref("0008")),
                        ref("0009"),
                    ),
                    ref("0010"),
                ),
                ref("0019"),
            ),
        ),
    ),
    formula(
        casilla_id="0021",
        formula_id="modelo_100.2026.b1.reduccion_art_20",
        body=_REDUCCION_ART20_BODY,
    ),
    formula(
        casilla_id="0022",
        formula_id="modelo_100.2026.b1.rendimiento_neto_reducido",
        body=clamp_pos(sub_op(ref("0020"), ref("0021"))),
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
