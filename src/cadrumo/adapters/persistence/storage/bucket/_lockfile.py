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

Every removal goes through :func:`~core.unlink_lockfile`, because a
waiting acquirer that opens the lockfile to read its PID blocks the holder's
unlink on Windows. On the release path that is a wedge rather than a delay --
the record names a live process, so the lock is never reclaimed as stale -- so
release retries to a deadline while a stale reclaim stays single-attempt.
"""

from __future__ import annotations

import atexit
import os
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from .....core import LOCKFILE_UNLINK_RETRY_SECONDS, pid_is_alive, unlink_lockfile
from .....core.config import load_settings as _load_settings
from .....core.external_constants import UTF_8_ENCODING
from .....core.logging import get_logger
from .._storage_path_definitions import BUCKET_LOCK_FILENAME
from ._errors import BucketBusyError, BucketValidationError

if TYPE_CHECKING:
    pass


@runtime_checkable
class BucketLockTarget(Protocol):
    """What the bucket lock actually needs: one directory to place ``.lock`` in.

    The lock reads two fields -- the directory it places ``.lock`` in, and the
    bucket identity its refusals name. Declaring exactly those, rather than
    demanding the whole :class:`BucketPaths` record, is what lets a caller holding a narrowed
    view of a bucket delegate here without first re-widening it back to the
    concrete record -- a round trip that had to be guarded by a runtime identity
    check standing in for a boundary this protocol states directly.

    It is deliberately NOT the pattern for the custody records. Those ports are
    narrower than the substrate needs on purpose: they hide key material the
    application has no business reading, so widening a crypto signature onto one
    would either expose that material or fail late on a field the port omits.
    The lock is the opposite case -- nothing is hidden, because nothing beyond a
    directory is used.
    """

    @property
    def bucket_dir(self) -> Path:
        """The bucket directory whose ``.lock`` sidecar is the lock target."""
        ...

    @property
    def bucket_id(self) -> str:
        """The bucket's identity, carried on every lock refusal's context.

        Declared because the lock genuinely reads it, not for symmetry: a
        busy-or-unlockable refusal names the bucket it could not take, and a
        protocol that omitted it would either fail late here or silently
        degrade the operator's refusal to an unattributed one.
        """
        ...


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


def lock_path(paths: BucketLockTarget) -> Path:
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


def _unlink_lockfile_if_present(target: Path, *, reason: str) -> bool:
    """Remove a lockfile best-effort; report whether it is gone.

    Delegates to :func:`~core.unlink_lockfile` so this lock and the
    auth-acquisition lock handle a waiter's open read handle identically. A
    single attempt is right for every caller except the release itself: losing
    the race on a stale reclaim or an interpreter-exit sweep costs one more
    poll, whereas losing it on release strands the lock.
    """
    removed = unlink_lockfile(target, reason=reason)
    if not removed:
        _log.debug("bucket lockfile unlink deferred; a peer holds the file open reason=%s", reason)
    return removed


def _unlink_released_lockfile(target: Path, paths: BucketLockTarget) -> None:
    """Remove the lockfile this process holds, waiting out a peer's open handle.

    A waiter that opens the lockfile to read the holder PID blocks this unlink
    on Windows. Failing here is a wedge rather than a delay: the record names
    this live process, so the lock is never reclaimed as stale and every later
    acquirer blocks to its own timeout.

    Raises:
        BucketValidationError: When the removal is still refused after
            :data:`~core.LOCKFILE_UNLINK_RETRY_SECONDS`, so the operator is told
            the bucket needs the stale lockfile cleared by hand.
    """
    if unlink_lockfile(target, retry_seconds=LOCKFILE_UNLINK_RETRY_SECONDS, reason="release"):
        return
    raise BucketValidationError(
        "bucket lockfile could not be released; another process holds it open",
        context={
            "reason": "lockfile_release_blocked",
            "surface": _LOCKFILE_VALIDATION_SURFACE,
            "bucket_id": paths.bucket_id,
            "lockfile": str(target),
        },
    )


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

    A ``PermissionError`` reads as held rather than propagating. Under
    cross-process contention Windows refuses this open with
    ``ERROR_ACCESS_DENIED`` while a peer's removal of the same lockfile is in
    flight -- a transient state that clears on its own, so the right response is
    the next poll, not a crash out of ``acquire_lock``. The cost is that a
    genuinely undeletable lockfile is reported as a busy bucket after the wait
    window rather than as a permission fault; the directory's writability is
    already checked by :func:`_ensure_bucket_dir_lockable` before this runs.
    """
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        fd = os.open(target, flags, _LOCKFILE_MODE)
    except (FileExistsError, PermissionError):
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


def _ensure_bucket_dir_lockable(paths: BucketLockTarget) -> None:
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
    paths: BucketLockTarget,
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
    paths: BucketLockTarget,
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


def acquire_lock(paths: BucketLockTarget, *, wait_seconds: float = 0.0) -> None:
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
    paths: BucketLockTarget,
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

    When the removal is refused outright the slot and the atexit registration
    are deliberately NOT cleared: this process really does still hold the lock,
    and leaving it registered means interpreter exit sweeps the file even if the
    operator ignores the refusal.
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
        _unlink_released_lockfile(target, paths)
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


def release_lock(paths: BucketLockTarget) -> None:
    """Release the per-bucket lockfile owned by this process.

    Removes the lockfile only when the recorded PID matches this process;
    a foreign lockfile is left alone so a stale-reclaim race cannot delete
    another process's lock.

    Raises:
        BucketValidationError: When the lockfile is owned by this process but
            a peer's open handle keeps the removal refused past the retry
            window, so the bucket would otherwise be wedged behind a lock
            stamped with a live PID.
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
                paths,
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
