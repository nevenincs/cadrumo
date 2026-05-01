"""Modelo 111 ruleset covering the full 2025 fiscal year.

Modelo 111 is the quarterly withholdings form for rendimientos del
trabajo, actividades económicas, premios, ganancias patrimoniales,
contraprestaciones en especie, and cesión del derecho de imagen
retained by any employer / pagador.

The form groups casillas in triples — ``(perceptores, percepciones,
retenciones)`` — for each of the six rubros above. Formula coverage:

- ``09 = 19% x 08`` — retención fija sobre premios en metálico
  (LIRPF art. 101.7 implementado vía RIRPF art. 99; el Reglamento
  art. 105 cubre transmisiones de IIC — NO premios).
- ``12 = 19% x 11`` — retención fija sobre ganancias patrimoniales
  gravadas (LIRPF art. 101.2 + RIRPF art. 100 — el artículo tiene
  solo dos apartados, sin sub-letras).
- ``28 = 03 + 06 + 09 + 12 + 15 + 18`` — total retenciones e ingresos a
  cuenta (sum of the six per-rubro retention casillas).
- ``30 = 28 - 29`` — resultado a ingresar (total retenciones menos los
  resultados negativos de declaraciones anteriores).

Per-rubro retention rates for rendimientos del trabajo (tabla
trabajadores) and actividades económicas (tipo variable) depend on
tabla inputs + categoría-profesional mapping and land in sub-EPIC
#305-Modelo-111-full. The above fixed-rate + sum relationships are
the minimum set that must hold on every 111 filing regardless of
rubro mix.
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
    make_citation(
        LegalCitationSource.REGLAMENTO,
        "100",
        "Artículo 100 RD 439/2007 (Reglamento del IRPF) — importe de "
        "las retenciones sobre rendimientos del arrendamiento o "
        "subarrendamiento de bienes inmuebles urbanos (19% en art. "
        "100.1; reducción 60% Ceuta/Melilla en art. 100.2). Modelo 111 "
        "casillas 11-12 map to rendimientos-gravados por LIRPF art. "
        "101.2 implementados vía este artículo.",
        url="https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820",
    ),
    make_citation(
        LegalCitationSource.REGLAMENTO,
        "99",
        "Artículo 99 RD 439/2007 (Reglamento del IRPF) — obligación "
        "general de practicar pagos a cuenta; implementa el 19% de "
        "retención sobre premios en metálico (LIRPF art. 101.7) y los "
        "tipos fijos sobre el resto de rendimientos gravados. "
        "correction: prior citation of art. 105.1 for premios was wrong "
        "(art. 105 covers IIC transmisiones, not premios).",
        url="https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820",
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
        casilla_id="08",
        label=_label("Percepciones premios", "Prize perceptions", "Nyeremény jövedelem"),
        computed=False,
    ),
    casilla(
        casilla_id="09",
        label=_label("Retenciones premios", "Prize withholdings", "Nyeremény levonás"),
        computed=True,
        legal_basis=_CITATIONS,
    ),
    casilla(
        casilla_id="11",
        label=_label(
            "Percepciones ganancias patrimoniales",
            "Capital gains perceptions",
            "Vagyonnyereség jövedelem",
        ),
        computed=False,
    ),
    casilla(
        casilla_id="12",
        label=_label("Retenciones ganancias patrimoniales", "Capital gains withholdings", "Vagyonnyereség levonás"),
        computed=True,
        legal_basis=_CITATIONS,
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
            "A deducir: exclusivamente en declaración complementaria",
            "Prior-filing deduction (complementary filings only)",
            "Korábbi bevallásból levonás (kiegészítő bevallás)",
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
        casilla_id="09",
        formula_id="modelo_111.2025.retenciones_premios",
        body=percent(param("irpf.premios_rate"), ref("08")),
    ),
    formula(
        casilla_id="12",
        formula_id="modelo_111.2025.retenciones_ganancias_arrendamiento",
        body=percent(param("irpf.ganancias_arrendamiento_rate"), ref("11")),
    ),
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


_PARAMETERS = ParameterTable(
    entries={
        "irpf.premios_rate": (
            ParameterValue(
                effective_from=_EFFECTIVE_FROM,
                effective_to=_EFFECTIVE_TO,
                value=Decimal("0.19"),
            ),
        ),
        "irpf.ganancias_arrendamiento_rate": (
            ParameterValue(
                effective_from=_EFFECTIVE_FROM,
                effective_to=_EFFECTIVE_TO,
                value=Decimal("0.19"),
            ),
        ),
    }
)


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
