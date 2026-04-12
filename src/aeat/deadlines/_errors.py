"""Domain errors for the deadline-engine subpackage.

All errors inherit from :class:`aeat.errors.AeatError` so that callers
have a single root they can catch when integrating with the engine.
"""

from __future__ import annotations

from aeat.errors import AeatError


class DeadlineError(AeatError):
    """Base class for every error raised by :mod:`aeat.deadlines`."""


class ProfileError(DeadlineError):
    """Raised when an :class:`AutonomoProfile` cannot be loaded or validated."""


class ScheduleComputationError(DeadlineError):
    """Raised when :meth:`DeadlineEngine.compute` cannot produce a schedule.

    Examples:
        - The configured year is outside the supported calendar range.
        - The injected catalogue loader returned an unknown modelo.
    """
