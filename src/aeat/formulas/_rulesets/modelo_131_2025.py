"""Modelo 131 ruleset covering the full 2025 fiscal year.

Modelo 131 is the quarterly IRPF pago fraccionado for autónomos under
the módulos régimen (estimación objetiva). It mirrors Modelo 130 for
the direct-estimation cousin, but the algebraic chain is different
because modules compute the quarterly instalment from fixed-coefficient
indicators (volumen ventas / volumen ingresos agrícolas) rather than
from a rendimiento neto.

Formula coverage:

- casilla 04 = 2% x casilla 03 (2% sobre volumen ventas en módulos sin
  datos-base — RIRPF art. 110.1.b, Orden EHA/672/2007 instrucciones).
- casilla 06 = 2% x casilla 05 (2% sobre volumen ingresos agrícolas,
  ganaderas, forestales, pesqueras — RIRPF art. 110.1.c).
- casilla 07 = casilla 02 + casilla 04 + casilla 06 (total previo a
  minoraciones).
- casilla 10 = casilla 07 - casilla 08 - casilla 09 (resultado tras
  retenciones e ingresos a cuenta y minoración por rendimientos netos
  del año anterior).
- casilla 13 = casilla 10 - casilla 11 - casilla 12 (resultado tras
  negativos anteriores y deducción vivienda).
- casilla 15 = casilla 13 - casilla 14 (resultado a ingresar tras
  a-deducir de autoliquidaciones anteriores del mismo trimestre, que
  aplica solo en complementarias).

Legal base: Orden EHA/672/2007 (BOE-A-2007-6032); yearly refresh per
BOE Sede AEAT instructions.
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
        LegalCitationSource.REGLAMENTO,
        "110",
        "Artículo 110 RD 439/2007 (Reglamento del IRPF) — pagos "
        "fraccionados por actividades económicas; art. 110.1.b fija "
        "los tipos 4%/3%/2% (escalados por número de asalariados) para "
        "actividades en estimación objetiva (módulos); art. 110.1.c fija "
        "el 2% de los ingresos del trimestre para actividades "
        "agrícolas/ganaderas/forestales/pesqueras.",
        url="https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820",
    ),
    make_citation(
        LegalCitationSource.ORDEN_MINISTERIAL,
        "EHA/672/2007",
        "Orden EHA/672/2007 (BOE-A-2007-6032) — aprobación del modelo 131 y sus instrucciones de cumplimentación.",
        url="https://www.boe.es/buscar/act.php?id=BOE-A-2007-6032",
    ),
)


def _input_casilla(cid: str, label: Translatable) -> tuple:
    return (casilla(casilla_id=cid, label=label, computed=False),)


def _computed_casilla(cid: str, label: Translatable) -> tuple:
    return (casilla(casilla_id=cid, label=label, computed=True, legal_basis=_CITATIONS),)


_CASILLAS = (
    *_input_casilla("01", _label("Suma rendimientos netos modulos", "Modules net income sum", "Modul nettó jövedelem")),
    *_input_casilla(
        "02",
        _label("Pago fraccionado del trimestre", "Quarterly instalment", "Negyedéves részlet"),
    ),
    *_input_casilla("03", _label("Volumen ventas sin datos-base", "Sales volume", "Értékesítési volumen")),
    *_computed_casilla("04", _label("2% s/casilla 03", "2% on casilla 03", "2%-os arány")),
    *_input_casilla(
        "05",
        _label("Volumen ingresos agricolas/ganaderas/forestales", "Agricultural income", "Mezőgazdasági bevétel"),
    ),
    *_computed_casilla("06", _label("2% s/casilla 05", "2% on casilla 05", "2%-os arány")),
    *_computed_casilla(
        "07",
        _label("Total 02+04+06", "Total", "Összesen"),
    ),
    *_input_casilla(
        "08",
        _label("Retenciones e ingresos a cuenta", "Withholdings", "Levonások"),
    ),
    *_input_casilla(
        "09",
        _label("Minoracion rendimientos ano anterior", "Prior-year minoration", "Korábbi év mérséklés"),
    ),
    *_computed_casilla(
        "10",
        _label("Resultado 07-08-09", "Result after credits", "Levonás utáni eredmény"),
    ),
    *_input_casilla(
        "11",
        _label("Resultados negativos autoliquidaciones anteriores", "Prior negatives", "Korábbi negatív eredmény"),
    ),
    *_input_casilla(
        "12",
        _label("Deduccion vivienda habitual", "Primary residence deduction", "Lakásvásárlási kedvezmény"),
    ),
    *_computed_casilla(
        "13",
        _label("Resultado 10-11-12", "Intermediate result", "Köztes eredmény"),
    ),
    *_input_casilla(
        "14",
        _label("A deducir autoliquidaciones anteriores", "Prior-filing offset", "Korábbi bevallási levonás"),
    ),
    *_computed_casilla(
        "15",
        _label("Resultado a ingresar", "Net amount payable", "Fizetendő eredmény"),
    ),
)


_FORMULAS = (
    formula(
        casilla_id="04",
        formula_id="modelo_131.2025.dos_por_ciento_ventas",
        body=percent(param("modulos.dos_por_ciento"), ref("03")),
    ),
    formula(
        casilla_id="06",
        formula_id="modelo_131.2025.dos_por_ciento_agricolas",
        body=percent(param("modulos.dos_por_ciento"), ref("05")),
    ),
    formula(
        casilla_id="07",
        formula_id="modelo_131.2025.total_previo",
        body=add_op(ref("02"), ref("04"), ref("06")),
    ),
    formula(
        casilla_id="10",
        formula_id="modelo_131.2025.resultado_tras_credits",
        body=sub_op(sub_op(ref("07"), ref("08")), ref("09")),
    ),
    formula(
        casilla_id="13",
        formula_id="modelo_131.2025.resultado_intermedio",
        body=sub_op(sub_op(ref("10"), ref("11")), ref("12")),
    ),
    formula(
        casilla_id="15",
        formula_id="modelo_131.2025.resultado_a_ingresar",
        body=sub_op(ref("13"), ref("14")),
    ),
)


_PARAMETERS = ParameterTable(
    entries={
        "modulos.dos_por_ciento": (
            ParameterValue(
                effective_from=_EFFECTIVE_FROM,
                effective_to=_EFFECTIVE_TO,
                value=Decimal("0.02"),
            ),
        ),
    }
)


RULESET: Ruleset = Ruleset(
    ruleset_id="modelo_131.2025",
    modelo=ModeloCode.MODELO_131,
    effective_from=_EFFECTIVE_FROM,
    effective_to=_EFFECTIVE_TO,
    casillas=_CASILLAS,
    formulas=_FORMULAS,
    parameters=_PARAMETERS,
    legal_citations=_CITATIONS,
)
