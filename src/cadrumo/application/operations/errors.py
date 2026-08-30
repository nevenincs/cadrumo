"""Canonical application errors for supervised operations."""

from __future__ import annotations

from ...core.errors.hierarchy import CoreValidationError


class OperationDeclarationError(CoreValidationError):
    """An executor attempted behavior outside its registered declaration."""


__all__ = ["OperationDeclarationError"]
