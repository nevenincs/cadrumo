"""Modelo 123 ruleset covering the full 2024 fiscal year.

Structural clone of
:mod:`aeat.domain.formulas._rulesets.modelo_123_2025`. Modelo 123 is a
pure aggregation ruleset — no parameter table — so the 2024 variant
only narrows the effective range. The operator uses this for
2024-period complementaria filings of capital-mobiliario retenciones.
"""

from __future__ import annotations

from datetime import date

from ...modelos import ModeloCode
from .._ruleset import ParameterTable, Ruleset
from .modelo_123_2025 import (
    _CASILLAS as _CASILLAS_2025,
)
from .modelo_123_2025 import (
    _CITATIONS as _CITATIONS_2025,
)
from .modelo_123_2025 import (
    _FORMULAS as _FORMULAS_2025,
)

_EFFECTIVE_FROM = date(2024, 1, 1)
_EFFECTIVE_TO = date(2024, 12, 31)


_PARAMETERS = ParameterTable(entries={})


RULESET: Ruleset = Ruleset(
    ruleset_id="modelo_123.2024",
    modelo=ModeloCode.MODELO_123,
    effective_from=_EFFECTIVE_FROM,
    effective_to=_EFFECTIVE_TO,
    casillas=_CASILLAS_2025,
    formulas=_FORMULAS_2025,
    parameters=_PARAMETERS,
    legal_citations=_CITATIONS_2025,
)
"""Modelo 123 ruleset for ejercicio 2024.

A :class:`aeat.domain.formulas._ruleset.Ruleset` re-using the casillas,
formulas and citations from
:mod:`aeat.domain.formulas._rulesets.modelo_123_2025` with an empty
``ParameterTable`` and the 2024 ``effective_from`` / ``effective_to``
window. Re-exported as
:data:`aeat.domain.formulas._rulesets.MODELO_123_2024`.
"""
