"""Concrete rulesets shipped with :mod:`aeat.formulas`."""

from __future__ import annotations

from .._ruleset import Ruleset
from .modelo_130_2024 import RULESET as MODELO_130_2024
from .modelo_130_2025 import RULESET as MODELO_130_2025
from .modelo_303_2024 import RULESET as MODELO_303_2024
from .modelo_303_2025 import RULESET as MODELO_303_2025

ALL_RULESETS: tuple[Ruleset, ...] = (
    MODELO_130_2024,
    MODELO_130_2025,
    MODELO_303_2024,
    MODELO_303_2025,
)

__all__ = [
    "ALL_RULESETS",
    "MODELO_130_2024",
    "MODELO_130_2025",
    "MODELO_303_2024",
    "MODELO_303_2025",
]
