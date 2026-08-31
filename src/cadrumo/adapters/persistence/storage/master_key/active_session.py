"""Active-bucket session resolution for the column-level encrypt path.

The column-level :class:`TypeDecorator` set in
``adapters/persistence/storage/crypto/_encrypted_columns.py`` cannot
thread an explicit session reference through SQLAlchemy's
:meth:`process_bind_param` signature (the method is invoked by
SQLAlchemy's column machinery with a fixed ``(self, value, dialect)``
shape). The substrate also forbids module-global mutable state that
could survive a bucket switch — the :class:`BucketSession` instance is
the only legitimate owner of unlocked KEK and DEK bytes.

This module composes both constraints with a ``ContextVar`` (PEP 567)
holding the active :class:`BucketSession`. The CLI entry point opens
a session and enters :func:`activate_session` as a contextmanager;
every column-level decrypt or encrypt call inside the block resolves
the active DEK through :func:`get_active_master_key`. On exit the
``ContextVar`` token is reset to the previous value (``None`` at the
top of the stack), so no *binding* outlives the with-block - the
session itself is not closed here, only unbound from this context.
:func:`close_active_bucket_session` is the explicit eviction boundary:
it closes the current session before removing that exact binding.

The pattern is per-thread and per-async-task by PEP 567 semantics.
``asyncio.Task`` instances inherit a copy of the parent context at
creation time, so the active session crosses into spawned tasks
correctly. :class:`concurrent.futures.ThreadPoolExecutor` workers do
NOT inherit ``ContextVar`` state by default; future code introducing
a thread-pool worker on the encrypt path must propagate the active
session explicitly via :func:`contextvars.copy_context`.
"""

from __future__ import annotations

import atexit as _atexit
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TypeGuard

from .....core.logging import get_logger
from .....core.time.clock import now
from ..bucket.errors import BucketLockedError
from ..errors import SecretStoreError
from ._live_sessions import close_all_live_bucket_sessions
from .bucket_session import BucketSession

_log = get_logger(__name__)

active_session: ContextVar[BucketSession | None] = ContextVar(
    "aeat_active_bucket_session",
    default=None,
)


class NoActiveBucketSessionError(SecretStoreError):
    """Raised when the encrypt path runs outside an active session block.

    The adapter establishes only the observed session state.  The CLI boundary
    decides whether a public profile label makes the canonical login action
    resolvable; this substrate must not manufacture that action from custody
    internals.
    """

    def __init__(self, detail: str | None = None) -> None:
        del detail
        super().__init__(
            context={"active_bucket_session_available": False},
            translated_message="errors.refused.refused_storage_master_key_no_active_session",
        )


@contextmanager
def activate_session(session: BucketSession) -> Iterator[None]:
    """Bind ``session`` as the active :class:`BucketSession` for the block.

    The previous value of the :class:`ContextVar` is restored on exit
    via the :class:`contextvars.Token` returned by ``set()``, so nested
    activations stack and unwind cleanly. The session itself is not
    closed on exit — ownership of the :class:`BucketSession` lifecycle
    stays with the caller that opened it.

    Args:
        session: The unlocked :class:`BucketSession` whose DEK becomes
            the column-level encryption key for the duration of the
            block.
    """
    token = active_session.set(session)
    try:
        yield
    finally:
        active_session.reset(token)


def bind_active_bucket_session(session: BucketSession) -> None:
    """Bind ``session`` as the active session for the rest of this context.

    The unscoped counterpart of :func:`activate_session`, for the one
    caller shape that has no enclosing ``with`` block: a persisted profile
    session resumed at CLI start-up, whose binding must outlive the
    function that opened it and is evicted explicitly by
    :func:`close_active_bucket_session` (or by the interpreter-exit hook).

    :func:`activate_session` cannot serve that shape — entering its
    generator without holding a reference lets the garbage collector
    finalise it, and the ``finally`` clause then resets the binding out
    from under the caller. Callers that DO have a scope must keep using
    :func:`activate_session` so the previous binding is restored on exit.

    Args:
        session: The unlocked :class:`BucketSession` to bind.
    """
    active_session.set(session)


