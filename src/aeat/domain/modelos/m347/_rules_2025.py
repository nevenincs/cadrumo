"""Modelo 347 schema manifest for exercise 2025."""

from __future__ import annotations

from ._rules_2024 import MANIFEST_2024

MANIFEST_2025 = MANIFEST_2024.model_copy(update={"ejercicio": 2025})

__all__ = ["MANIFEST_2025"]
