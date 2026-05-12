"""Domain errors for the ``aeat.domain.normatives`` subpackage.

All exceptions raised while loading, querying, verifying, or citing
Spanish tax normatives inherit from :class:`NormativeError`, which in
turn inherits from :class:`aeat.core.errors.AeatError`.
"""

from __future__ import annotations

from ...core.errors import AeatError


class NormativeError(AeatError):
    """Base error for every ``aeat.domain.normatives`` failure mode."""


class NormativeParseError(NormativeError):
    """Raised when a committed normative JSON fails schema validation."""


class NormativeNotFoundError(NormativeError):
    """Raised when a requested normative or article is missing."""


class NormativeValidationError(NormativeError, ValueError):
    """Raised on invalid normative field values. Inherits from ValueError for Pydantic."""
