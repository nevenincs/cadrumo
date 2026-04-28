"""Modelo 100 Anexo F — bases imponibles + reducciones + minimos (2026)."""

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
from .anexo_f_2025 import CASILLAS, CITATIONS

EFFECTIVE_FROM = date(2026, 1, 1)
EFFECTIVE_TO = date(2026, 12, 31)


_BIG_BODY = add_op(
    add_op(
        add_op(ref("0022"), ref("0107")),
        add_op(ref("0085"), ref("0205")),
    ),
    add_op(
        add_op(ref("0240"), ref("0260")),
        ref("0399"),
    ),
)


_BIA_BODY = add_op(ref("0049"), ref("0400"))


FORMULAS = (
    formula(
        casilla_id="0432",
        formula_id="modelo_100.2026.f.base_imponible_general",
        body=_BIG_BODY,
    ),
    formula(
        casilla_id="0460",
        formula_id="modelo_100.2026.f.base_imponible_ahorro",
        body=_BIA_BODY,
    ),
    formula(
        casilla_id="0500",
        formula_id="modelo_100.2026.f.minimo_personal_familiar_total",
        body=add_op(
            add_op(ref("0505"), ref("0510")),
            add_op(ref("0515"), ref("0520")),
        ),
    ),
    formula(
        casilla_id="0545",
        formula_id="modelo_100.2026.f.base_liquidable_general",
        body=clamp_pos(
            sub_op(
                sub_op(ref("0432"), ref("0445")),
                ref("0455"),
            ),
        ),
    ),
    formula(
        casilla_id="0555",
        formula_id="modelo_100.2026.f.base_liquidable_ahorro",
        body=ref("0460"),
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
