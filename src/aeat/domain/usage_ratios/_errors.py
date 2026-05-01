"""Domain exceptions for :mod:`aeat.domain.financial.usage_ratios`."""

from __future__ import annotations

from ...core.errors import AeatError

__all__ = ["UsageRatioError", "UsageRatioPersistenceError"]


class UsageRatioError(AeatError):
    """Base error for every usage-ratio profile failure."""


class UsageRatioPersistenceError(UsageRatioError):
    """Raised when the usage-ratio profile cannot be read or written."""
