"""Per-bucket ``.lock`` concurrency primitive for the bucket directory model.

Each bucket carries a single PID-stamped lockfile at ``<bucket-dir>/.lock``
created via ``os.open`` with ``O_CREAT | O_EXCL | O_WRONLY``; the
``O_EXCL`` flag is atomic on every POSIX kernel and on Windows NTFS, so a
second-process unlock against a held bucket fails fast with
:class:`adapters.persistence.storage.bucket.BucketBusyError` per
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
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from .....core import pid_is_alive
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


@dataclass(slots=True)
class _LocalLockOwnership:
    """Same-process owner and re-entry depth for one bucket lock."""

    pid: int
    thread_id: int
    depth: int


_LOCAL_LOCKS: dict[Path, _LocalLockOwnership] = {}
_LOCAL_LOCKS_CONDITION = threading.Condition()


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
    return _load_settings().cadrumo_bucket_lock_poll_interval_s


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
    should_reclaim = pid is _PidReadState.INVALID or (isinstance(pid, int) and not pid_is_alive(pid))
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


def _ensure_bucket_dir_lockable(paths: BucketPaths) -> None:
    """Validate the bucket directory exists before locking, or raise.

    A ``not is_dir()`` bucket path always raises: a present-but-non-directory
    path raises the ``bucket_dir_not_directory`` refusal (its ``mkdir`` fails),
    and an absent path raises ``bucket_dir_missing``.
    """
    if paths.bucket_dir.is_dir():
        return
    bucket_dir_present = os.path.lexists(paths.bucket_dir)
    if bucket_dir_present:
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
    raise BucketValidationError(
        "bucket lock requires an existing bucket directory",
        context={
            "reason": "bucket_dir_missing",
            "surface": _LOCKFILE_VALIDATION_SURFACE,
        },
    )


def _acquire_local_slot(
    target: Path,
    ownership_key: Path,
    paths: BucketPaths,
    *,
    pid: int,
    thread_id: int,
    deadline: float,
) -> bool:
    """Claim or re-enter the in-process ownership slot for a bucket lock.

    Returns ``True`` when a fresh slot (depth 0) was created and the caller must
    proceed to the filesystem claim; ``False`` when an existing same-thread lock
    was re-entered (depth incremented) and the caller must return immediately.

    Same-thread re-entry revalidates the on-disk record before honouring the
    in-process slot. The slot is a cache of a filesystem fact, and the two can
    diverge: if a foreign process replaced the lockfile while this thread held
    it, re-entering on the strength of the local record alone would hand the
    caller a lock this process does not hold, silently, with the foreign lock
    still on disk. A definite foreign PID therefore refuses the re-entry.
    """
    while True:
        with _LOCAL_LOCKS_CONDITION:
            ownership = _LOCAL_LOCKS.get(ownership_key)
            if ownership is not None and ownership.pid != pid:
                del _LOCAL_LOCKS[ownership_key]
                ownership = None
                _LOCAL_LOCKS_CONDITION.notify_all()
            if ownership is None:
                _LOCAL_LOCKS[ownership_key] = _LocalLockOwnership(
                    pid=pid,
                    thread_id=thread_id,
                    depth=0,
                )
                return True
            if ownership.thread_id == thread_id:
                if ownership.depth == 0:
                    raise RuntimeError(
                        "bucket lock cannot re-enter while initial acquisition is incomplete",
                    )
                recorded_pid = _read_pid(target)
                if isinstance(recorded_pid, int) and recorded_pid != pid:
                    raise BucketBusyError(
                        bucket_id=paths.bucket_id,
                        holding_pid=recorded_pid,
                    )
                ownership.depth += 1
                return False
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise BucketBusyError(
                    bucket_id=paths.bucket_id,
                    holding_pid=pid,
                )
            _LOCAL_LOCKS_CONDITION.wait(
                timeout=min(_poll_interval_seconds(), remaining),
            )


def _release_incomplete_local_slot(ownership_key: Path, *, pid: int, thread_id: int) -> None:
    """Drop a depth-0 in-process slot owned by this thread after a failed claim."""
    with _LOCAL_LOCKS_CONDITION:
        ownership = _LOCAL_LOCKS.get(ownership_key)
        if ownership is not None and ownership.pid == pid and ownership.thread_id == thread_id and ownership.depth == 0:
            del _LOCAL_LOCKS[ownership_key]
            _LOCAL_LOCKS_CONDITION.notify_all()


def _claim_lockfile(
    target: Path,
    ownership_key: Path,
    paths: BucketPaths,
    *,
    pid: int,
    thread_id: int,
    deadline: float,
) -> None:
    """Create the on-disk lockfile, reclaiming stale holders and polling to deadline.

    On success promotes the in-process slot to depth 1 and registers atexit
    cleanup; on any failure rolls back a freshly-created (depth 0) slot.
    """
    try:
        while True:
            _reclaim_if_stale(target)
            try:
                created = _try_create_lock(target, pid)
            except FileNotFoundError as exc:
                raise BucketValidationError(
                    "bucket directory disappeared during lock acquisition",
                    context={
                        "reason": "bucket_dir_disappeared",
                        "surface": _LOCKFILE_VALIDATION_SURFACE,
                    },
                ) from exc
            if created:
                with _LOCAL_LOCKS_CONDITION:
                    ownership = _LOCAL_LOCKS[ownership_key]
                    ownership.depth = 1
                _ATEXIT_REGISTRY.add(ownership_key)
                return
            if time.monotonic() >= deadline:
                pid_read = _read_pid(target)
                holding_pid = _holding_pid_for_error(pid_read)
                raise BucketBusyError(
                    bucket_id=paths.bucket_id,
                    holding_pid=holding_pid,
                )
            time.sleep(_poll_interval_seconds())
    except BaseException:
        _release_incomplete_local_slot(ownership_key, pid=pid, thread_id=thread_id)
        raise


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
    ownership_key = target.expanduser().resolve(strict=False)
    _ensure_bucket_dir_lockable(paths)
    pid = os.getpid()
    deadline = time.monotonic() + max(wait_seconds, 0.0)
    thread_id = threading.get_ident()

    if not _acquire_local_slot(target, ownership_key, paths, pid=pid, thread_id=thread_id, deadline=deadline):
        return
    _claim_lockfile(target, ownership_key, paths, pid=pid, thread_id=thread_id, deadline=deadline)


def _release_owned_slot(
    target: Path,
    ownership_key: Path,
    ownership: _LocalLockOwnership,
    *,
    current_pid: int,
    thread_id: int,
) -> None:
    """Release a same-process local slot: honour re-entry depth, then unlink.

    A slot owned by another thread, or a re-entered slot (depth > 1), is left in
    place (only its depth is decremented). At depth 1 the on-disk lockfile is
    unlinked only when its recorded PID matches, then the slot and its atexit
    registration are cleared.

    A lockfile that now records a FOREIGN pid is left on disk -- deleting it
    would drop another process's lock -- but the local slot is still cleared.
    Keeping it would leave this process holding an ownership record for a lock
    it demonstrably no longer holds, which a later same-thread acquire would
    read as a live re-entry.
    """
    if ownership.thread_id != thread_id:
        return
    if ownership.depth > 1:
        ownership.depth -= 1
        return
    pid = _read_pid(target)
    if pid is _PidReadState.UNREADABLE:
        _log.debug("bucket lockfile release skipped unreadable lockfile")
        return
    if pid == current_pid:
        _unlink_lockfile_if_present(target, reason="release")
    elif pid is not _PidReadState.MISSING:
        _log.debug(
            "bucket lockfile release found a foreign holder; leaving the lockfile and clearing local ownership",
        )
    del _LOCAL_LOCKS[ownership_key]
    _ATEXIT_REGISTRY.discard(ownership_key)
    _LOCAL_LOCKS_CONDITION.notify_all()


def _discard_orphan_lockfile_registration(target: Path, ownership_key: Path) -> None:
    """Sync the atexit registry when no in-process slot owns the lockfile."""
    pid = _read_pid(target)
    if pid is _PidReadState.MISSING:
        _log.debug("bucket lockfile release skipped missing lockfile")
        _ATEXIT_REGISTRY.discard(ownership_key)
    elif pid is _PidReadState.INVALID:
        _ATEXIT_REGISTRY.discard(ownership_key)


def release_lock(paths: BucketPaths) -> None:
    """Release the per-bucket lockfile owned by this process.

    Removes the lockfile only when the recorded PID matches this process;
    a foreign lockfile is left alone so a stale-reclaim race cannot delete
    another process's lock.
    """
    target = lock_path(paths)
    ownership_key = target.expanduser().resolve(strict=False)
    current_pid = os.getpid()
    thread_id = threading.get_ident()
    with _LOCAL_LOCKS_CONDITION:
        ownership = _LOCAL_LOCKS.get(ownership_key)
        if ownership is not None and ownership.pid != current_pid:
            del _LOCAL_LOCKS[ownership_key]
            ownership = None
            _LOCAL_LOCKS_CONDITION.notify_all()
        if ownership is not None:
            _release_owned_slot(
                target,
                ownership_key,
                ownership,
                current_pid=current_pid,
                thread_id=thread_id,
            )
            return

    _discard_orphan_lockfile_registration(target, ownership_key)


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
