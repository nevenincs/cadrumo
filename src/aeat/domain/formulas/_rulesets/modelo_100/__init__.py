"""Modelo 100 (RENTA / IRPF anual) full-form ruleset sub-package.

Hosts the per-anexo per-año modules that the parent-level aggregators
(``modelo_100_<año>.py``) compose into the public ``RULESET`` constants.

The layout splits cross-cutting helpers from the per-anexo per-año
modules:

- :mod:`._common` exposes the multilingual label helper and BOE URL
  constants reused across anexos.
- :mod:`._ccaa` defines the closed :class:`._ccaa.CCAA` enum and
  per-CCAA tarifa autonómica brackets for all 15 ordinary CCAAs (13
  stable plus Asturias and Canarias year-dependent under Ley 3/2025 and
  Ley 5/2024 respectively); País Vasco and Navarra are excluded as
  foral regimes.
- :mod:`._amortization` provides :class:`._amortization.AmortizationCategory`
  and the closed :class:`._amortization.AssetClass` enum encoding the
  LIS art. 12.1.a) lineal table.
- :mod:`._inventario` provides :class:`._inventario.InventoryRecord`
  and the closed :class:`._inventario.ValuationMethod` enum (FIFO,
  PMP, coste medio; LIFO forbidden by construction per LIS art. 17).
- ``anexo_<X>_<año>.py`` modules export the per-year ``CASILLAS``,
  ``FORMULAS`` and ``PARAMETERS`` tuples.
"""

from __future__ import annotations

from ._amortization import (
    LIS_ART_12_LINEAL_TABLE,
    AmortizationCategory,
    AssetClass,
)
from ._ccaa import CCAA
from ._inventario import InventoryRecord, ValuationMethod

__all__ = [
    "CCAA",
    "LIS_ART_12_LINEAL_TABLE",
    "AmortizationCategory",
    "AssetClass",
    "InventoryRecord",
    "ValuationMethod",
]
