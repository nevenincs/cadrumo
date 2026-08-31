"""Process-wide registry of key-holding bucket sessions, for emergency zeroisation.

The active-session binding is a :class:`~contextvars.ContextVar`, which is the
right shape for its job: each thread and each ``asyncio.Task`` gets its own
active session, and an encrypt path can never see a *sibling* context's key. A
child task spawned from within a bound context inherits that binding by PEP 567
copy-on-create - the same logical session extending into a scope the caller
created, not a leak across contexts. It has one blind spot, and only one. A
caller that needs to zeroise *every* live
session - not the one bound in its own context - cannot reach the others, because
by PEP 567 semantics a thread observes no binding another thread made.

That blind spot is load-bearing exactly once: when the process is about to die
abruptly. An embedding host's lifetime watchdog may reap with :func:`os._exit`,
which bypasses :mod:`atexit`, and it runs on its own daemon thread - so the
sessions it most needs to zeroise (bound inside in-flight warm workers) are
precisely the ones its context cannot see. Interpreter shutdown has the same
shape whenever a session was bound off the main thread.

This module is that escape hatch and nothing more. It does NOT own session
lifecycle, does NOT bind anything, and must never be used to *find* a session to
work with - :func:`~.active_session.get_active_master_key` and its neighbours
remain the only sanctioned readers, and routing real work through here would
re-create the shared-key hazard the ContextVar design exists to prevent.

Registration is a :class:`weakref.WeakSet`, so a session that is dropped without
an explicit close is garbage collected normally and its buffers go with it; the
registry never extends the lifetime of key material it is meant to destroy.

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
    """Record ``session`` as a live key holder for emergency zeroisation.

    Called from the :class:`BucketSession` constructor, so every session that
    has ever taken ownership of key buffers is covered regardless of how - or
    whether - it is later bound to a context.

    Args:
        session: The freshly constructed session.
    """
    with _lock:
        _live_sessions.add(session)


def live_bucket_session_count() -> int:
    """Return how many registered sessions are still unsealed.

    Diagnostics and tests only; never a control-flow input for the encrypt path.
    """
    with _lock:
        sessions = list(_live_sessions)
    return sum(1 for session in sessions if not session.sealed)


def close_all_live_bucket_sessions() -> int:
    """Close every registered session, zeroising its keys. Returns how many closed.

    The cross-context counterpart to
    :func:`~.active_session.close_active_bucket_session`, for the two callers
    that genuinely need it: the interpreter-exit hook and an embedding watchdog's
    pre-exit hook before an :func:`os._exit` that would otherwise skip both.

    Deliberately tolerant. It runs while the process is being torn down, so a
    session may be mid-use on another thread and its engine disposal may fail;
    one session's failure must not prevent the rest from being zeroised.
    :meth:`BucketSession.close` is idempotent, so an already-sealed session is a
    cheap no-op and double-closing is safe.

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
            # Never raise from a shutdown path; the remaining sessions still
            # need zeroising and the caller is usually about to _exit.
            _log.debug(
                "live bucket session close failed during shutdown error_type=%s",
                type(exc).__name__,
            )
            continue
        closed += 1
    return closed


__all__ = [
    "close_all_live_bucket_sessions",
    "live_bucket_session_count",
    "register_live_session",
]
