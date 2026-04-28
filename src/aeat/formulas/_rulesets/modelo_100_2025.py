"""Modelo 100 (RENTA / IRPF anual) full-form ruleset — ejercicio 2025.

Aggregates per-anexo modules from the ``modelo_100/`` sub-package into
the public ``RULESET`` constant registered at the default variant slot
``modelo_100.2025``. Coexists with ``modelo_100.summary.2025`` (variant
``summary``) — the existing summary ruleset's docstring explicitly
reserves the default slot for this full-form expansion.

Composition: Anexos B1 (rendimientos del trabajo) + B2 (rendimientos
del capital mobiliario) + C (rendimientos del capital inmobiliario)
land in this initial wave set. Subsequent waves extend the aggregator
with D (3 régimenes), E, F, G, Ñ.
"""

from __future__ import annotations

from datetime import date

from ...models import ModeloCode
from .._ruleset import Ruleset
from .modelo_100 import anexo_b1_2025, anexo_b2_2025, anexo_c_2025

_EFFECTIVE_FROM = date(2025, 1, 1)
_EFFECTIVE_TO = date(2025, 12, 31)


_CASILLAS = (
    *anexo_b1_2025.CASILLAS,
    *anexo_b2_2025.CASILLAS,
    *anexo_c_2025.CASILLAS,
)
_FORMULAS = (
    *anexo_b1_2025.FORMULAS,
    *anexo_b2_2025.FORMULAS,
    *anexo_c_2025.FORMULAS,
)
_CITATIONS = (
    *anexo_b1_2025.CITATIONS,
    *anexo_b2_2025.CITATIONS,
    *anexo_c_2025.CITATIONS,
)


RULESET: Ruleset = Ruleset(
    ruleset_id="modelo_100.2025",
    modelo=ModeloCode.MODELO_100,
    effective_from=_EFFECTIVE_FROM,
    effective_to=_EFFECTIVE_TO,
    casillas=_CASILLAS,
    formulas=_FORMULAS,
    parameters=anexo_b1_2025.PARAMETERS,
    legal_citations=_CITATIONS,
)
