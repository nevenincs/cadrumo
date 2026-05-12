"""Domain errors for AEAT modelo codes."""

from __future__ import annotations

from ...core.errors import AeatError


class ModeloError(AeatError):
    """Base error for the modelos subpackage."""


class ModeloValidationError(ModeloError, ValueError):
    """Raised when a modelo code violates shape invariants."""


__all__ = ["ModeloError", "ModeloValidationError"]
