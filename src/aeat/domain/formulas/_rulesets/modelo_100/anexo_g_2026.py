"""Define the Modelo 100 Anexo G ruleset for the 2026 ejercicio.

Ejercicio 2026 inherits the 2025 numerical surface for both the tarifa
estatal general (LIRPF art. 63) and the tarifa estatal del ahorro
(art. 66 post Ley 7/2024) per the consolidated BOE text. This module
re-exports the 2025 :data:`CASILLAS`, :data:`CITATIONS`, the two
tarifa tables, and the :func:`progressive_tarifa` AST builder from
:mod:`aeat.domain.formulas._rulesets.modelo_100.anexo_g_2025`, and
only redeclares the year-scoped :data:`FORMULAS` and effective-date
constants.
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
from .anexo_g_2025 import (
    CASILLAS,
    CITATIONS,
    TARIFA_ESTATAL_AHORRO_2025,
    TARIFA_ESTATAL_GENERAL_2025,
    progressive_tarifa,
)

EFFECTIVE_FROM = date(2026, 1, 1)
"""First day of the ejercicio in which this Anexo G ruleset applies."""

EFFECTIVE_TO = date(2026, 12, 31)
"""Last day of the ejercicio in which this Anexo G ruleset applies."""


_CUOTA_TARIFA_BLG_BODY = progressive_tarifa(ref("0545"), TARIFA_ESTATAL_GENERAL_2025)
_CUOTA_TARIFA_MINIMO_BODY = progressive_tarifa(
    min_op(ref("0500"), ref("0545")),
    TARIFA_ESTATAL_GENERAL_2025,
)
_CUOTA_INTEGRA_AHORRO_BODY = progressive_tarifa(ref("0555"), TARIFA_ESTATAL_AHORRO_2025)


FORMULAS = (
    formula(
        casilla_id="0540",
        formula_id="modelo_100.2026.g.cuota_tarifa_estatal_blg",
        body=_CUOTA_TARIFA_BLG_BODY,
    ),
    formula(
        casilla_id="0542",
        formula_id="modelo_100.2026.g.cuota_tarifa_estatal_minimo",
        body=_CUOTA_TARIFA_MINIMO_BODY,
    ),
    formula(
        casilla_id="0550",
        formula_id="modelo_100.2026.g.cuota_integra_estatal_general",
        body=clamp_pos(sub_op(ref("0540"), ref("0542"))),
    ),
    formula(
        casilla_id="0560",
        formula_id="modelo_100.2026.g.cuota_integra_estatal_ahorro",
        body=_CUOTA_INTEGRA_AHORRO_BODY,
    ),
    formula(
        casilla_id="0595",
        formula_id="modelo_100.2026.g.cuota_integra_total",
        body=add_op(
            add_op(ref("0550"), ref("0551")),
            add_op(ref("0560"), ref("0561")),
        ),
    ),
    formula(
        casilla_id="0630",
        formula_id="modelo_100.2026.g.total_deducciones",
        body=add_op(ref("0620"), ref("0622")),
    ),
    formula(
        casilla_id="0698",
        formula_id="modelo_100.2026.g.cuota_liquida_total",
        body=clamp_pos(
            sub_op(
                sub_op(ref("0595"), ref("0630")),
                ref("0612"),
            ),
        ),
    ),
    formula(
        casilla_id="0720",
        formula_id="modelo_100.2026.g.cuota_diferencial",
        body=sub_op(
            sub_op(ref("0698"), ref("0699")),
            ref("0700"),
        ),
    ),
)
"""Engine formula bindings for the 2026 Anexo G computed casillas."""


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
