"""Modelo 303 ruleset covering the full 2025 fiscal year (#183).

The 2024 and 2025 rulesets are mechanically identical because the
LIVA arts. 90 / 91 régimen general rates were not amended between
the two years (see the doc §"Mid-year rule
changes"). The shared casilla and citation tuples are imported
from the 2024 sibling; the formulas mirror the 2024 set with
year-stamped ``formula_id`` strings so audit ledgers can
distinguish the fiscal year of derivation.

The separate file simplifies any future divergence (e.g., a
hypothetical mid-year rate change effective 2025-Q3 would land
here without touching the 2024 ruleset).
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

_EFFECTIVE_FROM = date(2025, 1, 1)
_EFFECTIVE_TO = date(2025, 12, 31)


_FORMULAS_2025 = (
    formula(
        casilla_id="02",
        formula_id="modelo_303.2025.tipo_superreducido",
        body=lit(4),
    ),
    formula(
        casilla_id="03",
        formula_id="modelo_303.2025.cuota_superreducido",
        body=percent(param("iva.rate_superreducido"), ref("01")),
    ),
    formula(
        casilla_id="05",
        formula_id="modelo_303.2025.tipo_reducido",
        body=lit(10),
    ),
    formula(
        casilla_id="06",
        formula_id="modelo_303.2025.cuota_reducido",
        body=percent(param("iva.rate_reducido"), ref("04")),
    ),
    formula(
        casilla_id="08",
        formula_id="modelo_303.2025.tipo_general",
        body=lit(21),
    ),
    formula(
        casilla_id="09",
        formula_id="modelo_303.2025.cuota_general",
        body=percent(param("iva.rate_general"), ref("07")),
    ),
    formula(
        casilla_id="44",
        formula_id="modelo_303.2025.total_deducible",
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
        formula_id="modelo_303.2025.resultado_regimen_general",
        body=sub_op(add_op(ref("03"), ref("06"), ref("09")), ref("44")),
    ),
    formula(
        casilla_id="64",
        formula_id="modelo_303.2025.suma_resultados",
        body=add_op(ref("45"), lit("0")),
    ),
    formula(
        casilla_id="66",
        formula_id="modelo_303.2025.atribuible_estado",
        body=div_op(percent(ref("65"), ref("64")), lit("100")),
    ),
    formula(
        casilla_id="69",
        formula_id="modelo_303.2025.resultado",
        body=sub_op(ref("66"), ref("67")),
    ),
    formula(
        casilla_id="71",
        formula_id="modelo_303.2025.resultado_autoliquidacion",
        body=add_op(ref("69"), lit("0")),
    ),
)


_PARAMETERS_2025 = ParameterTable(
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
    ruleset_id="modelo_303.2025",
    modelo=ModeloCode.MODELO_303,
    effective_from=_EFFECTIVE_FROM,
    effective_to=_EFFECTIVE_TO,
    casillas=_CASILLAS_2024,
    formulas=_FORMULAS_2025,
    parameters=_PARAMETERS_2025,
    legal_citations=_CITATIONS_2024,
)
