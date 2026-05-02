"""Modelo 100 (RENTA / IRPF anual) full-form ruleset — ejercicio 2024.

Aggregates the per-anexo modules under
:mod:`aeat.domain.formulas._rulesets.modelo_100` (B1, B2, C, D normal /
simplificada / módulos, E, F, G, Ñ) into the single
:data:`RULESET` exposed by this module. Mirrors
:mod:`aeat.domain.formulas._rulesets.modelo_100_2025` and
:mod:`aeat.domain.formulas._rulesets.modelo_100_2026` with year-scoped
formula identifiers and an ``effective_from`` / ``effective_to``
window covering the 2024 ejercicio.
"""

from __future__ import annotations

from datetime import date

from ...modelos import ModeloCode
from .._ruleset import ParameterTable, Ruleset
from .modelo_100 import (
    anexo_b1_2024,
    anexo_b2_2024,
    anexo_c_2024,
    anexo_d_modulos_2024,
    anexo_d_normal_2024,
    anexo_d_simplificada_2024,
    anexo_e_2024,
    anexo_f_2024,
    anexo_g_2024,
    anexo_n_2024,
)

_EFFECTIVE_FROM = date(2024, 1, 1)
_EFFECTIVE_TO = date(2024, 12, 31)


_CASILLAS = (
    *anexo_b1_2024.CASILLAS,
    *anexo_b2_2024.CASILLAS,
    *anexo_c_2024.CASILLAS,
    *anexo_d_normal_2024.CASILLAS,
    *anexo_d_simplificada_2024.CASILLAS,
    *anexo_d_modulos_2024.CASILLAS,
    *anexo_e_2024.CASILLAS,
    *anexo_f_2024.CASILLAS,
    *anexo_g_2024.CASILLAS,
    *anexo_n_2024.CASILLAS,
)
_FORMULAS = (
    *anexo_b1_2024.FORMULAS,
    *anexo_b2_2024.FORMULAS,
    *anexo_c_2024.FORMULAS,
    *anexo_d_normal_2024.FORMULAS,
    *anexo_d_simplificada_2024.FORMULAS,
    *anexo_d_modulos_2024.FORMULAS,
    *anexo_e_2024.FORMULAS,
    *anexo_f_2024.FORMULAS,
    *anexo_g_2024.FORMULAS,
    *anexo_n_2024.FORMULAS,
)
_CITATIONS = (
    *anexo_b1_2024.CITATIONS,
    *anexo_b2_2024.CITATIONS,
    *anexo_c_2024.CITATIONS,
    *anexo_d_normal_2024.CITATIONS,
    *anexo_d_simplificada_2024.CITATIONS,
    *anexo_d_modulos_2024.CITATIONS,
    *anexo_e_2024.CITATIONS,
    *anexo_f_2024.CITATIONS,
    *anexo_g_2024.CITATIONS,
    *anexo_n_2024.CITATIONS,
)
_PARAMETERS = ParameterTable(
    entries={
        **anexo_b1_2024.PARAMETERS.entries,
        **anexo_b2_2024.PARAMETERS.entries,
        **anexo_c_2024.PARAMETERS.entries,
        **anexo_d_normal_2024.PARAMETERS.entries,
        **anexo_d_simplificada_2024.PARAMETERS.entries,
        **anexo_d_modulos_2024.PARAMETERS.entries,
        **anexo_e_2024.PARAMETERS.entries,
        **anexo_f_2024.PARAMETERS.entries,
        **anexo_g_2024.PARAMETERS.entries,
        **anexo_n_2024.PARAMETERS.entries,
    },
)


RULESET: Ruleset = Ruleset(
    ruleset_id="modelo_100.2024",
    modelo=ModeloCode.MODELO_100,
    effective_from=_EFFECTIVE_FROM,
    effective_to=_EFFECTIVE_TO,
    casillas=_CASILLAS,
    formulas=_FORMULAS,
    parameters=_PARAMETERS,
    legal_citations=_CITATIONS,
)
"""Aggregated Modelo 100 ruleset for ejercicio 2024.

A :class:`aeat.domain.formulas._ruleset.Ruleset` composed from the
per-anexo modules of :mod:`aeat.domain.formulas._rulesets.modelo_100`,
re-exported as :data:`aeat.domain.formulas._rulesets.MODELO_100_2024`.
"""
