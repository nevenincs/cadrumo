"""Modelo 111 ruleset covering the full 2024 fiscal year.

Structural clone of
:mod:`aeat.domain.formulas._rulesets.modelo_111_2025`. Ejercicio-2024
retention rates are identical to 2025 under LIRPF arts. 99-101
(obligation + rates) and RIRPF arts. 99 (pago-a-cuenta obligation
hook) + 100 (retention-on-rendimientos rates — the 19% on arrendamientos
is art. 100.1, not a sub-lettered subsection). The operator uses this
ruleset for 2024-period complementaria filings of withholdings on rendimientos
del trabajo, actividades económicas, premios, ganancias patrimoniales,
and contraprestaciones en especie.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ...modelos import ModeloCode
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
"""Modelo 111 ruleset for ejercicio 2024.

A :class:`aeat.domain.formulas._ruleset.Ruleset` re-using the casillas,
formulas and citations from
:mod:`aeat.domain.formulas._rulesets.modelo_111_2025` with a 2024
``ParameterTable`` and ``effective_from`` / ``effective_to`` window.
Re-exported as :data:`aeat.domain.formulas._rulesets.MODELO_111_2024`.
"""
