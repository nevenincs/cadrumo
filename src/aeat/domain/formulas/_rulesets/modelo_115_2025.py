"""Modelo 115 ruleset covering the full 2025 fiscal year.

Modelo 115 is the quarterly withholdings form for urban-real-estate
arrendamiento (commercial office / commercial premises). It has six
casillas:

- ``01``: nº arrendadores
- ``02``: base de retención
- ``03``: retenciones (percent of 02)
- ``04``: ingresos a cuenta
- ``05``: resultados negativos anteriores
- ``06``: resultado a ingresar

Two algebraic formulas:

- ``03 = 19 % x 02`` (RIRPF art. 100.1 / RD 439/2007, tipo fijo desde
  2016; the obligation hook is LIRPF art. 101.8).
- ``06 = 03 + 04 - 05`` (resultado a ingresar — instrucciones AEAT).

Parameter ``irpf.arrendamientos_rate`` lets us widen to historical
years without code changes; for 2016 onward AEAT has kept the 19 %
rate, so a single effective-range value suffices.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ....core.i18n import Translatable
from ...modelos import LegalCitationSource, ModeloCode
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
    """Return a :class:`aeat.core.i18n.Translatable` for ES/EN/HU labels."""
    return {"es": es, "en": en, "hu": hu}


_CITATIONS = (
    make_citation(
        LegalCitationSource.LEY,
        "101.8",
        "Artículo 101.8 Ley 35/2006 (IRPF) — enumera los supuestos en que "
        "existe obligación de retener e ingresar a cuenta, y remite al "
        "reglamento la fijación de los tipos aplicables.",
        url="https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764",
    ),
    make_citation(
        LegalCitationSource.REGLAMENTO,
        "100.1",
        "Artículo 100.1 RD 439/2007 (Reglamento del IRPF) — fija el "
        "porcentaje del 19% sobre todos los conceptos satisfechos al "
        "arrendador (excluido el IVA) por arrendamiento o "
        "subarrendamiento de bienes inmuebles urbanos. Art. 100.2 "
        "añade la reducción del 60% para inmuebles en Ceuta/Melilla.",
        url="https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820",
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
            "A deducir: exclusivamente en declaración complementaria",
            "Prior-filing deduction (complementary filings only)",
            "Korábbi bevallásból levonás (kiegészítő bevallás)",
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
"""Modelo 115 ruleset for ejercicio 2025.

A :class:`aeat.domain.formulas._ruleset.Ruleset` carrying the six
arrendamientos urbanos casillas, the two algebraic formulas, and the
19 % ``irpf.arrendamientos_rate`` parameter. Re-exported as
:data:`aeat.domain.formulas._rulesets.MODELO_115_2025`.
"""
