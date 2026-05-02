"""Domain errors for the :mod:`aeat.domain.deadlines` subpackage.

Every error inherits from :class:`aeat.core.errors.AeatError` so callers have
a single root they can catch when integrating with the deadline engine.
"""

from __future__ import annotations

from ...core.errors import AeatError


class DeadlineError(AeatError):
    """Base class for every error raised by :mod:`aeat.domain.deadlines`."""


class ProfileError(DeadlineError):
    """Raised when an :class:`aeat.domain.deadlines.AutonomoProfile` cannot be loaded or validated."""


class ScheduleComputationError(DeadlineError):
    """Raised when :meth:`aeat.domain.deadlines.DeadlineEngine.compute` cannot produce a schedule.

    Typical triggers include a configured year outside the supported
    calendar range, or an injected catalogue loader returning an
    unknown modelo.
    """
