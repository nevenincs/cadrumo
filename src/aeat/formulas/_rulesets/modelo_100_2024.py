"""Modelo 100 (RENTA / IRPF anual) full-form ruleset — ejercicio 2024.

Aggregates Anexos B1 + B2 + C into the public ``RULESET`` registered at
the default variant slot ``modelo_100.2024``. Subsequent waves extend
with D / E / F / G / Ñ.
"""

from __future__ import annotations

from datetime import date

from ...models import ModeloCode
from .._ruleset import Ruleset
from .modelo_100 import anexo_b1_2024, anexo_b2_2024, anexo_c_2024

_EFFECTIVE_FROM = date(2024, 1, 1)
_EFFECTIVE_TO = date(2024, 12, 31)


_CASILLAS = (
    *anexo_b1_2024.CASILLAS,
    *anexo_b2_2024.CASILLAS,
    *anexo_c_2024.CASILLAS,
)
_FORMULAS = (
    *anexo_b1_2024.FORMULAS,
    *anexo_b2_2024.FORMULAS,
    *anexo_c_2024.FORMULAS,
)
_CITATIONS = (
    *anexo_b1_2024.CITATIONS,
    *anexo_b2_2024.CITATIONS,
    *anexo_c_2024.CITATIONS,
)


RULESET: Ruleset = Ruleset(
    ruleset_id="modelo_100.2024",
    modelo=ModeloCode.MODELO_100,
    effective_from=_EFFECTIVE_FROM,
    effective_to=_EFFECTIVE_TO,
    casillas=_CASILLAS,
    formulas=_FORMULAS,
    parameters=anexo_b1_2024.PARAMETERS,
    legal_citations=_CITATIONS,
)
