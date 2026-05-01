"""Error hierarchy for the unified review queue.

All review-layer errors inherit from :class:`ReviewError` which in
turn inherits from :class:`aeat.core.errors.AeatError` per the project
mandate.
"""

from __future__ import annotations

from ...core.errors import AeatError


class ReviewError(AeatError):
    """Base class for every error raised by :mod:`aeat.application.review`."""


class ReviewSourceLoadError(ReviewError):
    """Raised when a source disk file is present but cannot be parsed."""


class ReviewKindReservedError(ReviewError):
    """Raised when the CLI receives a reserved-but-not-implemented kind token.

    Carries the blocking reason returned by
    :func:`aeat.application.review._enums.reserved_kind_reason`.
    """

    def __init__(self, token: str, reason: str) -> None:
        """Construct the error with the offending token and its blocking reason.

        Args:
            token: The ``--kind`` value supplied by the user.
            reason: Human-readable explanation naming the blocking
                upstream issue or record type.
        """
        super().__init__(f"--kind {token!r} is reserved but not yet emitted: {reason}")
        self.token = token
        self.reason = reason
