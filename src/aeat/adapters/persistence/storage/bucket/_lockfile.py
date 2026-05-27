"""Per-bucket ``.lock`` concurrency primitive for the bucket directory model.

Each bucket carries a single PID-stamped lockfile at ``<bucket-dir>/.lock``
created via ``os.open`` with ``O_CREAT | O_EXCL | O_WRONLY``; the
``O_EXCL`` flag is atomic on every POSIX kernel and on Windows NTFS, so a
second-process unlock against a held bucket fails fast with
:class:`aeat.adapters.persistence.storage.bucket.BucketBusyError` per
the substrate locking contract.

The lockfile carries the holder's PID. A stale lock (PID is no longer a
live process) is reclaimed lazily by the acquiring process so an abnormal
process exit (SIGKILL, OS crash, container OOM) does not permanently
strand the bucket; the lazy reclaim is documented under the plan's
"Lockfile staleness detection" open question.
"""

from __future__ import annotations

import atexit
import contextlib
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING

from .....core.config import Settings as _Settings
from .._namespace_registry import BUCKET_LOCK_FILENAME
from ._errors import BucketBusyError

if TYPE_CHECKING:
    from ._layout import BucketPaths

_POLL_INTERVAL_SECONDS = _Settings().aeat_bucket_lock_poll_interval_s


def lock_path(paths: BucketPaths) -> Path:
    """Return the canonical lockfile path for the bucket."""

    return paths.bucket_dir / BUCKET_LOCK_FILENAME


def _read_pid(target: Path) -> int | None:
    """Read the recorded PID from the lockfile, ``None`` on any IO failure."""

    try:
        text = target.read_text(encoding="utf-8").strip()
    except (FileNotFoundError, PermissionError):
        return None
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _pid_is_alive(pid: int) -> bool:
    """Cross-platform best-effort liveness probe for a holding PID.

    Returns ``True`` when the OS reports the PID as a live process and
    ``False`` when the OS reports it as gone. A permission error (the PID
    exists but belongs to another user) is treated as alive: from this
    process's perspective the lock cannot be safely reclaimed.
    """

    if pid <= 0:
        return False
    if os.name == "nt":
        # On Windows ``os.kill(pid, 0)`` reports terminated-but-cached PIDs
        # as alive until the kernel reclaims the PID, so the probe goes
        # through ``OpenProcess`` + ``GetExitCodeProcess``: a process whose
        # exit code is not ``STILL_ACTIVE`` (259) is dead even if its PID
        # is still allocated.
        import ctypes
        from ctypes import wintypes

        process_query_limited_information = 0x1000
        still_active = 259
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
        if not handle:
            # ``ERROR_INVALID_PARAMETER`` (87) is returned for a PID that
            # no longer exists; any other failure is treated as alive so
            # we never delete a foreign-user lockfile.
            last_error = ctypes.get_last_error()
            return last_error != 87
        try:
            code = wintypes.DWORD()
            ok = kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
            if not ok:
                return True
            return code.value == still_active
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _try_create_lock(target: Path, pid: int) -> bool:
    """Attempt the atomic ``O_EXCL`` lockfile creation.

    Returns ``True`` when the lockfile was created and the PID written,
    ``False`` when another process already holds the lockfile.
    """

    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        fd = os.open(target, flags, 0o644)
    except FileExistsError:
        return False
    try:
        os.write(fd, f"{pid}\n".encode("ascii"))
    finally:
        os.close(fd)
    return True


def _reclaim_if_stale(target: Path) -> None:
    """Remove the lockfile if the recorded PID is no longer a live process."""

    pid = _read_pid(target)
    if pid is None or not _pid_is_alive(pid):
        with contextlib.suppress(FileNotFoundError):
            target.unlink()


def acquire_lock(paths: BucketPaths, *, wait_seconds: float = 0.0) -> None:
    """Acquire the per-bucket lockfile or raise :class:`BucketBusyError`.

    Args:
        paths: The bucket paths whose ``.lock`` to acquire.
        wait_seconds: Maximum time to wait for the lock to become free.
            Defaults to ``0.0`` (no wait); callers that want bounded
            waiting pass a positive value.

    Raises:
        BucketBusyError: When the lockfile is held by a live process and
            the wait window expires.
    """

    target = lock_path(paths)
    paths.bucket_dir.mkdir(parents=True, exist_ok=True)
    pid = os.getpid()

    deadline = time.monotonic() + max(wait_seconds, 0.0)
    while True:
        _reclaim_if_stale(target)
        if _try_create_lock(target, pid):
            _ATEXIT_REGISTRY.add(target)
            return
        if time.monotonic() >= deadline:
            holding_pid = _read_pid(target) or 0
            raise BucketBusyError(bucket_id=paths.bucket_id, holding_pid=holding_pid)
        time.sleep(_POLL_INTERVAL_SECONDS)


def release_lock(paths: BucketPaths) -> None:
    """Release the per-bucket lockfile owned by this process.

    Removes the lockfile only when the recorded PID matches this process;
    a foreign lockfile is left alone so a stale-reclaim race cannot delete
    another process's lock.
    """

    target = lock_path(paths)
    pid = _read_pid(target)
    if pid is None:
        _ATEXIT_REGISTRY.discard(target)
        return
    if pid != os.getpid():
        return
    with contextlib.suppress(FileNotFoundError):
        target.unlink()
    _ATEXIT_REGISTRY.discard(target)


class _AtexitRegistry:
    """Set of lockfile paths released at interpreter shutdown.

    The atexit hook iterates the set on normal exit and unlinks each
    lockfile whose recorded PID matches this process; abnormal exits
    (SIGKILL, OS crash) bypass the hook and rely on lazy stale reclaim.
    """

    def __init__(self) -> None:
        self._targets: set[Path] = set()
        atexit.register(self._release_all)

    def add(self, target: Path) -> None:
        self._targets.add(target)

    def discard(self, target: Path) -> None:
        self._targets.discard(target)

    def _release_all(self) -> None:
        own_pid = os.getpid()
        for target in list(self._targets):
            pid = _read_pid(target)
            if pid == own_pid:
                with contextlib.suppress(FileNotFoundError):
                    target.unlink()
            self._targets.discard(target)


_ATEXIT_REGISTRY = _AtexitRegistry()


__all__ = ["acquire_lock", "lock_path", "release_lock"]
