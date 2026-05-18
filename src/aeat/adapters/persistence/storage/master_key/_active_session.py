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

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from ..errors import SecretStoreError
from ._bucket_session import BucketSession

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

    Raises:
        NoActiveBucketSessionError: When no :func:`activate_session`
            block is currently active on the calling thread or task.
            The diagnostic points the operator at ``aeat config
            profile switch NAME``.
    """

    session = _active_session.get()
    if session is None:
        raise NoActiveBucketSessionError(
            "no active bucket session; run `aeat config profile switch NAME` "
            "to unlock a profile before invoking commands that decrypt "
            "stored records.",
        )
    return session.dek


__all__ = [
    "NoActiveBucketSessionError",
    "activate_session",
    "get_active_master_key",
]
