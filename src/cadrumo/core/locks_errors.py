"""Typed errors raised by the cross-platform file-lock helpers.

Lives separately from :mod:`core.locks` so callers that only need
the exception type (e.g. for ``except`` clauses) avoid pulling in the
locking implementation and its OS-specific imports.

This module declares only the generic OS sidecar-lock failure raised by
:func:`core.locks.exclusive_file_lock`. Crash-recoverable auth
acquisition locks, bucket PID lockfiles, and secure-storage session
guards expose their own typed errors because they carry holder metadata,
TTL/recovery state, or custody semantics that this primitive does not own.
"""

from __future__ import annotations

from .errors.hierarchy import CadrumoError


class LockAcquisitionError(CadrumoError):
    """Raised when an exclusive file lock cannot be acquired within the timeout.

    Bound to a registered :class:`core.errors.ErrorCode` so callers
    can present a stable error identifier rather than a raw message.
    The registry classifies it as ``LOCKED`` and retryable, meaning a later
    bounded retry may succeed after another process releases the OS lock.
    It does not imply automatic stale-lock deletion or unbounded retry.
    """


__all__ = ["LockAcquisitionError"]
