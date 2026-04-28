"""Modelo 100 (RENTA / IRPF anual) full-form ruleset — ejercicio 2025.

Default-variant slot (modelo_100.2025) coexisting with the existing
modelo_100.summary.2025. Composition lands incrementally per the
megaproject implementation waves (research / ADR / plan in .vault/).

As of Wave 8 the aggregator composes:

- Anexo B1 — rendimientos del trabajo (LIRPF arts. 17-20)
- Anexo B2 — capital mobiliario (LIRPF arts. 25-26 + 101.4)
- Anexo C — capital inmobiliario (LIRPF arts. 22-24 + 85)
- Anexo D normal/simplificada/modulos — actividades economicas
- Anexo E — ganancias y perdidas patrimoniales (LIRPF arts. 33-49)
- Anexo F — bases imponibles + reducciones + minimo personal y
  familiar + base liquidable (LIRPF arts. 47-61)

Subsequent waves add G (cuotas + tarifas + Ceuta/Melilla 60 %),
N (deducciones autonomicas 15 CCAAs).
"""

from __future__ import annotations

from datetime import date

from ...models import ModeloCode
from .._ruleset import Ruleset
from .modelo_100 import (
    anexo_b1_2025,
    anexo_b2_2025,
    anexo_c_2025,
    anexo_d_modulos_2025,
    anexo_d_normal_2025,
    anexo_d_simplificada_2025,
    anexo_e_2025,
    anexo_f_2025,
)

_EFFECTIVE_FROM = date(2025, 1, 1)
_EFFECTIVE_TO = date(2025, 12, 31)


_CASILLAS = (
    *anexo_b1_2025.CASILLAS,
    *anexo_b2_2025.CASILLAS,
    *anexo_c_2025.CASILLAS,
    *anexo_d_normal_2025.CASILLAS,
    *anexo_d_simplificada_2025.CASILLAS,
    *anexo_d_modulos_2025.CASILLAS,
    *anexo_e_2025.CASILLAS,
    *anexo_f_2025.CASILLAS,
)
_FORMULAS = (
    *anexo_b1_2025.FORMULAS,
    *anexo_b2_2025.FORMULAS,
    *anexo_c_2025.FORMULAS,
    *anexo_d_normal_2025.FORMULAS,
    *anexo_d_simplificada_2025.FORMULAS,
    *anexo_d_modulos_2025.FORMULAS,
    *anexo_e_2025.FORMULAS,
    *anexo_f_2025.FORMULAS,
)
_CITATIONS = (
    *anexo_b1_2025.CITATIONS,
    *anexo_b2_2025.CITATIONS,
    *anexo_c_2025.CITATIONS,
    *anexo_d_normal_2025.CITATIONS,
    *anexo_d_simplificada_2025.CITATIONS,
    *anexo_d_modulos_2025.CITATIONS,
    *anexo_e_2025.CITATIONS,
    *anexo_f_2025.CITATIONS,
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
