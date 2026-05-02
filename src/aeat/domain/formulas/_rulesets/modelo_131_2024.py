"""Modelo 131 ruleset covering the full 2024 fiscal year.

Modelo 131 keeps the same liquidación template across the 2024 and 2025
annual periods. The 2 % rate on volumen ventas and volumen ingresos
agrícolas is anchored in RIRPF art. 110.1.b (módulos, estimación
objetiva) and art. 110.1.c (actividades agrícolas/ganaderas/forestales/
pesqueras). The 2024 ruleset supports complementaria filings under
módulos for that fiscal year.

The casilla layout is re-imported from
:mod:`aeat.domain.formulas._rulesets.modelo_131_2025` and rewrapped with
2024-scoped legal citations (Orden HFP/1359/2023 for that year's
estimación objetiva / IVA simplificado refresh).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ...modelos import LegalCitationSource, ModeloCode
from .._ruleset import ParameterTable, ParameterValue, Ruleset
from ._common import add_op, formula, make_citation, param, percent, ref, sub_op
from .modelo_131_2025 import (
    _CASILLAS as _BASE_CASILLAS,
)

_EFFECTIVE_FROM = date(2024, 1, 1)
_EFFECTIVE_TO = date(2024, 12, 31)

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
    make_citation(
        LegalCitationSource.ORDEN_MINISTERIAL,
        "HFP/1359/2023",
        "Orden HFP/1359/2023 (BOE-A-2023-25882) — desarrolla para "
        "2024 el método de estimación objetiva del IRPF y el régimen "
        "especial simplificado del IVA.",
        url="https://www.boe.es/boe/dias/2023/12/21/pdfs/BOE-A-2023-25882.pdf",
    ),
)

_CASILLAS = tuple(c.model_copy(update={"legal_basis": _CITATIONS}) if c.computed else c for c in _BASE_CASILLAS)

_FORMULAS = (
    formula(
        casilla_id="04",
        formula_id="modelo_131.2024.dos_por_ciento_ventas",
        body=percent(param("modulos.dos_por_ciento"), ref("03")),
    ),
    formula(
        casilla_id="06",
        formula_id="modelo_131.2024.dos_por_ciento_agricolas",
        body=percent(param("modulos.dos_por_ciento"), ref("05")),
    ),
    formula(
        casilla_id="07",
        formula_id="modelo_131.2024.total_previo",
        body=add_op(ref("02"), ref("04"), ref("06")),
    ),
    formula(
        casilla_id="10",
        formula_id="modelo_131.2024.resultado_tras_credits",
        body=sub_op(sub_op(ref("07"), ref("08")), ref("09")),
    ),
    formula(
        casilla_id="13",
        formula_id="modelo_131.2024.resultado_intermedio",
        body=sub_op(sub_op(ref("10"), ref("11")), ref("12")),
    ),
    formula(
        casilla_id="15",
        formula_id="modelo_131.2024.resultado_a_ingresar",
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
    ruleset_id="modelo_131.2024",
    modelo=ModeloCode.MODELO_131,
    effective_from=_EFFECTIVE_FROM,
    effective_to=_EFFECTIVE_TO,
    casillas=_CASILLAS,
    formulas=_FORMULAS,
    parameters=_PARAMETERS,
    legal_citations=_CITATIONS,
)
