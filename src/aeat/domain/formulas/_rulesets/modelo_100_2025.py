"""Modelo 100 (RENTA / IRPF anual) full-form ruleset — ejercicio 2025.

Default-variant slot (`modelo_100.2025`) coexisting with the existing
`modelo_100.summary.2025`. The aggregator composes the per-anexo
modules from the `modelo_100/` sub-package into one `Ruleset` covering:

- Anexo B1 — rendimientos del trabajo (LIRPF arts. 17-20)
- Anexo B2 — capital mobiliario (LIRPF arts. 25-26 + 101.4)
- Anexo C — capital inmobiliario (LIRPF arts. 22-24 + 85)
- Anexo D — actividades económicas en estimación directa normal /
  estimación directa simplificada / estimación objetiva (módulos)
- Anexo E — ganancias y pérdidas patrimoniales (LIRPF arts. 33-49)
- Anexo F — bases imponibles + reducciones de la base imponible +
  mínimo personal y familiar + base liquidable (LIRPF arts. 47-61, 84)
- Anexo G — cuotas íntegras / líquidas + tarifa estatal general +
  tarifa estatal del ahorro + Ceuta/Melilla 60 % (LIRPF arts. 63-79)
- Anexo Ñ — deducciones autonómicas (LIRPF art. 46 bis + 73-77)

The 2024 / 2025 / 2026 rulesets share casillas + citations via re-
import from the 2025 canonical anexo modules; only year-scoped
formula IDs and effective dates are per-year specific.
"""

from __future__ import annotations

from datetime import date

from ...modelos import ModeloCode
from .._ruleset import ParameterTable, Ruleset
from .modelo_100 import (
    anexo_b1_2025,
    anexo_b2_2025,
    anexo_c_2025,
    anexo_d_modulos_2025,
    anexo_d_normal_2025,
    anexo_d_simplificada_2025,
    anexo_e_2025,
    anexo_f_2025,
    anexo_g_2025,
    anexo_n_2025,
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
    *anexo_g_2025.CASILLAS,
    *anexo_n_2025.CASILLAS,
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
    *anexo_g_2025.FORMULAS,
    *anexo_n_2025.FORMULAS,
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
    *anexo_g_2025.CITATIONS,
    *anexo_n_2025.CITATIONS,
)
_PARAMETERS = ParameterTable(
    entries={
        **anexo_b1_2025.PARAMETERS.entries,
        **anexo_b2_2025.PARAMETERS.entries,
        **anexo_c_2025.PARAMETERS.entries,
        **anexo_d_normal_2025.PARAMETERS.entries,
        **anexo_d_simplificada_2025.PARAMETERS.entries,
        **anexo_d_modulos_2025.PARAMETERS.entries,
        **anexo_e_2025.PARAMETERS.entries,
        **anexo_f_2025.PARAMETERS.entries,
        **anexo_g_2025.PARAMETERS.entries,
        **anexo_n_2025.PARAMETERS.entries,
    },
)


RULESET: Ruleset = Ruleset(
    ruleset_id="modelo_100.2025",
    modelo=ModeloCode.MODELO_100,
    effective_from=_EFFECTIVE_FROM,
    effective_to=_EFFECTIVE_TO,
    casillas=_CASILLAS,
    formulas=_FORMULAS,
    parameters=_PARAMETERS,
    legal_citations=_CITATIONS,
)