def _require_fresh_active_session() -> BucketSession:
    """Return the active, unexpired :class:`BucketSession` or raise.

    The shared resolution behind :func:`get_active_master_key` and
    :func:`get_active_hmac_subkey`: both key surfaces must refuse
    identically when no session is bound or the bound session expired,
    so the checks live once here.

    Raises:
        NoActiveBucketSessionError: When no :func:`activate_session` block is
            currently active on the calling thread or task.
        BucketLockedError: When the active session has expired.
    """
    session = active_session.get()
    if session is None:
        raise NoActiveBucketSessionError()
    if session.is_expired(now()):
        bucket_id = session.bucket_id
        close_active_bucket_session()
        raise BucketLockedError(bucket_id=bucket_id)
    return session


def get_active_master_key() -> bytes:
    """Return the DEK bytes of the currently-active :class:`BucketSession`.

    Used by every column-level encrypt and decrypt operation in
    ``_encrypted_columns.py``. The DEK (not the KEK) is the
    AES-256-GCM key for the row-ciphertext layer — the KEK only ever
    unwraps the DEK during :meth:`BucketSession.open`.

    Returns:
        The 32-byte DEK used for AES-256-GCM column-level encryption.

    Raises:
        NoActiveBucketSessionError: When no :func:`activate_session` block is
            currently active on the calling thread or task.
        BucketLockedError: When the active session has expired.
    """
    return _require_fresh_active_session().dek


def get_active_hmac_subkey(context: bytes) -> bytes:
    """Return the active session's memoised HKDF sub-key for ``context``.

    The keyed-lookup digest path (:class:`HashedLookup` and the
    secure-object key digest built on it) derives a per-consumer sub-key
    from the active DEK before HMAC-ing its material. That derivation
    depends only on ``(DEK, context)``, so it is memoised on the
    :class:`BucketSession` (see :meth:`BucketSession.hmac_subkey`) and
    resolved here under exactly the freshness checks
    :func:`get_active_master_key` applies.

    Args:
        context: Stable per-consumer HKDF info bytes.

    Returns:
        The 32-byte derived sub-key.

    Raises:
        NoActiveBucketSessionError: When no :func:`activate_session` block is
            currently active on the calling thread or task.
        BucketLockedError: When the active session has expired.
    """
    return _require_fresh_active_session().hmac_subkey(context)


def has_active_bucket_session() -> bool:
    """Return whether an active :class:`BucketSession` is bound."""
    return active_session.get() is not None


def current_active_bucket_session() -> BucketSession | None:
    """Return the currently-bound :class:`BucketSession`, or ``None``.

    Read-only observation of the active-session :class:`~contextvars.ContextVar`
    for callers (storage runtime readiness, per-request secure-object session
    gating) that need the live session's attributes (``bucket_id``, ``sealed``,
    idle deadline) rather than only its DEK (:func:`get_active_master_key`) or
    its presence (:func:`has_active_bucket_session`). Never mutates the
    context; :func:`activate_session`, :func:`suspend_active_session`, and
    :func:`close_active_bucket_session` own binding changes.
    """
    return active_session.get()


def session_serves_bucket(session: BucketSession | None, bucket_id: str) -> TypeGuard[BucketSession]:
    """Return whether ``session`` is open for exactly ``bucket_id``.

    The single bucket-identity comparison for session reuse. Callers holding an
    explicitly-passed session (the auth scope resolves one, then layers
    storage-root and explicit-routing agreement on top) use this; callers
    reading the ambient binding use :func:`active_bucket_session_serves`, which
    is this function applied to the active-session ``ContextVar``.

    One comparison, two entry points: an injected-session caller must not
    re-derive ``session.bucket_id == bucket_id`` locally, because that is the
    comparison whose omission produces the cross-bucket read.

    Typed as a :data:`~typing.TypeGuard` so a caller that passes the guard may
    read the session's own attributes without a redundant ``is not None``
    re-check. :data:`~typing.TypeIs` would be unsound here: this returns
    ``False`` for a perfectly non-``None`` session bound to a different bucket,
    which must not narrow the negative branch to ``None``.
    """
    return session is not None and session.bucket_id == bucket_id


