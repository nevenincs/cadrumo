"""Modelo 180 ruleset covering the full 2025 fiscal year.

Modelo 180 is the annual informativa that rolls up the four quarterly
Modelo 115 filings (retenciones sobre arrendamientos urbanos). MVP
targets the 4-casilla summary block:

- casilla 01 (total perceptores — arrendadores).
- casilla 02 (total base retencion).
- casilla 03 (total retenciones e ingresos a cuenta; 19% x 02 per
  art. 100.3.a RIRPF).
- casilla 04 (total ingresos a cuenta por retribuciones en especie).

Only one algebraic formula holds at aggregation level:

- casilla 03 = 19% x casilla 02 (same rate as the quarterly Modelo 115
  because 180 is the annual aggregation of 115 filings).

Legal base: Ley 35/2006 (LIRPF) art. 101.8, RD 439/2007 (Reglamento)
art. 100.3.a.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ...i18n import Translatable
from ...models import LegalCitationSource, ModeloCode
from .._ruleset import ParameterTable, ParameterValue, Ruleset
from ._common import (
    casilla,
    formula,
    make_citation,
    param,
    percent,
    ref,
)

_EFFECTIVE_FROM = date(2025, 1, 1)
_EFFECTIVE_TO = date(2025, 12, 31)


def _label(es: str, en: str, hu: str) -> Translatable:
    return {"es": es, "en": en, "hu": hu}


_CITATIONS = (
    make_citation(
        LegalCitationSource.REGLAMENTO,
        "100.3.a",
        "Artículo 100.3.a RD 439/2007 — tipo fijo del 19% de retención "
        "sobre arrendamientos urbanos; aplica tanto al Modelo 115 "
        "trimestral como a su resumen anual Modelo 180.",
        url="https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820",
    ),
)


_CASILLAS = (
    casilla(
        casilla_id="01",
        label=_label("Total perceptores", "Total recipients", "Összes bérbeadó"),
        computed=False,
    ),
    casilla(
        casilla_id="02",
        label=_label("Total base retencion", "Total withholding base", "Teljes levonási alap"),
        computed=False,
    ),
    casilla(
        casilla_id="03",
        label=_label("Total retenciones", "Total withholdings", "Teljes levonás"),
        computed=True,
        legal_basis=_CITATIONS,
    ),
    casilla(
        casilla_id="04",
        label=_label(
            "Total ingresos a cuenta por retribuciones en especie",
            "In-kind payments on account",
            "Természetbeni előlegek",
        ),
        computed=False,
    ),
)


_FORMULAS = (
    formula(
        casilla_id="03",
        formula_id="modelo_180.2025.total_retenciones",
        body=percent(param("irpf.arrendamientos_rate"), ref("02")),
    ),
)


_PARAMETERS = ParameterTable(
    entries={
        "irpf.arrendamientos_rate": (
            ParameterValue(
                effective_from=_EFFECTIVE_FROM,
                effective_to=_EFFECTIVE_TO,
                value=Decimal("0.19"),
            ),
        ),
    }
)


RULESET: Ruleset = Ruleset(
    ruleset_id="modelo_180.2025",
    modelo=ModeloCode.MODELO_180,
    effective_from=_EFFECTIVE_FROM,
    effective_to=_EFFECTIVE_TO,
    casillas=_CASILLAS,
    formulas=_FORMULAS,
    parameters=_PARAMETERS,
    legal_citations=_CITATIONS,
)
