"""Modelo 100 Anexo D — módulos (ejercicio 2026).

Re-exports ``CASILLAS`` and ``CITATIONS`` from
:mod:`.anexo_d_modulos_2025`; only ``FORMULAS`` (year-scoped formula
IDs) and the effective-date constants are year-specific. The
per-actividad tabla for 2026 is governed by Orden HAC/1425/2025
(BOE-A-2025-25272) and is supplied externally by the caller via
``0250``.
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
from .anexo_d_modulos_2025 import CASILLAS, CITATIONS

EFFECTIVE_FROM = date(2026, 1, 1)
EFFECTIVE_TO = date(2026, 12, 31)


FORMULAS = (
    formula(
        casilla_id="0260",
        formula_id="modelo_100.2026.d_modulos.rendimiento_neto_reducido",
        body=clamp_pos(sub_op(ref("0250"), ref("0255"))),
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
