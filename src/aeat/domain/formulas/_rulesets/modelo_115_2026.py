"""Modelo 115 ruleset covering the full 2026 fiscal year.

Structurally identical to
:mod:`aeat.domain.formulas._rulesets.modelo_115_2024` and
:mod:`aeat.domain.formulas._rulesets.modelo_115_2025`: RIRPF art. 100
(RD 439/2007) was not amended for 2025 or 2026. The BOE consolidated
text carries the verbatim statute:

    Artículo 100. Importe de las retenciones sobre arrendamientos
    y subarrendamientos de inmuebles.

    La retención a practicar sobre los rendimientos procedentes
    del arrendamiento o subarrendamiento de inmuebles urbanos,
    cualquiera que sea su calificación, será el resultado de
    aplicar el porcentaje del 19 por ciento sobre todos los
    conceptos que se satisfagan al arrendador, excluido el
    Impuesto sobre el Valor Añadido.

The 19 % retention rate has been fixed since 2016. RD 253/2025 (the
only 2025 modification of RIRPF) touched art. 69 (information
obligations), not art. 100.

Re-imports ``_CASILLAS``, ``_FORMULAS``, and ``_CITATIONS`` from the
2025 module — same convention as the 2024 ruleset — and declares only
its own ``ParameterTable`` bound to the 2026 effective range.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ...modelos import ModeloCode
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


RULESET: Ruleset = Ruleset(
    ruleset_id="modelo_115.2026",
    modelo=ModeloCode.MODELO_115,
    effective_from=_EFFECTIVE_FROM,
    effective_to=_EFFECTIVE_TO,
    casillas=_CASILLAS_2025,
    formulas=_FORMULAS_2025,
    parameters=_PARAMETERS,
    legal_citations=_CITATIONS_2025,
)
"""Modelo 115 ruleset for ejercicio 2026.

A :class:`aeat.domain.formulas._ruleset.Ruleset` re-using the casillas,
formulas and citations from
:mod:`aeat.domain.formulas._rulesets.modelo_115_2025` with a 2026
``ParameterTable`` and ``effective_from`` / ``effective_to`` window.
Re-exported as :data:`aeat.domain.formulas._rulesets.MODELO_115_2026`.
"""
