"""Modelo 347 schema manifest for exercise 2026."""

from __future__ import annotations

from ._rules_2024 import MANIFEST_2024

MANIFEST_2026 = MANIFEST_2024.model_copy(update={"ejercicio": 2026})

__all__ = ["MANIFEST_2026"]
