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
import os
import time
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from .....core.config import load_settings as _load_settings
from .....core.external_constants import UTF_8_ENCODING
from .....core.logging import get_logger
from .._namespace_registry import BUCKET_LOCK_FILENAME
from ._errors import BucketBusyError, BucketValidationError

if TYPE_CHECKING:
    from ._layout import BucketPaths

_log = get_logger(__name__)
_LOCKFILE_MODE = 0o600
_LOCKFILE_VALIDATION_SURFACE = "bucket_lockfile"


class _PidReadState(Enum):
    MISSING = "missing"
    UNREADABLE = "unreadable"
    INVALID = "invalid"


_PidReadResult = int | _PidReadState


def _poll_interval_seconds() -> float:
    """Return the currently effective bucket-lock poll interval in seconds.

    Resolved per-call via :func:`load_settings` so an
    :func:`override_settings` block (test scope) is honoured. Replaces a
    module-level constant that snapshotted settings at import time
    and could not be overridden after the module had loaded.
    """
    return _load_settings().aeat_bucket_lock_poll_interval_s


def lock_path(paths: BucketPaths) -> Path:
    """Return the canonical lockfile path for the bucket."""
    return paths.bucket_dir / BUCKET_LOCK_FILENAME


def _read_pid(target: Path) -> _PidReadResult:
    """Read the recorded PID from the lockfile with explicit failure states."""
    try:
        text = target.read_text(encoding=UTF_8_ENCODING).strip()
    except FileNotFoundError:
        return _PidReadState.MISSING
    except PermissionError:
        _log.debug("bucket lockfile pid unreadable; treating lock as non-reclaimable unknown holder")
        return _PidReadState.UNREADABLE
    if not text:
        _log.debug("bucket lockfile pid empty; treating lock as stale")
        return _PidReadState.INVALID
    try:
        return int(text)
    except ValueError:
        _log.debug("bucket lockfile pid malformed; treating lock as stale")
        return _PidReadState.INVALID


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
            missing = last_error == 87
            if not missing:
                _log.debug("bucket lockfile pid liveness probe unavailable; treating holder as alive")
            return not missing
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
        _log.debug("bucket lockfile pid liveness probe denied; treating holder as alive")
        return True
    return True


def _holding_pid_for_error(pid: _PidReadResult) -> int:
    """Return the PID exposed on `BucketBusyError` without leaking read-state details."""
    if isinstance(pid, int):
        return pid
    return 0


def _unlink_lockfile_if_present(target: Path, *, reason: str) -> None:
    """Remove a lockfile and log if a race already removed it."""
    try:
        target.unlink()
    except FileNotFoundError:
        _log.debug("bucket lockfile unlink skipped missing file reason=%s", reason)


def _cleanup_created_lockfile(target: Path, *, reason: str) -> None:
    """Best-effort cleanup for a lockfile that was created but not acquired."""
    try:
        _unlink_lockfile_if_present(target, reason=reason)
    except OSError as exc:
        _log.debug(
            "bucket lockfile create cleanup failed reason=%s error=%s",
            reason,
            type(exc).__name__,
        )


def _write_lockfile_pid(fd: int, pid: int) -> None:
    """Write the PID payload fully to an already-created lockfile descriptor."""
    payload = f"{pid}\n".encode("ascii")
    view = memoryview(payload)
    offset = 0
    while offset < len(view):
        written = os.write(fd, view[offset:])
        if written <= 0:
            raise OSError("bucket lockfile pid write made no progress")
        offset += written


def _try_create_lock(target: Path, pid: int) -> bool:
    """Attempt the atomic ``O_EXCL`` lockfile creation.

    Returns ``True`` when the lockfile was created and the PID written,
    ``False`` when another process already holds the lockfile.
    """
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        fd = os.open(target, flags, _LOCKFILE_MODE)
    except FileExistsError:
        return False
    write_failed = False
    try:
        _write_lockfile_pid(fd, pid)
    except OSError:
        write_failed = True
        _cleanup_created_lockfile(target, reason="pid_write_failure")
        raise
    finally:
        try:
            os.close(fd)
        except OSError as exc:
            _log.debug("bucket lockfile close failed after create error=%s", type(exc).__name__)
            if not write_failed:
                _cleanup_created_lockfile(target, reason="pid_close_failure")
                raise
    return True


def _reclaim_if_stale(target: Path) -> None:
    """Remove the lockfile if the recorded PID is no longer a live process."""
    pid = _read_pid(target)
    if pid is _PidReadState.UNREADABLE:
        _log.debug("bucket lockfile stale reclaim skipped unreadable lockfile")
        return
    should_reclaim = pid is _PidReadState.INVALID or (isinstance(pid, int) and not _pid_is_alive(pid))
    if not should_reclaim:
        return
    # Re-read the PID immediately before unlinking and reclaim only when the
    # record is byte-identical to the one we judged stale. This closes the
    # TOCTOU window where a peer reclaims the stale lock and re-creates it with
    # its own live PID between our read and our unlink: without the re-check we
    # would delete that peer's live lock, letting a third writer in.
    if _read_pid(target) != pid:
        _log.debug("bucket lockfile stale reclaim aborted; holder changed under reclaim")
        return
    _unlink_lockfile_if_present(target, reason="stale_reclaim")


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
    try:
        paths.bucket_dir.mkdir(parents=True, exist_ok=True)
    except FileExistsError as exc:
        raise BucketValidationError(
            "bucket lock directory path is not a directory",
            context={
                "reason": "bucket_dir_not_directory",
                "surface": _LOCKFILE_VALIDATION_SURFACE,
            },
        ) from exc
    pid = os.getpid()

    deadline = time.monotonic() + max(wait_seconds, 0.0)
    while True:
        _reclaim_if_stale(target)
        if _try_create_lock(target, pid):
            _ATEXIT_REGISTRY.add(target)
            return
        if time.monotonic() >= deadline:
            pid_read = _read_pid(target)
            holding_pid = _holding_pid_for_error(pid_read)
            raise BucketBusyError(bucket_id=paths.bucket_id, holding_pid=holding_pid)
        time.sleep(_poll_interval_seconds())


def release_lock(paths: BucketPaths) -> None:
    """Release the per-bucket lockfile owned by this process.

    Removes the lockfile only when the recorded PID matches this process;
    a foreign lockfile is left alone so a stale-reclaim race cannot delete
    another process's lock.
    """
    target = lock_path(paths)
    pid = _read_pid(target)
    if pid is _PidReadState.MISSING:
        _log.debug("bucket lockfile release skipped missing lockfile")
        _ATEXIT_REGISTRY.discard(target)
        return
    if pid is _PidReadState.INVALID:
        _ATEXIT_REGISTRY.discard(target)
        return
    if pid is _PidReadState.UNREADABLE:
        _log.debug("bucket lockfile release skipped unreadable lockfile")
        return
    if pid != os.getpid():
        return
    _unlink_lockfile_if_present(target, reason="release")
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
                _unlink_lockfile_if_present(target, reason="atexit")
            self._targets.discard(target)


_ATEXIT_REGISTRY = _AtexitRegistry()


__all__ = ["acquire_lock", "lock_path", "release_lock"]
