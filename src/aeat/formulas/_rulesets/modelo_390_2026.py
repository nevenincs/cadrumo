"""Modelo 390 ruleset covering the full 2026 fiscal year.

Structurally identical to :mod:`modelo_390_2024` and
:mod:`modelo_390_2025`. The BOE-grounded algebraic chain encoded by
Modelo 390 is unchanged across 2024, 2025, and 2026: LIVA arts. 90 /
91 / 92 / 102 / 107 / 164 and RIVA art. 71.7 were not amended for
2026, and Orden EHA/3111/2009 is amended only for non-substantive
form metadata each year.

The 2026 small-enterprise franquicia regime introduced by Directiva
(UE) 2020/285 is an opt-in regime under which a participating
taxpayer drops out of the standard Modelo 390 surface entirely. It is
not a modification of the régimen-general result chain encoded here
and is tracked by the IVA complexity sub-EPIC ``#345`` rather than
this base ruleset. The rule-delta manifest at
``.vault/reference/2026-04-27-modelo-390-rule-delta-reference.md``
documents the deferral.

This module re-imports ``_CASILLAS`` and ``_CITATIONS`` from the
2024 master, declares its own year-stamped formula tuple plus an
empty ``ParameterTable``, and binds to the 2026 effective range.
"""

from __future__ import annotations

from datetime import date

from ...models import ModeloCode
from .._ruleset import ParameterTable, Ruleset
from ._common import (
    add_op,
    clamp_pos,
    formula,
    lit,
    ref,
    sub_op,
)
from .modelo_390_2024 import (
    _CASILLAS as _CASILLAS_2024,
)
from .modelo_390_2024 import (
    _CITATIONS as _CITATIONS_2024,
)

_EFFECTIVE_FROM = date(2026, 1, 1)
_EFFECTIVE_TO = date(2026, 12, 31)


_FORMULAS_2026 = (
    formula(
        casilla_id="104",
        formula_id="modelo_390.2026.iva_soportado_total",
        body=add_op(ref("100"), ref("101")),
    ),
    formula(
        casilla_id="105",
        formula_id="modelo_390.2026.resultado_regimen_general",
        body=sub_op(ref("96"), ref("104")),
    ),
    formula(
        casilla_id="190",
        formula_id="modelo_390.2026.suma_resultado",
        body=add_op(ref("105"), ref("108"), ref("109")),
    ),
    formula(
        casilla_id="191",
        formula_id="modelo_390.2026.cuota_resultante_anual",
        body=sub_op(ref("190"), ref("662")),
    ),
    formula(
        casilla_id="192",
        formula_id="modelo_390.2026.total_a_ingresar",
        body=clamp_pos(ref("191")),
    ),
    formula(
        casilla_id="193",
        formula_id="modelo_390.2026.total_a_devolver",
        body=clamp_pos(sub_op(lit("0"), ref("191"))),
    ),
)


_PARAMETERS = ParameterTable(entries={})


RULESET: Ruleset = Ruleset(
    ruleset_id="modelo_390.2026",
    modelo=ModeloCode.MODELO_390,
    effective_from=_EFFECTIVE_FROM,
    effective_to=_EFFECTIVE_TO,
    casillas=_CASILLAS_2024,
    formulas=_FORMULAS_2026,
    parameters=_PARAMETERS,
    legal_citations=_CITATIONS_2024,
)
