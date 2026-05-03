"""Central registry for legally approved AEAT calculation definitions."""

from __future__ import annotations

from ._registry import (
    CalculationCatalogueTarget,
    CalculationRegistry,
    get_calculation_registry,
)

__all__ = [
    "CalculationCatalogueTarget",
    "CalculationRegistry",
    "get_calculation_registry",
]
