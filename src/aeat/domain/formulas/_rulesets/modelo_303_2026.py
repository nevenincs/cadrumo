"""Modelo 303 ruleset covering the full 2026 fiscal year.

The scoped régimen-general liquidación arithmetic is unchanged from
2024 and 2025:

- LIVA art. 90 keeps the general IVA rate at 21 %.
- LIVA art. 91 keeps the reduced and super-reduced rates used by this
  ruleset at 10 % and 4 %.
- LIVA arts. 92-100 keep deductible-input VAT as taxpayer-supplied
  casillas in this ruleset; deeper prorrata derivation remains outside
  this formula surface.
- RIVA art. 71 and Orden EHA/3786/2008 continue to ground Modelo 303
  as the periodic autoliquidación form.

The 2026 file intentionally mirrors the 2024 / 2025 formula graph with
year-scoped formula identifiers and a 2026 ``ParameterTable``. Form
families not represented in the existing M303 ruleset, including
franquicia / small-enterprise special-regime treatment, simplified
regime, recargo de equivalencia, and regional regimes, remain outside
this base régimen-general ruleset and are tracked by the IVA complexity
workstream.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ...modelos import ModeloCode
from .._ruleset import ParameterTable, ParameterValue, Ruleset
from ._common import (
    add_op,
    div_op,
    formula,
    lit,
    param,
    percent,
    ref,
    sub_op,
)
from .modelo_303_2024 import (
    _CASILLAS as _CASILLAS_2024,
)
from .modelo_303_2024 import (
    _CITATIONS as _CITATIONS_2024,
)

_EFFECTIVE_FROM = date(2026, 1, 1)
_EFFECTIVE_TO = date(2026, 12, 31)


_FORMULAS_2026 = (
    formula(
        casilla_id="02",
        formula_id="modelo_303.2026.tipo_superreducido",
        body=lit(4),
    ),
    formula(
        casilla_id="03",
        formula_id="modelo_303.2026.cuota_superreducido",
        body=percent(param("iva.rate_superreducido"), ref("01")),
    ),
    formula(
        casilla_id="05",
        formula_id="modelo_303.2026.tipo_reducido",
        body=lit(10),
    ),
    formula(
        casilla_id="06",
        formula_id="modelo_303.2026.cuota_reducido",
        body=percent(param("iva.rate_reducido"), ref("04")),
    ),
    formula(
        casilla_id="08",
        formula_id="modelo_303.2026.tipo_general",
        body=lit(21),
    ),
    formula(
        casilla_id="09",
        formula_id="modelo_303.2026.cuota_general",
        body=percent(param("iva.rate_general"), ref("07")),
    ),
    formula(
        casilla_id="44",
        formula_id="modelo_303.2026.total_deducible",
        body=add_op(
            ref("29"),
            ref("31"),
            ref("33"),
            ref("35"),
            ref("37"),
            ref("39"),
            ref("40"),
            ref("41"),
            ref("42"),
            ref("43"),
        ),
    ),
    formula(
        casilla_id="45",
        formula_id="modelo_303.2026.resultado_regimen_general",
        body=sub_op(add_op(ref("03"), ref("06"), ref("09")), ref("44")),
    ),
    formula(
        casilla_id="64",
        formula_id="modelo_303.2026.suma_resultados",
        body=add_op(ref("45"), lit("0")),
    ),
    formula(
        casilla_id="66",
        formula_id="modelo_303.2026.atribuible_estado",
        body=div_op(percent(ref("65"), ref("64")), lit("100")),
    ),
    formula(
        casilla_id="69",
        formula_id="modelo_303.2026.resultado",
        body=sub_op(ref("66"), ref("67")),
    ),
    formula(
        casilla_id="71",
        formula_id="modelo_303.2026.resultado_autoliquidacion",
        body=add_op(ref("69"), lit("0")),
    ),
)


_PARAMETERS_2026 = ParameterTable(
    entries={
        "iva.rate_general": (
            ParameterValue(
                effective_from=_EFFECTIVE_FROM,
                effective_to=_EFFECTIVE_TO,
                value=Decimal("0.21"),
            ),
        ),
        "iva.rate_reducido": (
            ParameterValue(
                effective_from=_EFFECTIVE_FROM,
                effective_to=_EFFECTIVE_TO,
                value=Decimal("0.10"),
            ),
        ),
        "iva.rate_superreducido": (
            ParameterValue(
                effective_from=_EFFECTIVE_FROM,
                effective_to=_EFFECTIVE_TO,
                value=Decimal("0.04"),
            ),
        ),
    }
)


RULESET: Ruleset = Ruleset(
    ruleset_id="modelo_303.2026",
    modelo=ModeloCode.MODELO_303,
    effective_from=_EFFECTIVE_FROM,
    effective_to=_EFFECTIVE_TO,
    casillas=_CASILLAS_2024,
    formulas=_FORMULAS_2026,
    parameters=_PARAMETERS_2026,
    legal_citations=_CITATIONS_2024,
)
