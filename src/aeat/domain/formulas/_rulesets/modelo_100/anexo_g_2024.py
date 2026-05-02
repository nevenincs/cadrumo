"""Define the Modelo 100 Anexo G ruleset for the 2024 ejercicio.

The 2024 ruleset diverges from
:mod:`aeat.domain.formulas._rulesets.modelo_100.anexo_g_2025` only in
the tarifa estatal del ahorro top bracket (>300.000 EUR), which sits
at 14 % in 2024 and was raised to 15 % by Ley 7/2024 (BOE-A-2024-26694)
with effects 1/1/2025. All other tarifa ranges are unchanged, so the
2025 :data:`CASILLAS`, :data:`CITATIONS`, the
:data:`TARIFA_ESTATAL_GENERAL_2025` table, and the
:func:`progressive_tarifa` AST builder are re-exported.
"""

from __future__ import annotations

from datetime import date

from ..._ruleset import ParameterTable
from .._common import (
    add_op,
    clamp_pos,
    formula,
    min_op,
    ref,
    sub_op,
)
from .anexo_g_2025 import CASILLAS as CASILLAS  # re-export
from .anexo_g_2025 import (
    CITATIONS,
    TARIFA_ESTATAL_GENERAL_2025,
    progressive_tarifa,
)

EFFECTIVE_FROM = date(2024, 1, 1)
"""First day of the ejercicio in which this Anexo G ruleset applies."""

EFFECTIVE_TO = date(2024, 12, 31)
"""Last day of the ejercicio in which this Anexo G ruleset applies."""


TARIFA_ESTATAL_AHORRO_2024: tuple[tuple[str, str | None, str], ...] = (
    ("0", "6000.00", "0.095"),
    ("6000.00", "50000.00", "0.105"),
    ("50000.00", "200000.00", "0.115"),
    ("200000.00", "300000.00", "0.135"),
    ("300000.00", None, "0.14"),
)
"""Tarifa estatal del ahorro for 2024 — LIRPF art. 66 pre Ley 7/2024.

Each tuple is ``(from_value, to_value, rate)`` with ``to_value=None``
for the open-ended top bracket. The 2024 ceiling rate is 14 %; from
2025 onward Ley 7/2024 raises it to 15 % (see
:data:`aeat.domain.formulas._rulesets.modelo_100.anexo_g_2025.TARIFA_ESTATAL_AHORRO_2025`).
"""


_CUOTA_TARIFA_BLG_BODY = progressive_tarifa(ref("0545"), TARIFA_ESTATAL_GENERAL_2025)
_CUOTA_TARIFA_MINIMO_BODY = progressive_tarifa(
    min_op(ref("0500"), ref("0545")),
    TARIFA_ESTATAL_GENERAL_2025,
)
_CUOTA_INTEGRA_AHORRO_BODY = progressive_tarifa(ref("0555"), TARIFA_ESTATAL_AHORRO_2024)


FORMULAS = (
    formula(
        casilla_id="0540",
        formula_id="modelo_100.2024.g.cuota_tarifa_estatal_blg",
        body=_CUOTA_TARIFA_BLG_BODY,
    ),
    formula(
        casilla_id="0542",
        formula_id="modelo_100.2024.g.cuota_tarifa_estatal_minimo",
        body=_CUOTA_TARIFA_MINIMO_BODY,
    ),
    formula(
        casilla_id="0550",
        formula_id="modelo_100.2024.g.cuota_integra_estatal_general",
        body=clamp_pos(sub_op(ref("0540"), ref("0542"))),
    ),
    formula(
        casilla_id="0560",
        formula_id="modelo_100.2024.g.cuota_integra_estatal_ahorro",
        body=_CUOTA_INTEGRA_AHORRO_BODY,
    ),
    formula(
        casilla_id="0595",
        formula_id="modelo_100.2024.g.cuota_integra_total",
        body=add_op(
            add_op(ref("0550"), ref("0551")),
            add_op(ref("0560"), ref("0561")),
        ),
    ),
    formula(
        casilla_id="0630",
        formula_id="modelo_100.2024.g.total_deducciones",
        body=add_op(ref("0620"), ref("0622")),
    ),
    formula(
        casilla_id="0698",
        formula_id="modelo_100.2024.g.cuota_liquida_total",
        body=clamp_pos(
            sub_op(
                sub_op(ref("0595"), ref("0630")),
                ref("0612"),
            ),
        ),
    ),
    formula(
        casilla_id="0720",
        formula_id="modelo_100.2024.g.cuota_diferencial",
        body=sub_op(
            sub_op(ref("0698"), ref("0699")),
            ref("0700"),
        ),
    ),
)
"""Engine formula bindings for the 2024 Anexo G computed casillas."""


PARAMETERS = ParameterTable(entries={})
"""Anexo G declares no parametric tables."""


__all__ = [
    "CASILLAS",
    "CITATIONS",
    "EFFECTIVE_FROM",
    "EFFECTIVE_TO",
    "FORMULAS",
    "PARAMETERS",
]
