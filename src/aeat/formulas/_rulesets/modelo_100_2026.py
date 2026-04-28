"""Modelo 100 (RENTA / IRPF anual) full-form ruleset — ejercicio 2026."""

from __future__ import annotations

from datetime import date

from ...models import ModeloCode
from .._ruleset import Ruleset
from .modelo_100 import (
    anexo_b1_2026,
    anexo_b2_2026,
    anexo_c_2026,
    anexo_d_modulos_2026,
    anexo_d_normal_2026,
    anexo_d_simplificada_2026,
    anexo_e_2026,
    anexo_f_2026,
)

_EFFECTIVE_FROM = date(2026, 1, 1)
_EFFECTIVE_TO = date(2026, 12, 31)


_CASILLAS = (
    *anexo_b1_2026.CASILLAS,
    *anexo_b2_2026.CASILLAS,
    *anexo_c_2026.CASILLAS,
    *anexo_d_normal_2026.CASILLAS,
    *anexo_d_simplificada_2026.CASILLAS,
    *anexo_d_modulos_2026.CASILLAS,
    *anexo_e_2026.CASILLAS,
    *anexo_f_2026.CASILLAS,
)
_FORMULAS = (
    *anexo_b1_2026.FORMULAS,
    *anexo_b2_2026.FORMULAS,
    *anexo_c_2026.FORMULAS,
    *anexo_d_normal_2026.FORMULAS,
    *anexo_d_simplificada_2026.FORMULAS,
    *anexo_d_modulos_2026.FORMULAS,
    *anexo_e_2026.FORMULAS,
    *anexo_f_2026.FORMULAS,
)
_CITATIONS = (
    *anexo_b1_2026.CITATIONS,
    *anexo_b2_2026.CITATIONS,
    *anexo_c_2026.CITATIONS,
    *anexo_d_normal_2026.CITATIONS,
    *anexo_d_simplificada_2026.CITATIONS,
    *anexo_d_modulos_2026.CITATIONS,
    *anexo_e_2026.CITATIONS,
    *anexo_f_2026.CITATIONS,
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
