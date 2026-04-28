"""Modelo 100 (RENTA / IRPF anual) full-form ruleset — ejercicio 2026.

Aggregates per-anexo modules from the ``modelo_100/`` sub-package into
the public ``RULESET`` constant registered at the default variant slot
``modelo_100.2026``.

The 2026 ejercicio inherits the 2025 numerical surface for Anexo B1
(LIRPF arts. 17-20 unchanged 2024 → 2025 → 2026 per BOE consolidated-
text consult at 2026-02-28). The 2026 Orden HAC del Modelo 100 has not
yet been published at retrieval 2026-04-27; any 2026-specific delta
lands as a follow-up issue when the Orden publishes.

Wave 5 (megaproject `#317`) lands Anexo B1 only. Subsequent waves
extend the aggregator with B2, C, D (3 régimenes), E, F, G, Ñ.
"""

from __future__ import annotations

from datetime import date

from ...models import ModeloCode
from .._ruleset import Ruleset
from .modelo_100 import anexo_b1_2026

_EFFECTIVE_FROM = date(2026, 1, 1)
_EFFECTIVE_TO = date(2026, 12, 31)


_CASILLAS = anexo_b1_2026.CASILLAS
_FORMULAS = anexo_b1_2026.FORMULAS
_PARAMETERS = anexo_b1_2026.PARAMETERS
_CITATIONS = anexo_b1_2026.CITATIONS


RULESET: Ruleset = Ruleset(
    ruleset_id="modelo_100.2026",
    modelo=ModeloCode.MODELO_100,
    effective_from=_EFFECTIVE_FROM,
    effective_to=_EFFECTIVE_TO,
    casillas=_CASILLAS,
    formulas=_FORMULAS,
    parameters=_PARAMETERS,
    legal_citations=_CITATIONS,
)
