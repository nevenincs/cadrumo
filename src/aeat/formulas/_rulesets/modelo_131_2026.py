"""Modelo 131 ruleset covering the full 2026 fiscal year.

The repository's current Modelo 131 ruleset covers the liquidación
chain for quarterly IRPF payments under estimación objetiva: 2% on
ventas/ingresos when no datos-base are available, the 2% agricultural
income branch, retenciones/minoraciones, prior negatives, vivienda,
and complementaria offsets. RIRPF art. 110 remains the operative
source for those percentages, while Orden HAC/1425/2025 keeps the
2026 módulos amounts and instructions aligned with Orden HAC/1347/2024.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ...models import LegalCitationSource, ModeloCode
from .._ruleset import ParameterTable, ParameterValue, Ruleset
from ._common import add_op, formula, make_citation, param, percent, ref, sub_op
from .modelo_131_2025 import (
    _CASILLAS as _CASILLAS_2025,
)
from .modelo_131_2025 import (
    _CITATIONS as _CITATIONS_2025,
)

_EFFECTIVE_FROM = date(2026, 1, 1)
_EFFECTIVE_TO = date(2026, 12, 31)

_CITATIONS = (
    *_CITATIONS_2025,
    make_citation(
        LegalCitationSource.ORDEN_MINISTERIAL,
        "HAC/1425/2025",
        "Orden HAC/1425/2025 (BOE-A-2025-25272) — desarrolla para "
        "2026 el método de estimación objetiva del IRPF; mantiene la "
        "cuantía de signos, índices o módulos y las instrucciones de "
        "aplicación.",
        url="https://www.boe.es/diario_boe/txt.php?id=BOE-A-2025-25272",
    ),
)

_FORMULAS = (
    formula(
        casilla_id="04",
        formula_id="modelo_131.2026.dos_por_ciento_ventas",
        body=percent(param("modulos.dos_por_ciento"), ref("03")),
    ),
    formula(
        casilla_id="06",
        formula_id="modelo_131.2026.dos_por_ciento_agricolas",
        body=percent(param("modulos.dos_por_ciento"), ref("05")),
    ),
    formula(
        casilla_id="07",
        formula_id="modelo_131.2026.total_previo",
        body=add_op(ref("02"), ref("04"), ref("06")),
    ),
    formula(
        casilla_id="10",
        formula_id="modelo_131.2026.resultado_tras_credits",
        body=sub_op(sub_op(ref("07"), ref("08")), ref("09")),
    ),
    formula(
        casilla_id="13",
        formula_id="modelo_131.2026.resultado_intermedio",
        body=sub_op(sub_op(ref("10"), ref("11")), ref("12")),
    ),
    formula(
        casilla_id="15",
        formula_id="modelo_131.2026.resultado_a_ingresar",
        body=sub_op(ref("13"), ref("14")),
    ),
)

_CASILLAS = tuple(c.model_copy(update={"legal_basis": _CITATIONS}) if c.computed else c for c in _CASILLAS_2025)

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
    ruleset_id="modelo_131.2026",
    modelo=ModeloCode.MODELO_131,
    effective_from=_EFFECTIVE_FROM,
    effective_to=_EFFECTIVE_TO,
    casillas=_CASILLAS,
    formulas=_FORMULAS,
    parameters=_PARAMETERS,
    legal_citations=_CITATIONS,
)
