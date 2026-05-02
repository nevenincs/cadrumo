"""Typed errors raised by the cross-platform file-lock helpers.

Lives separately from :mod:`aeat.core.locks` so callers that only need
the exception type (e.g. for ``except`` clauses) avoid pulling in the
locking implementation and its OS-specific imports.
"""

from __future__ import annotations

from .errors import AeatError


class LockAcquisitionError(AeatError):
    """Raised when an exclusive file lock cannot be acquired within the timeout.

    Bound to a registered :class:`aeat.core.errors.ErrorCode` so callers
    can present a stable error identifier rather than a raw message.
    """


__all__ = ["LockAcquisitionError"]
