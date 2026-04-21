"""Modelo 115 ruleset covering the full 2025 fiscal year.

Modelo 115 is the quarterly withholdings form for urban-real-estate
arrendamiento (commercial office/commercial premises). It has six
casillas:

- 01: nº arrendadores
- 02: base de retención
- 03: retenciones (percent of 02)
- 04: ingresos a cuenta
- 05: resultados negativos anteriores
- 06: resultado a ingresar

Two algebraic formulas:

- ``03 = 19% x 02`` (art. 100.2 LIRPF, tipo fijo desde 2016).
- ``06 = 03 + 04 - 05`` (resultado a ingresar — instrucciones AEAT).

Parameter ``irpf.arrendamientos_rate`` lets us widen to historical
years without code changes; for 2016 onward AEAT has kept the 19%
rate, so a single effective-range value suffices.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ...i18n import Translatable
from ...models import LegalCitationSource, ModeloCode
from .._ruleset import ParameterTable, ParameterValue, Ruleset
from ._common import (
    add_op,
    casilla,
    formula,
    make_citation,
    param,
    percent,
    ref,
    sub_op,
)

_EFFECTIVE_FROM = date(2025, 1, 1)
_EFFECTIVE_TO = date(2025, 12, 31)


def _label(es: str, en: str, hu: str) -> Translatable:
    return {"es": es, "en": en, "hu": hu}


_CITATIONS = (
    make_citation(
        LegalCitationSource.LEY,
        "100.2",
        "Artículo 100.2 Ley 35/2006 (IRPF) — tipo de retención aplicable "
        "a los rendimientos procedentes del arrendamiento o "
        "subarrendamiento de bienes inmuebles urbanos. Tipo fijo del "
        "19% desde 2016.",
        url="https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764",
    ),
)


_CASILLAS = (
    casilla(
        casilla_id="01",
        label=_label(
            "Nº de arrendadores",
            "Number of landlords",
            "Bérbeadók száma",
        ),
        computed=False,
    ),
    casilla(
        casilla_id="02",
        label=_label(
            "Base de retención",
            "Withholding base",
            "Levonási alap",
        ),
        computed=False,
    ),
    casilla(
        casilla_id="03",
        label=_label(
            "Retenciones e ingresos a cuenta",
            "Withholdings",
            "Levonások",
        ),
        computed=True,
        legal_basis=_CITATIONS,
    ),
    casilla(
        casilla_id="04",
        label=_label(
            "Ingresos a cuenta por retribución en especie",
            "In-kind payments on account",
            "Természetbeni előlegek",
        ),
        computed=False,
    ),
    casilla(
        casilla_id="05",
        label=_label(
            "Resultados negativos declaraciones anteriores",
            "Negative results from prior filings",
            "Korábbi bevallások negatív eredményei",
        ),
        computed=False,
    ),
    casilla(
        casilla_id="06",
        label=_label(
            "Resultado a ingresar",
            "Net amount payable",
            "Fizetendő eredmény",
        ),
        computed=True,
        legal_basis=_CITATIONS,
    ),
)


_FORMULAS = (
    formula(
        casilla_id="03",
        formula_id="modelo_115.2025.retenciones",
        body=percent(param("irpf.arrendamientos_rate"), ref("02")),
    ),
    formula(
        casilla_id="06",
        formula_id="modelo_115.2025.resultado_a_ingresar",
        body=sub_op(add_op(ref("03"), ref("04")), ref("05")),
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
    ruleset_id="modelo_115.2025",
    modelo=ModeloCode.MODELO_115,
    effective_from=_EFFECTIVE_FROM,
    effective_to=_EFFECTIVE_TO,
    casillas=_CASILLAS,
    formulas=_FORMULAS,
    parameters=_PARAMETERS,
    legal_citations=_CITATIONS,
)
