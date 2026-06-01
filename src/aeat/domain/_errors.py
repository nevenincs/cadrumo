"""Domain-level error types for AEAT business logic."""

from __future__ import annotations

from ..core.errors import AeatError


class DomainValidationError(AeatError, ValueError):
    """Raised when domain identifiers or models are invalid."""
