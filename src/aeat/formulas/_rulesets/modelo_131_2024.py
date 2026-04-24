"""Modelo 131 ruleset covering the full 2024 fiscal year.

Structural clone of :mod:`modelo_131_2025`. 2% rate on volumen ventas
and volumen ingresos agrícolas unchanged from 2024 to 2025 under
RIRPF art. 110.1.b (módulos, estimación objetiva) and art. 110.1.c
(actividades agrícolas/ganaderas/forestales/pesqueras). Kent uses
this for 2024-period complementaria filings under módulos.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ...models import ModeloCode
from .._ruleset import ParameterTable, ParameterValue, Ruleset
from .modelo_131_2025 import (
    _CASILLAS as _CASILLAS_2025,
)
from .modelo_131_2025 import (
    _CITATIONS as _CITATIONS_2025,
)
from .modelo_131_2025 import (
    _FORMULAS as _FORMULAS_2025,
)

_EFFECTIVE_FROM = date(2024, 1, 1)
_EFFECTIVE_TO = date(2024, 12, 31)


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
    casillas=_CASILLAS_2025,
    formulas=_FORMULAS_2025,
    parameters=_PARAMETERS,
    legal_citations=_CITATIONS_2025,
)
