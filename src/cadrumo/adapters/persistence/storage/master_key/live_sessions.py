"""Process-wide registry of key-holding bucket sessions.

The active-session binding is a :class:`~contextvars.ContextVar`, which is the
right shape for ordinary work: each thread and each ``asyncio.Task`` gets its
own active session, and an encrypt path can never see a sibling context's key.
An embedding host's lifetime watchdog also needs one public shutdown operation
that can zeroise sessions held by other contexts before an abrupt exit. This
module owns that process-wide emergency boundary.

Registration is a :class:`weakref.WeakSet`, so a session that is dropped
without an explicit close is garbage collected normally and the registry never
extends the lifetime of key material it is meant to destroy.

See Also:
    :func:`~.active_session.close_active_bucket_session`
        The ordinary, context-scoped close every normal caller wants.
"""

from __future__ import annotations

import threading
import weakref
from typing import TYPE_CHECKING

from .....core.logging import get_logger

if TYPE_CHECKING:
    from .bucket_session import BucketSession

_log = get_logger(__name__)

#: Every :class:`BucketSession` ever opened and not yet collected. Weak by
#: construction: holding these strongly would keep zeroisable key buffers alive
#: past the point the owning code dropped them, which is the opposite of this
#: module's purpose.
_live_sessions: weakref.WeakSet[BucketSession] = weakref.WeakSet()

#: Guards the set itself. ``WeakSet`` mutation is not atomic under free-threaded
#: builds, and registration happens on whatever thread opened the session.
_lock = threading.Lock()


def register_live_session(session: BucketSession) -> None:
    """Record ``session`` as a live key holder for emergency zeroisation."""
    with _lock:
        _live_sessions.add(session)


def close_all_live_bucket_sessions() -> int:
    """Close every registered session, zeroising its keys.

    The cross-context counterpart to
    :func:`~.active_session.close_active_bucket_session`, for the interpreter
    exit hook and an embedding watchdog's pre-exit hook before an ``os._exit``
    that would otherwise skip both. One session's failure never prevents the
    remaining sessions from being zeroised.

    Returns:
        The number of sessions this call transitioned from unsealed to sealed.
    """
    with _lock:
        sessions = list(_live_sessions)
    closed = 0
    for session in sessions:
        if session.sealed:
            continue
        try:
            session.close()
        except Exception as exc:
            _log.debug(
                "live bucket session close failed during shutdown error_type=%s",
                type(exc).__name__,
            )
            continue
        closed += 1
    return closed


__all__ = ["close_all_live_bucket_sessions", "register_live_session"]