def active_bucket_session_serves(bucket_id: str) -> bool:
    """Return whether the bound session is open for exactly ``bucket_id``.

    The single reuse predicate for callers deciding whether an ambient session
    already serves the bucket they are about to read or write, rather than
    opening a second span over it.

    :func:`has_active_bucket_session` answers a strictly weaker question --
    whether *any* session is bound -- and a caller that resolves a target
    bucket and then reuses on presence alone will operate against whichever
    bucket happens to be bound. The two differ exactly when a session for one
    bucket is ambient while the caller targets another, which is the case that
    reads or writes one profile's encrypted store under another profile's
    identity. Callers that hold a target bucket MUST use this predicate;
    :func:`has_active_bucket_session` remains correct only for callers with no
    target to compare against.

    Storage-root and explicit-routing agreement are a separate, stricter
    concern layered on top of this by
    :func:`~application.auth.operator_scope.active_profile_storage_span`; this
    function owns the bucket-identity half that every caller needs.
    """
    return session_serves_bucket(active_session.get(), bucket_id)


def close_active_bucket_session() -> None:
    """Close and evict the currently bound :class:`BucketSession`.

    The existing :meth:`BucketSession.close` boundary owns key zeroisation,
    sealing, and engine disposal. This function adds only active-context
    eviction. It is idempotent when no session is bound or when the bound
    session is already sealed.

    The binding is cleared in ``finally`` so an unexpected close failure cannot
    leave a key-owning or sealed object advertised as active. An identity check
    preserves a replacement binding installed reentrantly during cleanup.
    """
    session = active_session.get()
    if session is None:
        return
    try:
        session.close()
    finally:
        if active_session.get() is session:
            active_session.set(None)


@contextmanager
def suspend_active_session() -> Iterator[None]:
    """Temporarily clear the active :class:`BucketSession` for the current context."""
    token = active_session.set(None)
    try:
        yield
    finally:
        active_session.reset(token)


def _close_active_session_at_exit() -> None:
    """Best-effort close of every live session on interpreter shutdown.

    Registered as an :func:`atexit.register` hook below. If a session is
    still bound when the interpreter exits (an interrupted CLI run, a
    crashed test, a long-lived REPL) this hook zeroises the key
    buffers in place so the memory footprint at shutdown does not leak
    cleartext key material.

    Closes the calling context's binding first, then sweeps the process-wide
    live-session registry. The sweep is what covers a session bound on another
    thread: ``atexit`` hooks run on the main thread, and by PEP 567 semantics
    that thread observes no binding a worker made, so the context-scoped close
    alone would silently leave a worker's keys in memory.
    """
    try:
        close_active_bucket_session()
    except Exception as exc:
        # Interpreter shutdown is a degraded environment; never raise
        # from an atexit hook, but keep a debug breadcrumb for audit.
        _log.debug("active bucket session cleanup failed at interpreter exit error_type=%s", type(exc).__name__)
    try:
        close_all_live_bucket_sessions()
    except Exception as exc:
        _log.debug("live bucket session sweep failed at interpreter exit error_type=%s", type(exc).__name__)
        return


_atexit.register(_close_active_session_at_exit)


__all__ = [
    "NoActiveBucketSessionError",
    "activate_session",
    "active_bucket_session_serves",
    "bind_active_bucket_session",
    "close_active_bucket_session",
    "current_active_bucket_session",
    "get_active_hmac_subkey",
    "get_active_master_key",
    "has_active_bucket_session",
    "session_serves_bucket",
    "suspend_active_session",
]
