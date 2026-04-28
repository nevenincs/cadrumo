"""Modelo 100 (RENTA / IRPF anual) full-form ruleset — ejercicio 2026.

Aggregates Anexos B1 + B2 + C into the public ``RULESET`` registered at
the default variant slot ``modelo_100.2026``. The 2026 ejercicio inherits
the 2025 numerical surface across these anexos (LIRPF arts. 17-26 + 85
unchanged for 2026 at BOE consolidated text consult 2026-02-28). Any
2026-specific delta lands as a follow-up issue when the 2026 Orden
HAC publishes (precedent feb-mar 2027). Subsequent waves extend with
D / E / F / G / Ñ.
"""

from __future__ import annotations

from datetime import date

from ...models import ModeloCode
from .._ruleset import Ruleset
from .modelo_100 import anexo_b1_2026, anexo_b2_2026, anexo_c_2026

_EFFECTIVE_FROM = date(2026, 1, 1)
_EFFECTIVE_TO = date(2026, 12, 31)


_CASILLAS = (
    *anexo_b1_2026.CASILLAS,
    *anexo_b2_2026.CASILLAS,
    *anexo_c_2026.CASILLAS,
)
_FORMULAS = (
    *anexo_b1_2026.FORMULAS,
    *anexo_b2_2026.FORMULAS,
    *anexo_c_2026.FORMULAS,
)
_CITATIONS = (
    *anexo_b1_2026.CITATIONS,
    *anexo_b2_2026.CITATIONS,
    *anexo_c_2026.CITATIONS,
)


RULESET: Ruleset = Ruleset(
    ruleset_id="modelo_100.2026",
    modelo=ModeloCode.MODELO_100,
    effective_from=_EFFECTIVE_FROM,
    effective_to=_EFFECTIVE_TO,
    casillas=_CASILLAS,
    formulas=_FORMULAS,
    parameters=anexo_b1_2026.PARAMETERS,
    legal_citations=_CITATIONS,
)
