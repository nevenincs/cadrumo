"""Modelo 100 (RENTA / IRPF anual) full-form sub-package.

This sub-package hosts the per-anexo per-año modules that the parent-
level aggregators (``modelo_100_<año>.py``) compose into the public
``RULESET`` constants.

Layout overview:

- ``_common.py`` — shared label helper, BOE URL constants, citation
  helpers reused across anexos.
- ``_ccaa.py`` — closed ``CCAA`` enum + per-CCAA tarifa autonómica
  brackets for all 15 ordinary CCAAs (13 stable + Asturias / Canarias
  year-dependent post Ley 3/2025 + Ley 5/2024 respectively); País
  Vasco / Navarra excluded as foral regimes.
- ``_amortization.py`` — Pydantic ``AmortizationCategory`` + closed
  ``AssetClass`` enum encoding the LIS art. 12.1.a) lineal table.
- ``_inventario.py`` — Pydantic ``InventoryRecord`` + closed
  ``ValuationMethod`` enum (FIFO / PMP / coste medio; LIFO forbidden
  by construction per LIS art. 17).
- ``anexo_<X>_<año>.py`` — per-anexo per-año modules exporting
  ``CASILLAS``, ``FORMULAS``, ``PARAMETERS`` tuples.

The ADR for this feature documents the rationale for the sub-package
pattern (first sub-package within ``aeat.formulas._rulesets`` — M100-
specific, justified by the 5-10x scale relative to sibling Tier-L
modelos).
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
