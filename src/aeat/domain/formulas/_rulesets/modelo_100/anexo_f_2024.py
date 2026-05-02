"""Define the Modelo 100 Anexo F ruleset for the 2024 ejercicio.

Bases imponibles, reducciónes, and the mínimo personal y familiar share
the structural surface defined for 2025 in
:mod:`aeat.domain.formulas._rulesets.modelo_100.anexo_f_2025`. LIRPF
arts. 47-61 are unchanged in 2024, so this module re-exports the 2025
:data:`CASILLAS` and :data:`CITATIONS` and only redeclares the
year-scoped :data:`FORMULAS` and effective-date constants.
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
from .anexo_f_2025 import CASILLAS, CITATIONS

EFFECTIVE_FROM = date(2024, 1, 1)
"""First day of the ejercicio in which this Anexo F ruleset applies."""

EFFECTIVE_TO = date(2024, 12, 31)
"""Last day of the ejercicio in which this Anexo F ruleset applies."""


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
        formula_id="modelo_100.2024.f.base_imponible_general",
        body=_BIG_BODY,
    ),
    formula(
        casilla_id="0460",
        formula_id="modelo_100.2024.f.base_imponible_ahorro",
        body=_BIA_BODY,
    ),
    formula(
        casilla_id="0500",
        formula_id="modelo_100.2024.f.minimo_personal_familiar_total",
        body=add_op(
            add_op(ref("0505"), ref("0510")),
            add_op(ref("0515"), ref("0520")),
        ),
    ),
    formula(
        casilla_id="0545",
        formula_id="modelo_100.2024.f.base_liquidable_general",
        body=clamp_pos(
            sub_op(
                sub_op(ref("0432"), ref("0445")),
                ref("0455"),
            ),
        ),
    ),
    formula(
        casilla_id="0555",
        formula_id="modelo_100.2024.f.base_liquidable_ahorro",
        body=ref("0460"),
    ),
)
"""Engine formula bindings for the 2024 Anexo F computed casillas."""


PARAMETERS = ParameterTable(entries={})
"""Anexo F declares no parametric tables."""


__all__ = [
    "CASILLAS",
    "CITATIONS",
    "EFFECTIVE_FROM",
    "EFFECTIVE_TO",
    "FORMULAS",
    "PARAMETERS",
]
