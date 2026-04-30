"""Modelo 200 ruleset covering ejercicio 2025.

The page-14 liquidación surface is unchanged from the 2024 ruleset:
the form prints the applicable statutory rate in casilla 00558 as a
whole-percent value, and the ruleset verifies the invariant arithmetic
from base imponible to cuota íntegra, cuota diferencial, and líquido a
ingresar or devolver.

As of 2026-04-28 the annual Orden Ministerial approving the Modelo 200
layout for periods initiated in 2025 has not been published on BOE. The
ruleset is therefore anchored to the consolidated LIS/RIS arithmetic and
keeps the same extractor-visible page-14 casillas as Orden HAC/657/2025.
"""

from __future__ import annotations

from datetime import date

from ...modelos import LegalCitationSource, ModeloCode
from .._ruleset import ParameterTable, Ruleset
from ._common import make_citation
from .modelo_200_2024 import _make_casillas, _make_formulas

_EFFECTIVE_FROM = date(2025, 1, 1)
_EFFECTIVE_TO = date(2025, 12, 31)

_CITATIONS = (
    make_citation(
        LegalCitationSource.LEY,
        "29-30",
        "Artículos 29 y 30 Ley 27/2014 (LIS) — tipo de gravamen aplicable "
        "y cuota íntegra por aplicación del tipo a la base imponible.",
        url="https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328",
    ),
    make_citation(
        LegalCitationSource.LEY,
        "30+39+125.3",
        "Artículos 30, 39.2 y 125.3 Ley 27/2014 (LIS) — cuota líquida, "
        "abono de deducciones monetizables e incremento por pérdida de "
        "beneficios fiscales.",
        url="https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328",
    ),
    make_citation(
        LegalCitationSource.REGLAMENTO,
        "RD 634/2015",
        "Real Decreto 634/2015 (RIS) — desarrollo reglamentario del "
        "Impuesto sobre Sociedades y contexto de amortización/declaración.",
        url="https://www.boe.es/buscar/act.php?id=BOE-A-2015-7771",
    ),
)

_CASILLAS = _make_casillas(_CITATIONS)
_FORMULAS = _make_formulas(2025)
_PARAMETERS = ParameterTable(entries={})

RULESET: Ruleset = Ruleset(
    ruleset_id="modelo_200.2025",
    modelo=ModeloCode.MODELO_200,
    effective_from=_EFFECTIVE_FROM,
    effective_to=_EFFECTIVE_TO,
    casillas=_CASILLAS,
    formulas=_FORMULAS,
    parameters=_PARAMETERS,
    legal_citations=_CITATIONS,
)
