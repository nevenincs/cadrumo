"""Modelo 100 (RENTA / IRPF anual) full-form ruleset — ejercicio 2025.

Aggregates per-anexo modules from the ``modelo_100/`` sub-package into
the public ``RULESET`` constant registered at the default variant slot
``modelo_100.2025``.

Composition lands incrementally across the megaproject's
implementation waves. As of Wave 7:

- Anexo B1 — rendimientos del trabajo (LIRPF arts. 17-20)
- Anexo B2 — capital mobiliario (LIRPF arts. 25-26 + 101.4)
- Anexo C — capital inmobiliario (LIRPF arts. 22-24 + 85)
- Anexo D normal — actividades económicas E.D. normal (LIRPF arts.
  27-28 + 32, LIS arts. 12-14 + 17)
- Anexo D simplificada — actividades económicas E.D. simplificada
  (LIRPF arts. 28 + 32, RIRPF art. 30 5 % / 2.000 € cap)
- Anexo D módulos — actividades económicas estimación objetiva
  (LIRPF art. 31 + RIRPF art. 32; per-actividad tabla per Orden HAC
  anual)

Subsequent waves extend with E (ganancias y pérdidas), F (bases
imponibles + reducciones + mínimos), G (cuotas + tarifas + deducciones
estatales + Ceuta/Melilla 60 %), Ñ (deducciones autonómicas 15 CCAAs).
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
)
_FORMULAS = (
    *anexo_b1_2025.FORMULAS,
    *anexo_b2_2025.FORMULAS,
    *anexo_c_2025.FORMULAS,
    *anexo_d_normal_2025.FORMULAS,
    *anexo_d_simplificada_2025.FORMULAS,
    *anexo_d_modulos_2025.FORMULAS,
)
_CITATIONS = (
    *anexo_b1_2025.CITATIONS,
    *anexo_b2_2025.CITATIONS,
    *anexo_c_2025.CITATIONS,
    *anexo_d_normal_2025.CITATIONS,
    *anexo_d_simplificada_2025.CITATIONS,
    *anexo_d_modulos_2025.CITATIONS,
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
