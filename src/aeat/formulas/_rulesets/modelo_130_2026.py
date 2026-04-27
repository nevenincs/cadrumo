"""Modelo 130 ruleset covering the full 2026 fiscal year.

The 2024, 2025, and 2026 rulesets are mechanically identical — RIRPF
art. 110 (RD 439/2007) was not amended between 2024 and 2026:

- The general 20 % rate (art. 110.1.a), the 2 % agraria rate
  (art. 110.1.c), the casilla-13 minoración brackets at 9 000 /
  10 000 / 11 000 / 12 000 € (art. 110.3.c), and the vivienda-
  habitual 2 % deduction with 660,14 € quarterly cap (art. 110.3.d)
  are unchanged from the post-RD 1003/2014 + RD 960/2013 baseline.
- RD 253/2025 (the only 2025 modification of RIRPF) touched art. 69
  (information obligations), not art. 110.

The separate ruleset file simplifies future divergence (e.g., the
La Palma 60 % reduction overlay tracked under EPIC #316, which
lands as a dedicated territorial overlay rather than a base-
ruleset amendment). The rule-delta manifest at
``.vault/reference/2026-130-rule-delta.md`` documents the 2024 →
2025 → 2026 trail with BOE citations.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ...models import ModeloCode
from .._ruleset import ParameterTable, ParameterValue, Ruleset
from ._common import (
    add_op,
    clamp_pos,
    formula,
    lit,
    max_op,
    param,
    percent,
    ref,
    sub_op,
)
from .modelo_130_2024 import (
    _CASILLAS as _CASILLAS_2024,
)
from .modelo_130_2024 import (
    _CITATIONS as _CITATIONS_2024,
)

_EFFECTIVE_FROM = date(2026, 1, 1)
_EFFECTIVE_TO = date(2026, 12, 31)


_FORMULAS = (
    formula(
        casilla_id="03",
        formula_id="modelo_130.2026.rendimiento_neto",
        body=sub_op(ref("01"), ref("02")),
    ),
    formula(
        casilla_id="04",
        formula_id="modelo_130.2026.pago_fraccionado",
        body=clamp_pos(percent(param("irpf.trimestral_rate"), ref("03"))),
    ),
    formula(
        casilla_id="07",
        formula_id="modelo_130.2026.resultado_apartado_i",
        body=sub_op(sub_op(ref("04"), ref("05")), ref("06")),
    ),
    formula(
        casilla_id="09",
        formula_id="modelo_130.2026.pago_fraccionado_agraria",
        body=percent(param("agraria.trimestral_rate"), ref("08")),
    ),
    formula(
        casilla_id="11",
        formula_id="modelo_130.2026.resultado_apartado_ii",
        body=sub_op(ref("09"), ref("10")),
    ),
    formula(
        casilla_id="12",
        formula_id="modelo_130.2026.suma_parciales",
        body=max_op(lit("0"), add_op(ref("07"), ref("11"))),
    ),
    formula(
        casilla_id="14",
        formula_id="modelo_130.2026.neto_tras_minoracion",
        body=sub_op(ref("12"), ref("13")),
    ),
    formula(
        casilla_id="17",
        formula_id="modelo_130.2026.diferencia",
        body=sub_op(sub_op(ref("14"), ref("15")), ref("16")),
    ),
    formula(
        casilla_id="19",
        formula_id="modelo_130.2026.resultado_final",
        body=sub_op(ref("17"), ref("18")),
    ),
)


_PARAMETERS = ParameterTable(
    entries={
        "irpf.trimestral_rate": (
            ParameterValue(
                effective_from=_EFFECTIVE_FROM,
                effective_to=_EFFECTIVE_TO,
                value=Decimal("0.20"),
            ),
        ),
        "agraria.trimestral_rate": (
            ParameterValue(
                effective_from=_EFFECTIVE_FROM,
                effective_to=_EFFECTIVE_TO,
                value=Decimal("0.02"),
            ),
        ),
    }
)


RULESET: Ruleset = Ruleset(
    ruleset_id="modelo_130.2026",
    modelo=ModeloCode.MODELO_130,
    effective_from=_EFFECTIVE_FROM,
    effective_to=_EFFECTIVE_TO,
    casillas=_CASILLAS_2024,
    formulas=_FORMULAS,
    parameters=_PARAMETERS,
    legal_citations=_CITATIONS_2024,
)
