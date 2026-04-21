"""Modelo 200 ruleset covering ejercicio 2024 (filed in 2025).

Modelo 200 is the annual IS / IRNR-EP self-assessment for sociedades.
MVP targets the page-14 liquidación block — the chain of algebraic
relationships that every filing must satisfy regardless of régimen
fiscal (socimis, cooperatives, etc. add lateral casillas but the core
liquidación is invariant).

Formula coverage (page 14):

- casilla 00562 = 00552 x (00558 / 100) (cuota íntegra = base imponible
  x tipo de gravamen; AEAT prints 00558 as whole-percent value).
- casilla 00611 = 00592 - 00599 - 00601 - 00603 - 00605 (cuota
  diferencial = cuota líquida menos retenciones y pagos fraccionados
  del ejercicio).
- casilla 00621 = 00611 + 00619 - 00615 (líquido a ingresar o devolver
  = cuota diferencial más incremento por pérdida beneficios fiscales
  menos abono de deducciones, art. 125 LIS).

Legal base: Ley 27/2014 (LIS), Reglamento IS (RD 634/2015), Orden
HAC/657/2025 (BOE-A-2025-12818, ejercicio 2024). Casillas between
00582 and 00592 (deducciones, bonificaciones) land in sub-EPIC
#305-Modelo-200-full.
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
    percent_from_whole,
    ref,
    sub_op,
)

_EFFECTIVE_FROM = date(2024, 1, 1)
# Ruleset covers the *fiscal year* 2024 (filed during 2025). A separate
# ejercicio-2025 ruleset will land when Orden HAC/657/2025's successor
# is published; narrowing to 2024-12-31 prevents span-overlap conflicts
# in `_spans_overlap` when that ruleset registers (wave 37 H2 fix).
_EFFECTIVE_TO = date(2024, 12, 31)


def _label(es: str, en: str, hu: str) -> Translatable:
    return {"es": es, "en": en, "hu": hu}


_CITATIONS = (
    make_citation(
        LegalCitationSource.LEY,
        "29-30",
        "Artículos 29 y 30 Ley 27/2014 (LIS) — tipo de gravamen y cuota íntegra del IS.",
        url="https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328",
    ),
    make_citation(
        LegalCitationSource.LEY,
        "125",
        "Artículo 125 Ley 27/2014 (LIS) — líquido a ingresar o devolver; "
        "incremento por pérdida de beneficios fiscales de ejercicios "
        "anteriores y abono de deducciones.",
        url="https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328",
    ),
    make_citation(
        LegalCitationSource.ORDEN_MINISTERIAL,
        "HAC/657/2025",
        "Orden HAC/657/2025 (BOE-A-2025-12818) — aprobación del modelo "
        "200 para ejercicio 2024 y casillas de autoliquidación "
        "rectificativa.",
        url="https://www.boe.es/buscar/doc.php?id=BOE-A-2025-12818",
    ),
)


def _input(cid: str, label: Translatable) -> tuple:
    return (casilla(casilla_id=cid, label=label, computed=False),)


def _computed(cid: str, label: Translatable) -> tuple:
    return (casilla(casilla_id=cid, label=label, computed=True, legal_basis=_CITATIONS),)


_CASILLAS = (
    *_input("00547", _label("Compensacion BINs", "BIN compensation", "Veszteség-beszámítás")),
    *_input("00550", _label("Base imponible antes reserva", "BI pre-reserve", "Adóalap rezerv előtt")),
    *_input("00552", _label("Base imponible", "Taxable base", "Adóalap")),
    *_input("00558", _label("Tipo de gravamen", "Tax rate", "Adókulcs")),
    *_input("00560", _label("Cuota integra previa", "Gross tax (pre)", "Bruttó adó (elő)")),
    *_computed("00562", _label("Cuota integra", "Gross tax amount", "Bruttó adóösszeg")),
    *_input("00582", _label("Cuota integra ajustada positiva", "Adjusted gross tax", "Módosított bruttó adó")),
    *_input("00592", _label("Cuota liquida", "Net tax amount", "Nettó adóösszeg")),
    *_input("00599", _label("Retenciones e ingresos a cuenta", "Withholdings", "Levonások")),
    *_input("00601", _label("Pago fraccionado 1P", "Instalment 1P", "1P részlet")),
    *_input("00603", _label("Pago fraccionado 2P", "Instalment 2P", "2P részlet")),
    *_input("00605", _label("Pago fraccionado 3P", "Instalment 3P", "3P részlet")),
    *_input("00615", _label("Abono de deducciones", "Deductions refund", "Kedvezmény-visszatérítés")),
    *_input(
        "00619",
        _label(
            "Incremento por perdida beneficios fiscales",
            "Increment for lost tax benefits",
            "Növelés elveszett kedvezmények miatt",
        ),
    ),
    *_computed("00611", _label("Cuota diferencial", "Tax differential", "Adókülönbözet")),
    *_computed(
        "00621",
        _label("Liquido a ingresar o devolver", "Net payable or refundable", "Fizetendő vagy visszatérítendő"),
    ),
)


_FORMULAS = (
    formula(
        casilla_id="00562",
        formula_id="modelo_200.2024.cuota_integra",
        # 00562 = 00552 x (00558 / 100). AEAT prints 00558 as whole-percent.
        body=percent_from_whole(ref("00558"), ref("00552")),
    ),
    formula(
        casilla_id="00611",
        formula_id="modelo_200.2024.cuota_diferencial",
        # 00611 = 00592 - 00599 - 00601 - 00603 - 00605.
        body=sub_op(
            sub_op(
                sub_op(
                    sub_op(ref("00592"), ref("00599")),
                    ref("00601"),
                ),
                ref("00603"),
            ),
            ref("00605"),
        ),
    ),
    formula(
        casilla_id="00621",
        formula_id="modelo_200.2024.liquido_a_ingresar",
        # 00621 = 00611 + 00619 - 00615 (art. 125 LIS).
        body=add_op(sub_op(ref("00611"), ref("00615")), ref("00619")),
    ),
)


_PARAMETERS = ParameterTable(entries={})


RULESET: Ruleset = Ruleset(
    ruleset_id="modelo_200.2024",
    modelo=ModeloCode.MODELO_200,
    effective_from=_EFFECTIVE_FROM,
    effective_to=_EFFECTIVE_TO,
    casillas=_CASILLAS,
    formulas=_FORMULAS,
    parameters=_PARAMETERS,
    legal_citations=_CITATIONS,
)
