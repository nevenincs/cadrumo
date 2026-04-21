"""Modelo 115 ruleset covering the full 2024 fiscal year.

Structurally identical to :mod:`modelo_115_2025` — art. 100.3.a RIRPF
has fixed the 19% retention on arrendamientos urbanos since 2016 and
did not change for 2024. This ruleset exists so Kent can self-audit
a 2024 Q1-Q4 complementaria filing without resolving against a 2025
ruleset (which would pass the audit but leak through the wrong
effective-range citation).

Shares the casillas + formulas + citations with the 2025 variant,
tagged with the 2024 effective range and `irpf.arrendamientos_rate`
parameter value.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ...models import ModeloCode
from .._ruleset import ParameterTable, ParameterValue, Ruleset
from .modelo_115_2025 import (
    _CASILLAS as _CASILLAS_2025,
)
from .modelo_115_2025 import (
    _CITATIONS as _CITATIONS_2025,
)
from .modelo_115_2025 import (
    _FORMULAS as _FORMULAS_2025,
)

_EFFECTIVE_FROM = date(2024, 1, 1)
_EFFECTIVE_TO = date(2024, 12, 31)


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


RULESET: Ruleset = Ruleset(
    ruleset_id="modelo_115.2024",
    modelo=ModeloCode.MODELO_115,
    effective_from=_EFFECTIVE_FROM,
    effective_to=_EFFECTIVE_TO,
    casillas=_CASILLAS_2025,
    formulas=_FORMULAS_2025,
    parameters=_PARAMETERS,
    legal_citations=_CITATIONS_2025,
)
