"""Domain errors for the :mod:`aeat.domain.deadlines` subpackage.

Every error inherits from :class:`aeat.core.errors.AeatError` so callers have
a single root they can catch when integrating with the deadline engine.
"""

from __future__ import annotations

from ...core.errors import AeatError


class DeadlineError(AeatError):
    """Base class for every error raised by :mod:`aeat.domain.deadlines`."""


class ProfileError(DeadlineError):
    """Raised when an :class:`aeat.domain.deadlines.TaxpayerProfile` cannot be loaded or validated."""


class ScheduleComputationError(DeadlineError):
    """Raised when the engine cannot produce a valid schedule.

    Often caused by a mismatch between the requested year and the
    registry's coverage, or by profile facts that trigger an
    unknown modelo.
    """


class DeadlineValidationError(DeadlineError, ValueError):
    """Raised when deadline records violate state or shape invariants.

    Inherits from ValueError to maintain compatibility with Pydantic
    validators.
    """
