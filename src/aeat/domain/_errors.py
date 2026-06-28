"""Domain-level validation errors for pure domain value objects.

Defines :class:`DomainValidationError`, the ``AeatError`` subclass that also
behaves as :exc:`ValueError` so Pydantic validators can surface invalid domain
identifiers and models as validation failures.
"""

from __future__ import annotations

from ..core.errors import AeatError


class DomainValidationError(AeatError, ValueError):
    """Raised when domain identifiers or models are invalid."""
