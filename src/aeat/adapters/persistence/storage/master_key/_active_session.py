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
top of the stack), so no key material outlives the with-block.

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
from typing import override

from .....core.errors import resolve_error_message
from .....core.logging import get_logger
from .....core.time import now
from ..bucket._errors import BucketLockedError
from ..errors import SecretStoreError
from ._bucket_session import BucketSession

_log = get_logger(__name__)

_active_session: ContextVar[BucketSession | None] = ContextVar(
    "aeat_active_bucket_session",
    default=None,
)


class NoActiveBucketSessionError(SecretStoreError):
    """Raised when the encrypt path runs outside an active session block.

    Carries no payload — the diagnostic message names the
    canonical remediation verb so operators see how to recover
    without re-parsing the message.
    """

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(
            context={"detail": detail} if detail else None,
            translated_message="errors.refused.refused_storage_master_key_no_active_session",
        )
        self._detail = detail

    @override
    def __str__(self) -> str:
        """Render the locale-backed remediation message while keeping positional args empty."""
        return resolve_error_message(self)


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
    token = _active_session.set(session)
    try:
        yield
    finally:
        _active_session.reset(token)


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
    session = _active_session.get()
    if session is None:
        raise NoActiveBucketSessionError(
            "no active bucket session; run `aeat config switch NAME` "
            "to unlock a profile before invoking commands that decrypt "
            "stored records.",
        )
    if session.is_expired(now()):
        bucket_id = session.bucket_id
        session.close()
        raise BucketLockedError(bucket_id=bucket_id)
    return session.dek


def has_active_bucket_session() -> bool:
    """Return whether an active :class:`BucketSession` is bound."""
    return _active_session.get() is not None


def _close_active_session_at_exit() -> None:
    """Best-effort close of the active session on interpreter shutdown.

    Registered as an :func:`atexit.register` hook below. If a session is
    still bound when the interpreter exits (an interrupted CLI run, a
    crashed test, a long-lived REPL) this hook zeroises the key
    buffers in place so the memory footprint at shutdown does not leak
    cleartext key material.
    """
    session = _active_session.get()
    if session is None:
        return
    try:
        session.close()
    except Exception as exc:
        # Interpreter shutdown is a degraded environment; never raise
        # from an atexit hook, but keep a debug breadcrumb for audit.
        _log.debug("active bucket session cleanup failed at interpreter exit error_type=%s", type(exc).__name__)
        return


_atexit.register(_close_active_session_at_exit)


__all__ = [
    "NoActiveBucketSessionError",
    "activate_session",
    "get_active_master_key",
    "has_active_bucket_session",
]
