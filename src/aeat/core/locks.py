"""Cross-platform exclusive file locking.

The helper exposes :func:`exclusive_file_lock`, a context manager that
acquires an OS-level exclusive lock on a sidecar file alongside a
protected resource. Two operating-system primitives back the helper:

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
"""

from __future__ import annotations

import os
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
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
    """
    return _load_settings().aeat_file_lock_timeout_s


def _default_retry_backoff() -> float:
    """Return the currently effective non-blocking retry backoff in seconds."""
    return _load_settings().aeat_file_lock_retry_backoff_s


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


def fsync_parent_dir(target: Path) -> None:
    """Best-effort fsync of the directory containing ``target``.

    POSIX-only — Windows does not support fsync against a directory
    handle (``os.O_DIRECTORY`` is not defined), and on Windows the
    directory entry is updated atomically with ``os.replace`` anyway.

    Used after an ``os.replace`` swap-in to ensure the directory entry
    update is durable across power loss. Without this, a crash between
    ``os.replace`` and the next directory flush could leave the entry
    in an inconsistent state on POSIX filesystems where file fsync
    does not imply directory fsync (ext4, xfs, etc.).

    The function never raises — directory fsync is a best-effort
    durability hardening, not a correctness gate. Callers that hit
    a sandboxed-/read-only-/non-directory FD path should not see a
    spurious failure on top of an otherwise-successful atomic
    replace.
    """
    if not hasattr(os, "O_DIRECTORY"):
        return
    parent = target.parent
    try:
        fd = os.open(parent, os.O_DIRECTORY | os.O_RDONLY)
    except OSError:
        _log.debug("fsync_parent_dir: could not open parent directory %s", parent, exc_info=True)
        return
    try:
        try:
            os.fsync(fd)
        except OSError:
            _log.debug("fsync_parent_dir: could not fsync parent directory %s", parent, exc_info=True)
    finally:
        try:
            os.close(fd)
        except OSError:
            _log.debug("fsync_parent_dir: could not close parent directory fd for %s", parent, exc_info=True)


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

    Args:
        target: Path to the resource being protected. The lock sidecar
            is created at ``<target>.lock``. The parent directory must
            exist before the call.
        timeout: Maximum time in seconds to wait for the lock. Defaults
            to ``DEFAULT_LOCK_TIMEOUT``. ``0`` requests a single non-
            blocking attempt.
        retry_backoff: Sleep interval between non-blocking attempts.
            Tests may shorten this; defaults to ``0.05``.

    Yields:
        The :class:`Path` of the acquired lock sidecar.

    Raises:
        LockAcquisitionError: If the lock cannot be acquired within
            ``timeout`` seconds, or if ``timeout`` is negative. The
            error category is ``LOCKED`` and ``retryable`` is ``True``.
            The retryable flag means "another acquirer may release
            shortly and the operation could succeed on retry"; consumers
            that retry MUST bound the retry budget themselves.
    """
    # Resolve sentinel defaults via load_settings() so override_settings()
    # blocks (test scope) propagate. A literal float passed by the caller
    # bypasses settings entirely.
    if isinstance(timeout, _DefaultLockTimeout):
        timeout = _default_lock_timeout()
    if isinstance(retry_backoff, _DefaultLockTimeout):
        retry_backoff = _default_retry_backoff()
    if timeout < 0:
        raise LockAcquisitionError(f"timeout must be non-negative; got {timeout}")
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
    fd = os.open(lock_path, open_flags, 0o600)
    try:
        deadline = time.monotonic() + timeout
        while True:
            if _try_lock(fd):
                break
            if time.monotonic() >= deadline:
                _log.warning(
                    "exclusive_file_lock: timed out waiting for %s after %.2fs",
                    lock_path,
                    timeout,
                )
                raise LockAcquisitionError(
                    f"failed to acquire exclusive lock on {lock_path} within {timeout:.2f}s",
                )
            time.sleep(retry_backoff)
        _log.debug("exclusive_file_lock: acquired %s", lock_path)
        try:
            yield lock_path
        finally:
            _release_lock(fd)
            _log.debug("exclusive_file_lock: released %s", lock_path)
    finally:
        os.close(fd)
