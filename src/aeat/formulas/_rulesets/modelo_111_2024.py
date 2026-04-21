"""Modelo 111 ruleset covering the full 2024 fiscal year.

Structural clone of :mod:`modelo_111_2025`. Ejercicio-2024 retention
rates are identical to 2025 under art. 99-101 LIRPF and art. 100.3.c
/ 105.1 RIRPF — 19% on premios and ganancias-arrendamientos
unchanged since 2016. Kent uses this ruleset for 2024-period
complementaria filings.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ...models import ModeloCode
from .._ruleset import ParameterTable, ParameterValue, Ruleset
from .modelo_111_2025 import (
    _CASILLAS as _CASILLAS_2025,
)
from .modelo_111_2025 import (
    _CITATIONS as _CITATIONS_2025,
)
from .modelo_111_2025 import (
    _FORMULAS as _FORMULAS_2025,
)

_EFFECTIVE_FROM = date(2024, 1, 1)
_EFFECTIVE_TO = date(2024, 12, 31)


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
    ruleset_id="modelo_111.2024",
    modelo=ModeloCode.MODELO_111,
    effective_from=_EFFECTIVE_FROM,
    effective_to=_EFFECTIVE_TO,
    casillas=_CASILLAS_2025,
    formulas=_FORMULAS_2025,
    parameters=_PARAMETERS,
    legal_citations=_CITATIONS_2025,
)
