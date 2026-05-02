"""Error hierarchy for the self-healing sync runner.

All sync-layer errors inherit from :class:`SyncError`, which in turn
inherits from :class:`aeat.core.errors.AeatError`. The narrow subclass
hierarchy lets callers catch specific failures
(:class:`WireValidationError`, :class:`DivergenceClassificationError`,
:class:`HealingError`, :class:`DivergenceRepositoryError`) without
swallowing unrelated sync errors.
"""

from __future__ import annotations

from ...core.errors import AeatError


class SyncError(AeatError):
    """Base class for every error raised by :mod:`aeat.application.sync`."""


class WireValidationError(SyncError):
    """Raised when a live AEAT payload fails strict pydantic validation."""


class DivergenceClassificationError(SyncError):
    """Raised when the classifier cannot decide the shape of a divergence."""


class HealingError(SyncError):
    """Raised when a healing strategy cannot apply a divergence record."""


class DivergenceRepositoryError(SyncError):
    """Raised when the divergence repository cannot persist or load a record."""
