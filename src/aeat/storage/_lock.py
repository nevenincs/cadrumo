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

import contextlib
import os
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Final

from ..logging import get_logger
from .errors import LockAcquisitionError

_log = get_logger(__name__)

DEFAULT_LOCK_TIMEOUT: Final[float] = 30.0
"""Default timeout for :func:`exclusive_file_lock` in seconds."""

_RETRY_BACKOFF: Final[float] = 0.05
"""Sleep interval between non-blocking lock-acquire attempts."""


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
        with contextlib.suppress(OSError):
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)

else:  # POSIX
    import fcntl

    def _try_lock(fd: int) -> bool:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False

    def _release_lock(fd: int) -> None:
        with contextlib.suppress(OSError):
            fcntl.flock(fd, fcntl.LOCK_UN)


@contextmanager
def exclusive_file_lock(
    target: Path,
    *,
    timeout: float = DEFAULT_LOCK_TIMEOUT,
    retry_backoff: float = _RETRY_BACKOFF,
) -> Iterator[Path]:
    """Acquire an OS-level exclusive lock on a sidecar lock file.

    The sidecar lock file is created alongside ``target`` with the suffix
    ``.lock``. The caller is expected to use the lock to coordinate
    concurrent access to ``target``. The lock is released when the
    context manager exits, whether normally or via exception. The lock
    file itself is left on disk so a racing acquirer never sees a
    transient missing-file state.

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
            ``timeout`` seconds. The error category is ``LOCKED`` and
            ``retryable`` is ``True``.
        OSError: If the lock-file descriptor cannot be opened. The
            caller decides whether to wrap.
    """
    if timeout < 0:
        raise LockAcquisitionError(f"timeout must be non-negative; got {timeout}")
    lock_path = _lock_path_for(target)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        deadline = time.monotonic() + timeout
        while True:
            if _try_lock(fd):
                break
            if time.monotonic() >= deadline:
                raise LockAcquisitionError(
                    f"failed to acquire exclusive lock on {lock_path} within {timeout:.2f}s",
                )
            time.sleep(retry_backoff)
        try:
            yield lock_path
        finally:
            _release_lock(fd)
    finally:
        os.close(fd)
