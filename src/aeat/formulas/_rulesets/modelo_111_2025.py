"""Modelo 111 ruleset covering the full 2025 fiscal year.

Modelo 111 is the quarterly withholdings form for rendimientos del
trabajo, actividades económicas, premios, ganancias patrimoniales,
contraprestaciones en especie, and cesión del derecho de imagen
retained by any employer / pagador.

The form groups casillas in triples — ``(perceptores, percepciones,
retenciones)`` — for each of the six rubros above. Only the total
block (casillas 28-30) is constrained by AEAT formula:

- ``28 = 03 + 06 + 09 + 12 + 15 + 18`` — total retenciones e ingresos a
  cuenta (sum of the six per-rubro retention casillas).
- ``30 = 28 - 29`` — resultado a ingresar (total retenciones minus
  resultados negativos de declaraciones anteriores).

The per-rubro retention rates vary (15% actividades profesionales,
variable IRPF tabla trabajadores, 19% ganancias patrimoniales…) so
this MVP ruleset verifies the sum-and-difference relationships only.
A richer ruleset per rubro would require tabla-trabajadores input
plus categoría-profesional mapping, tracked under sub-EPIC
#305-Modelo-111-full.
"""

from __future__ import annotations

from datetime import date

from ...i18n import Translatable
from ...models import LegalCitationSource, ModeloCode
from .._ruleset import ParameterTable, Ruleset
from ._common import (
    add_op,
    casilla,
    formula,
    make_citation,
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
        "99-101",
        "Artículos 99-101 Ley 35/2006 (IRPF) — régimen general de "
        "retenciones e ingresos a cuenta del IRPF sobre rendimientos "
        "del trabajo, actividades económicas, premios, ganancias y "
        "contraprestaciones en especie. Instrucciones Modelo 111 fijan "
        "la suma de retenciones y el cálculo del resultado a ingresar.",
        url="https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764",
    ),
)


_CASILLAS = (
    casilla(
        casilla_id="03",
        label=_label("Retenciones rendimientos del trabajo", "Work income withholdings", "Munkajövedelem levonás"),
        computed=False,
    ),
    casilla(
        casilla_id="06",
        label=_label("Retenciones actividades económicas", "Business income withholdings", "Gazdasági tev. levonás"),
        computed=False,
    ),
    casilla(
        casilla_id="09",
        label=_label("Retenciones premios", "Prize withholdings", "Nyeremény levonás"),
        computed=False,
    ),
    casilla(
        casilla_id="12",
        label=_label("Retenciones ganancias patrimoniales", "Capital gains withholdings", "Vagyonnyereség levonás"),
        computed=False,
    ),
    casilla(
        casilla_id="15",
        label=_label("Retenciones contraprestaciones en especie", "In-kind withholdings", "Természetbeni levonás"),
        computed=False,
    ),
    casilla(
        casilla_id="18",
        label=_label("Retenciones cesión de imagen", "Image rights withholdings", "Képmás-jog levonás"),
        computed=False,
    ),
    casilla(
        casilla_id="28",
        label=_label("Total retenciones", "Total withholdings", "Levonás összesen"),
        computed=True,
        legal_basis=_CITATIONS,
    ),
    casilla(
        casilla_id="29",
        label=_label(
            "Resultados negativos declaraciones anteriores",
            "Negative results from prior filings",
            "Korábbi bevallások negatív eredményei",
        ),
        computed=False,
    ),
    casilla(
        casilla_id="30",
        label=_label("Resultado a ingresar", "Net amount payable", "Fizetendő eredmény"),
        computed=True,
        legal_basis=_CITATIONS,
    ),
)


_FORMULAS = (
    formula(
        casilla_id="28",
        formula_id="modelo_111.2025.total_retenciones",
        body=add_op(
            ref("03"),
            ref("06"),
            ref("09"),
            ref("12"),
            ref("15"),
            ref("18"),
        ),
    ),
    formula(
        casilla_id="30",
        formula_id="modelo_111.2025.resultado_a_ingresar",
        body=sub_op(ref("28"), ref("29")),
    ),
)


_PARAMETERS = ParameterTable(entries={})


RULESET: Ruleset = Ruleset(
    ruleset_id="modelo_111.2025",
    modelo=ModeloCode.MODELO_111,
    effective_from=_EFFECTIVE_FROM,
    effective_to=_EFFECTIVE_TO,
    casillas=_CASILLAS,
    formulas=_FORMULAS,
    parameters=_PARAMETERS,
    legal_citations=_CITATIONS,
)
