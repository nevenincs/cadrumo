"""Modelo 200 ruleset covering ejercicio 2026.

This ruleset deliberately keeps Modelo 200's current verified surface to
page-14 liquidación arithmetic. The fiscal-year 2026 annual Modelo 200
order is not available on BOE as of 2026-04-28, so the ruleset is based
on consolidated LIS/RIS formulas that remain year-invariant for the
casillas modeled here.
"""

from __future__ import annotations

from datetime import date

from ...models import LegalCitationSource, ModeloCode
from .._ruleset import ParameterTable, Ruleset
from ._common import make_citation
from .modelo_200_2024 import _make_casillas, _make_formulas

_EFFECTIVE_FROM = date(2026, 1, 1)
_EFFECTIVE_TO = date(2026, 12, 31)

_CITATIONS = (
    make_citation(
        LegalCitationSource.LEY,
        "29-30",
        "Artículos 29 y 30 Ley 27/2014 (LIS) — tipo de gravamen aplicable "
        "y cuota íntegra por aplicación del tipo a la base imponible.",
        url="https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328&p=20260428&tn=1",
    ),
    make_citation(
        LegalCitationSource.LEY,
        "30+39+125.3",
        "Artículos 30, 39.2 y 125.3 Ley 27/2014 (LIS) — cuota líquida, "
        "abono de deducciones monetizables e incremento por pérdida de "
        "beneficios fiscales.",
        url="https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328&p=20260428&tn=1",
    ),
    make_citation(
        LegalCitationSource.REGLAMENTO,
        "RD 634/2015",
        "Real Decreto 634/2015 (RIS) — desarrollo reglamentario del "
        "Impuesto sobre Sociedades y contexto de amortización/declaración.",
        url="https://www.boe.es/buscar/act.php?id=BOE-A-2015-7771&p=20260428&tn=1",
    ),
)

_CASILLAS = _make_casillas(_CITATIONS)
_FORMULAS = _make_formulas(2026)
_PARAMETERS = ParameterTable(entries={})

RULESET: Ruleset = Ruleset(
    ruleset_id="modelo_200.2026",
    modelo=ModeloCode.MODELO_200,
    effective_from=_EFFECTIVE_FROM,
    effective_to=_EFFECTIVE_TO,
    casillas=_CASILLAS,
    formulas=_FORMULAS,
    parameters=_PARAMETERS,
    legal_citations=_CITATIONS,
)
