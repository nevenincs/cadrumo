"""Domain errors for the ``aeat.normatives`` subpackage.

All exceptions raised while loading, querying, verifying, or citing
Spanish tax normatives inherit from :class:`NormativeError`, which in
turn inherits from :class:`aeat.errors.AeatError`.
"""

from __future__ import annotations

from ...core.errors import AeatError


class NormativeError(AeatError):
    """Base error for every ``aeat.normatives`` failure mode."""


class NormativeParseError(NormativeError):
    """Raised when a committed normative JSON fails schema validation."""


class NormativeNotFoundError(NormativeError):
    """Raised when a requested normative or article is missing."""
