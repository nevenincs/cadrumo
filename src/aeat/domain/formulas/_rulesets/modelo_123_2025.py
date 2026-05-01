"""Modelo 123 ruleset covering the full 2025 fiscal year.

Modelo 123 is the quarterly (monthly for grandes empresas) withholdings
form for rendimientos del capital mobiliario — dividends, interest on
deposits/loans/securities — under IRPF / IS / IRNR.

The liquidación block is fully algebraic. Every row is a total (dividends
+ otras rentas). Formula coverage:

- casilla 03 = 01 + 02 (total perceptores).
- casilla 06 = 04 + 05 (total base retenciones).
- casilla 09 = 07 + 08 (total retenciones).
- casilla 11 = 09 - 10 (resultado a ingresar — total retenciones menos
  resultado declaración anterior en complementaria).

For Kent's IRPF autónomo path, LIRPF art. 101.4 and RIRPF art. 90
anchor the ordinary capital-income retention rate at 19%. The Modelo
123 form also covers IS and IRNR rents, so the per-row withholding
amounts remain user-supplied in this cross-tax ruleset; Kent verifies
the declared aggregates and complementaria offset.
"""

from __future__ import annotations

from datetime import date

from ....core.i18n import Translatable
from ...modelos import LegalCitationSource, ModeloCode
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
        "25",
        "Artículo 25 Ley 35/2006 (IRPF) — define los rendimientos "
        "íntegros del capital mobiliario, including dividends and "
        "interest, that can feed Modelo 123 withholding declarations.",
        url="https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764&p=20260228&tn=1",
    ),
    make_citation(
        LegalCitationSource.LEY,
        "101.4",
        "Artículo 101.4 Ley 35/2006 (IRPF) — fixes the ordinary "
        "retención e ingreso a cuenta rate for rendimientos del "
        "capital mobiliario at 19%, subject to statutory exceptions.",
        url="https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764&p=20260228&tn=1",
    ),
    make_citation(
        LegalCitationSource.REGLAMENTO,
        "90",
        "Artículo 90 RD 439/2007 (Reglamento del IRPF) — applies "
        "the 19% rate to the withholding base for rendimientos del "
        "capital mobiliario.",
        url="https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820&p=20260228&tn=1",
    ),
)


_CASILLAS = (
    casilla(
        casilla_id="01",
        label=_label("Perceptores dividendos", "Dividend recipients", "Osztalék-kedvezményezettek"),
        computed=False,
    ),
    casilla(
        casilla_id="02",
        label=_label("Perceptores otras rentas", "Other recipients", "Egyéb kedvezményezettek"),
        computed=False,
    ),
    casilla(
        casilla_id="03",
        label=_label("Total perceptores", "Total recipients", "Összes kedvezményezett"),
        computed=True,
        legal_basis=_CITATIONS,
    ),
    casilla(
        casilla_id="04",
        label=_label("Base retenciones dividendos", "Dividend withholding base", "Osztalék levonási alap"),
        computed=False,
    ),
    casilla(
        casilla_id="05",
        label=_label("Base retenciones otras rentas", "Other withholding base", "Egyéb levonási alap"),
        computed=False,
    ),
    casilla(
        casilla_id="06",
        label=_label("Base total retenciones", "Total withholding base", "Teljes levonási alap"),
        computed=True,
        legal_basis=_CITATIONS,
    ),
    casilla(
        casilla_id="07",
        label=_label("Retenciones dividendos", "Dividend withholdings", "Osztalék-levonás"),
        computed=False,
    ),
    casilla(
        casilla_id="08",
        label=_label("Retenciones otras rentas", "Other withholdings", "Egyéb levonás"),
        computed=False,
    ),
    casilla(
        casilla_id="09",
        label=_label("Total retenciones", "Total withholdings", "Teljes levonás"),
        computed=True,
        legal_basis=_CITATIONS,
    ),
    casilla(
        casilla_id="10",
        label=_label(
            "Resultado declaracion anterior (complementaria)",
            "Prior filing result (complementaria)",
            "Korábbi bevallás eredménye",
        ),
        computed=False,
    ),
    casilla(
        casilla_id="11",
        label=_label("Resultado a ingresar", "Net amount payable", "Fizetendő eredmény"),
        computed=True,
        legal_basis=_CITATIONS,
    ),
)


_FORMULAS = (
    formula(
        casilla_id="03",
        formula_id="modelo_123.2025.total_perceptores",
        body=add_op(ref("01"), ref("02")),
    ),
    formula(
        casilla_id="06",
        formula_id="modelo_123.2025.base_total",
        body=add_op(ref("04"), ref("05")),
    ),
    formula(
        casilla_id="09",
        formula_id="modelo_123.2025.total_retenciones",
        body=add_op(ref("07"), ref("08")),
    ),
    formula(
        casilla_id="11",
        formula_id="modelo_123.2025.resultado_a_ingresar",
        body=sub_op(ref("09"), ref("10")),
    ),
)


_PARAMETERS = ParameterTable(entries={})


RULESET: Ruleset = Ruleset(
    ruleset_id="modelo_123.2025",
    modelo=ModeloCode.MODELO_123,
    effective_from=_EFFECTIVE_FROM,
    effective_to=_EFFECTIVE_TO,
    casillas=_CASILLAS,
    formulas=_FORMULAS,
    parameters=_PARAMETERS,
    legal_citations=_CITATIONS,
)
