"""Domain-level error types for AEAT business logic."""

from __future__ import annotations

from ..core.errors import AeatError


class DomainError(AeatError, ValueError):
    """Base error for domain logic and record validation."""


class DomainValidationError(DomainError):
    """Raised when domain identifiers or models are invalid."""
