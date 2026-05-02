"""Modelo 180 ruleset covering the full 2026 fiscal year.

Modelo 180 is the annual summary for retenciones e ingresos a cuenta
on rendimientos from urban property leases. The computed summary
surface is unchanged from 2024 and 2025: casilla 03 remains the 19 %
retention on casilla 02 under RIRPF art. 100.1.

The 2026 file keeps a separate effective window and formula identifier
so registry resolution and discrepancy provenance do not leak 2025
metadata into 2026 filings. The casilla and citation tuples are
re-imported from :mod:`aeat.domain.formulas._rulesets.modelo_180_2025`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ...modelos import ModeloCode
from .._ruleset import ParameterTable, ParameterValue, Ruleset
from ._common import (
    formula,
    param,
    percent,
    ref,
)
from .modelo_180_2025 import (
    _CASILLAS as _CASILLAS_2025,
)
from .modelo_180_2025 import (
    _CITATIONS as _CITATIONS_2025,
)

_EFFECTIVE_FROM = date(2026, 1, 1)
_EFFECTIVE_TO = date(2026, 12, 31)


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


_FORMULAS = (
    formula(
        casilla_id="03",
        formula_id="modelo_180.2026.total_retenciones",
        body=percent(param("irpf.arrendamientos_rate"), ref("02")),
    ),
)


RULESET: Ruleset = Ruleset(
    ruleset_id="modelo_180.2026",
    modelo=ModeloCode.MODELO_180,
    effective_from=_EFFECTIVE_FROM,
    effective_to=_EFFECTIVE_TO,
    casillas=_CASILLAS_2025,
    formulas=_FORMULAS,
    parameters=_PARAMETERS,
    legal_citations=_CITATIONS_2025,
)
