"""Modelo 180 ruleset covering the full 2024 fiscal year.

Structural clone of :mod:`aeat.domain.formulas._rulesets.modelo_180_2025` —
the 19 % retention on arrendamientos has been unchanged since 2016. The
2024 ruleset exists so the engine can self-audit a 2024 annual 180
summary (or a sustitutiva filed in 2025 for ejercicio 2024) without
leaking through the 2025 effective range.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ...modelos import ModeloCode
from .._ruleset import ParameterTable, ParameterValue, Ruleset
from .modelo_180_2025 import (
    _CASILLAS as _CASILLAS_2025,
)
from .modelo_180_2025 import (
    _CITATIONS as _CITATIONS_2025,
)
from .modelo_180_2025 import (
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
    ruleset_id="modelo_180.2024",
    modelo=ModeloCode.MODELO_180,
    effective_from=_EFFECTIVE_FROM,
    effective_to=_EFFECTIVE_TO,
    casillas=_CASILLAS_2025,
    formulas=tuple(
        f.model_copy(update={"formula_id": f.formula_id.replace(".2025.", ".2024.")}) for f in _FORMULAS_2025
    ),
    parameters=_PARAMETERS,
    legal_citations=_CITATIONS_2025,
)
