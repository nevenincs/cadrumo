"""Cross-platform exclusive file locking.

The helper exposes :func:`exclusive_file_lock`, a context manager that
acquires an OS-level exclusive lock on a sidecar file alongside a
protected resource, and :func:`exclusive_file_lock_async`, its awaitable
twin for callers running on an event loop. The two share one sidecar
path, one OS primitive, one deadline and one refusal; they differ only
in how they wait between attempts. Two operating-system primitives back
the helper:

- POSIX (Linux, macOS): :func:`fcntl.flock` with ``LOCK_EX | LOCK_NB``.
- Windows: :func:`msvcrt.locking` with ``LK_NBLCK`` against a one-byte
  region of the lock file.

The wait loop is identical across platforms: try the non-blocking
acquire, sleep for a small backoff interval, retry until the timeout
elapses. On timeout the helper raises :class:`LockAcquisitionError`
(category ``LOCKED`` in the error registry).

The lock file is created adjacent to the protected path by appending
the suffix ``.lock``. The lock fd is held for the duration of the
context. The lock file itself is left on disk after release; cleanup
of stale lock files is the consumer's responsibility because deleting
the file while another process is racing to acquire it would create
a TOCTOU window.

This primitive is deliberately metadata-free. It does not write a PID,
hostname, profile id, timeout stamp, or secure-storage custody state into
the sidecar file, and it does not perform stale-lock recovery. Consumers
that need recoverable lock records, bucket ownership, or auth-acquisition
TTL semantics own those protocols above this OS-lock layer.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Final, override

from .config import load_settings as _load_settings
from .locks_errors import LockAcquisitionError
from .logging import get_logger

_log = get_logger(__name__)


def _default_lock_timeout() -> float:
    """Return the currently effective lock-acquire timeout in seconds.

    Resolved each call via :func:`load_settings` so an
    :func:`override_settings` block (test scope) is honoured. Replaces a
    module-level constant that snapshotted ``Settings()`` at import time
    and could not be overridden after the module had loaded.

    The setting is only a local wait budget. It is not a lease, TTL, or
    stale-lock age; the OS lock is released by descriptor teardown.
    """
    return _load_settings().cadrumo_file_lock_timeout_s


def _default_retry_backoff() -> float:
    """Return the currently effective non-blocking retry backoff in seconds."""
    return _load_settings().cadrumo_file_lock_retry_backoff_s


class _DefaultLockTimeout:
    """Sentinel marking ``timeout`` as "resolve from settings on call"."""

    @override
    def __repr__(self) -> str:
        return "DEFAULT_LOCK_TIMEOUT"


DEFAULT_LOCK_TIMEOUT: Final[_DefaultLockTimeout] = _DefaultLockTimeout()
"""Sentinel for :func:`exclusive_file_lock` ``timeout``; resolves at call time."""

_DEFAULT_RETRY_BACKOFF: Final[_DefaultLockTimeout] = _DefaultLockTimeout()
"""Sentinel for :func:`exclusive_file_lock` ``retry_backoff``; resolves at call time."""


def _lock_path_for(target: Path) -> Path:
    """Return the canonical lock-file path adjacent to ``target``."""
    return target.with_name(target.name + ".lock")


if sys.platform == "win32":  # pragma: no cover - branch covered on Windows only
    import msvcrt

    def _try_lock(fd: int) -> bool:
        """Try to acquire an exclusive lock on ``fd``; return ``True`` on success."""
        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False

    def _release_lock(fd: int) -> None:
        """Release the exclusive lock previously acquired via :func:`_try_lock`."""
        # Best-effort: the OS already releases the lock when the
        # descriptor is closed. Avoid raising during teardown.
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        except OSError:
            _log.debug("exclusive_file_lock: Windows lock release failed for fd %s", fd, exc_info=True)

else:  # POSIX
    import fcntl

    def _try_lock(fd: int) -> bool:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False

    def _release_lock(fd: int) -> None:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            _log.debug("exclusive_file_lock: POSIX lock release failed for fd %s", fd, exc_info=True)


def _resolved_lock_budget(
    timeout: float | _DefaultLockTimeout,
    retry_backoff: float | _DefaultLockTimeout,
) -> tuple[float, float]:
    """Resolve sentinel defaults from settings and enforce both bounds."""
    # Resolve sentinel defaults via load_settings() so override_settings()
    # blocks (test scope) propagate. A literal float passed by the caller
    # bypasses settings entirely.
    if isinstance(timeout, _DefaultLockTimeout):
        timeout = _default_lock_timeout()
    if isinstance(retry_backoff, _DefaultLockTimeout):
        retry_backoff = _default_retry_backoff()
    if timeout < 0:
        raise LockAcquisitionError(f"timeout must be non-negative; got {timeout}")
    # The Settings field that supplies the default is bound `gt=0`, but a
    # caller-supplied value bypassed settings entirely and reached the sleep,
    # which raises a bare ValueError on a negative interval — surfacing as an
    # unhandled crash instead of this primitive's documented refusal. The bound
    # is enforced here so both routes carry one contract. Zero is refused too:
    # a zero interval is a busy-spin the typed field does not permit.
    if retry_backoff <= 0:
        raise LockAcquisitionError(f"retry_backoff must be strictly positive; got {retry_backoff}")
    return timeout, retry_backoff


def _open_lock_fd(target: Path) -> tuple[int, Path]:
    """Open the sidecar lock descriptor for ``target``."""
    lock_path = _lock_path_for(target)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    # Add the close-on-exec / no-inherit flag so the lock-file descriptor
    # cannot leak into a subprocess spawned while the lock is held.
    # POSIX: O_CLOEXEC; Windows: O_NOINHERIT. A leaked descriptor would
    # extend the lock's lifetime to the child process and could deadlock
    # an unrelated writer if the child outlives the parent.
    open_flags = os.O_RDWR | os.O_CREAT
    open_flags |= getattr(os, "O_CLOEXEC", 0)
    open_flags |= getattr(os, "O_NOINHERIT", 0)
    return os.open(lock_path, open_flags, 0o600), lock_path


def _lock_acquired_before_deadline(fd: int, lock_path: Path, *, deadline: float, timeout: float) -> bool:
    """Attempt one non-blocking acquire; refuse once the deadline has passed.

    Returns ``True`` when the lock is held and ``False`` when the caller
    should back off and retry. The waiting itself belongs to the caller,
    which is what lets the synchronous and awaitable acquisitions share
    one deadline and one refusal without sharing a sleep.
    """
    if _try_lock(fd):
        return True
    if time.monotonic() >= deadline:
        _log.warning(
            "exclusive_file_lock: timed out waiting for %s after %.2fs",
            lock_path,
            timeout,
        )
        raise LockAcquisitionError(
            f"failed to acquire exclusive lock on {lock_path} within {timeout:.2f}s",
        )
    return False


@contextmanager
def exclusive_file_lock(
    target: Path,
    *,
    timeout: float | _DefaultLockTimeout = DEFAULT_LOCK_TIMEOUT,
    retry_backoff: float | _DefaultLockTimeout = _DEFAULT_RETRY_BACKOFF,
) -> Iterator[Path]:
    """Acquire an OS-level exclusive lock on a sidecar lock file.

    The sidecar lock file is created alongside ``target`` with the suffix
    ``.lock``. The caller is expected to use the lock to coordinate
    concurrent access to ``target``. The lock is released when the
    context manager exits, whether normally or via exception. The lock
    file itself is left on disk so a racing acquirer never sees a
    transient missing-file state.

    On Windows ``msvcrt.locking`` enforces a mandatory lock against a
    single byte of the lock file. On POSIX ``fcntl.flock`` is advisory —
    readers that do not also acquire the lock can still observe the
    protected resource mid-write. Callers MUST treat the lock as advisory
    across the whole file regardless of the underlying primitive.

    The sidecar carries no ownership metadata and is not deleted on
    release. This is a generic local coordination primitive for atomic
    file updates; higher-level bucket lockfiles, auth acquisition locks,
    and secure-object sessions provide their own holder records, TTLs,
    custody checks, and recovery rules.

    Args:
        target: Path to the resource being protected. The lock sidecar
            is created at ``<target>.lock``. The parent directory must
            exist before the call.
        timeout: Maximum time in seconds to wait for the lock. Defaults
            to ``DEFAULT_LOCK_TIMEOUT``. ``0`` requests a single non-
            blocking attempt.
        retry_backoff: Sleep interval between non-blocking attempts.
            Must be strictly positive, matching the ``gt=0`` bound on the
            :class:`~core.config.Settings` field that supplies its default.
            Tests may shorten this; defaults to ``0.05``.

    Yields:
        The :class:`Path` of the acquired lock sidecar.

    Raises:
        LockAcquisitionError: If the lock cannot be acquired within
            ``timeout`` seconds, if ``timeout`` is negative, or if
            ``retry_backoff`` is not strictly positive. The
            error category is ``LOCKED`` and ``retryable`` is ``True``.
            The retryable flag means "another acquirer may release
            shortly and the operation could succeed on retry"; consumers
            that retry MUST bound the retry budget themselves.
    """
    timeout, retry_backoff = _resolved_lock_budget(timeout, retry_backoff)
    fd, lock_path = _open_lock_fd(target)
    try:
        deadline = time.monotonic() + timeout
        while not _lock_acquired_before_deadline(fd, lock_path, deadline=deadline, timeout=timeout):
            time.sleep(retry_backoff)
        _log.debug("exclusive_file_lock: acquired %s", lock_path)
        try:
            yield lock_path
        finally:
            _release_lock(fd)
            _log.debug("exclusive_file_lock: released %s", lock_path)
    finally:
        os.close(fd)


@asynccontextmanager
async def exclusive_file_lock_async(
    target: Path,
    *,
    timeout: float | _DefaultLockTimeout = DEFAULT_LOCK_TIMEOUT,
    retry_backoff: float | _DefaultLockTimeout = _DEFAULT_RETRY_BACKOFF,
) -> AsyncIterator[Path]:
    """Acquire the same OS-level exclusive lock without blocking the event loop.

    This is the awaitable twin of :func:`exclusive_file_lock`, not a
    replacement for it: identical sidecar path, identical OS primitive,
    identical deadline and refusal. The only difference is that the wait
    between non-blocking attempts is :func:`asyncio.sleep` rather than
    :func:`time.sleep`, so a coroutine waiting on a contended lock yields
    to the loop instead of stalling every other task on it.

    Use this from a coroutine. Use the synchronous form everywhere else —
    a synchronous caller has no loop to block and gains nothing here.

    Cancellation: the wait is a cancellation point, so a cancelled task
    stops waiting promptly and the descriptor is closed on the way out.
    The synchronous form cannot be cancelled at all, which is what makes
    it unsuitable for a polling UI worker.

    An executor hop (:func:`asyncio.to_thread`, ``run_in_executor``) is
    deliberately NOT the mechanism here. It pays a thread hop per call,
    and it drops the :mod:`contextvars` context that carries the active
    run id, so an offloaded read that records an observability event
    raises instead of recording it.

    Args and refusals are exactly those of :func:`exclusive_file_lock`.

    Yields:
        The :class:`Path` of the acquired lock sidecar.
    """
    timeout, retry_backoff = _resolved_lock_budget(timeout, retry_backoff)
    fd, lock_path = _open_lock_fd(target)
    try:
        deadline = time.monotonic() + timeout
        while not _lock_acquired_before_deadline(fd, lock_path, deadline=deadline, timeout=timeout):
            await asyncio.sleep(retry_backoff)
        _log.debug("exclusive_file_lock_async: acquired %s", lock_path)
        try:
            yield lock_path
        finally:
            _release_lock(fd)
            _log.debug("exclusive_file_lock_async: released %s", lock_path)
    finally:
        os.close(fd)
