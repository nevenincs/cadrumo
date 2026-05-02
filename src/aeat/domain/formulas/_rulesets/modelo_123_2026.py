"""Modelo 123 ruleset covering the full 2026 fiscal year.

Structurally identical to :mod:`aeat.domain.formulas._rulesets.modelo_123_2024`
and :mod:`aeat.domain.formulas._rulesets.modelo_123_2025`. LIRPF art. 101.4 and
RIRPF art. 90 continue to anchor the ordinary IRPF capital-income retention
rate at 19% in the BOE consolidated text current for 2026, but Modelo 123 also
covers IS and IRNR rents. This ruleset therefore preserves the existing
cross-tax verification boundary: per-row withholding amounts are declared
inputs, while totals and the complementaria offset are recomputed by the engine.

The exported :data:`RULESET` reuses the casilla, formula, and citation tuples
from the 2025 sibling and binds them to the 2026 effective range so registry
resolution does not leak metadata across fiscal years.
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

_EFFECTIVE_FROM = date(2026, 1, 1)
_EFFECTIVE_TO = date(2026, 12, 31)


_PARAMETERS = ParameterTable(entries={})


RULESET: Ruleset = Ruleset(
    ruleset_id="modelo_123.2026",
    modelo=ModeloCode.MODELO_123,
    effective_from=_EFFECTIVE_FROM,
    effective_to=_EFFECTIVE_TO,
    casillas=_CASILLAS_2025,
    formulas=_FORMULAS_2025,
    parameters=_PARAMETERS,
    legal_citations=_CITATIONS_2025,
)
