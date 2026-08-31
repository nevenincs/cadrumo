"""Identity-anchored local filesystem substrate for profile custody."""

from __future__ import annotations

import os
import stat
import sys
import threading
import time
from collections.abc import Generator
from contextlib import ExitStack, contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal, cast, overload
from uuid import uuid4

from ._capsule_filesystem import (
    renameat2_noreplace as _renameat2_noreplace,
)
from ._capsule_filesystem import (
    windows_mark_handle_for_deletion as _windows_mark_handle_for_deletion,
)
from .errors import ProfileCustodyRecordError
from .filesystem_primitives import ProfileCustodyPasswordReadOperation, ensure_profile_custody_local_directory
from .filesystem_primitives import anchor_directory as _anchor_directory
from .filesystem_primitives import posix_directory_fd as _posix_directory_fd
from .filesystem_primitives import windows_create_file_api as _windows_create_file_api
from .filesystem_primitives import windows_file_information_type as _windows_file_information_type

PROFILE_CUSTODY_DATA_MAX_ENTRIES: Final = 1024
PROFILE_CUSTODY_DATA_FILE_MAX_BYTES: Final = 64 * 1024 * 1024
_LOCAL_RECORD_REPLACE_BUDGET_SECONDS: Final = 1.0
"""How long a local-record replacement waits out readers holding the leaf open.

Stated as a deadline rather than an attempt count: what has to be outlasted is a
span of contention, and an attempt count silently shortens the wait whenever the
poll interval changes. A reader's handle lives microseconds; a denying ACL never
clears, and Windows reports both as ``ERROR_ACCESS_DENIED``, so the budget is
the only thing that separates them.

Sized by what losing costs. This path carries the login handover witness, and an
exhausted budget is not a delay -- it refuses the login. Under eight concurrent
readers the previous eighty-millisecond budget exhausted on roughly one write in
ten, so the wait is longer than a reader needs and far shorter than a failure
costs the operator.
"""

_LOCAL_RECORD_REPLACE_POLL_SECONDS: Final = 0.01


@dataclass(slots=True)
class _ProfileCustodyRootLockOwnership:
    """One thread-local re-entrant ownership entry for a custody storage root."""

    pid: int
    thread_id: int
    depth: int


_PROFILE_CUSTODY_ROOT_LOCKS = threading.local()


@contextmanager
def profile_custody_local_lock(path: Path, *, timeout_seconds: float = 30.0) -> Generator[None]:
    """Hold a no-follow, parent-anchored cross-process custody lock.

    On POSIX the descriptor is opened relative to a pinned parent and locked
    with ``flock``.  Windows opens the exact no-reparse leaf with no sharing;
    the kernel releases that exclusion when a process dies.  Neither platform
    relies on a stale lock-file convention.
    """
    if timeout_seconds <= 0:
        raise ProfileCustodyRecordError("local custody lock timeout must be positive")
    if os.name != "nt":
        with _profile_custody_posix_lock(path, timeout_seconds=timeout_seconds):
            yield
        return

    with _profile_custody_windows_lock(path, timeout_seconds=timeout_seconds):
        yield


@contextmanager
def profile_custody_root_lock(root: Path, *, timeout_seconds: float = 30.0) -> Generator[None]:
    """Hold the single re-entrant root lock for every current custody pointer mutation.

    This is deliberately a separate primitive from leaf locks: both the
    application active-pointer transaction and custody compare-and-swap use
    this exact root lock identity.  Re-entry is limited to the same process,
    thread, and effective root; sibling processes retain kernel-enforced
    exclusion through :func:`profile_custody_local_lock`.
    """
    current_pid = os.getpid()
    current_thread_id = threading.get_ident()
    configured_owners = getattr(_PROFILE_CUSTODY_ROOT_LOCKS, "owners", None)
    if configured_owners is None:
        owners: dict[Path, _ProfileCustodyRootLockOwnership] = {}
        _PROFILE_CUSTODY_ROOT_LOCKS.owners = owners
    else:
        owners = cast(dict[Path, _ProfileCustodyRootLockOwnership], configured_owners)
    ownership = owners.get(root)
    if ownership is not None:
        if ownership.pid != current_pid or ownership.thread_id != current_thread_id:
            raise ProfileCustodyRecordError("profile custody root lock ownership is not live in this thread")
        ownership.depth += 1
        try:
            yield
        finally:
            ownership.depth -= 1
        return

    # Pointer creation is a normal first-profile operation.  Anchor the one
    # storage-root component before opening its lock leaf so first use neither
    # follows a substituted root nor requires an unrelated bootstrap write.
    ensure_profile_custody_local_directory(root)
    with profile_custody_local_lock(root / ".profile-custody-root.lock", timeout_seconds=timeout_seconds):
        owners[root] = _ProfileCustodyRootLockOwnership(
            pid=current_pid,
            thread_id=current_thread_id,
            depth=1,
        )
        try:
            yield
        finally:
            ownership = owners.pop(root)
            if ownership.pid != current_pid or ownership.thread_id != current_thread_id or ownership.depth != 1:
                raise ProfileCustodyRecordError("profile custody root lock ownership changed before release")


@contextmanager
def _profile_custody_posix_lock(path: Path, *, timeout_seconds: float) -> Generator[None]:
    import errno
    import fcntl

    flock = getattr(fcntl, "flock", None)
    lock_ex = getattr(fcntl, "LOCK_EX", None)
    lock_nb = getattr(fcntl, "LOCK_NB", None)
    lock_un = getattr(fcntl, "LOCK_UN", None)
    if (
        not callable(flock)
        or not isinstance(lock_ex, int)
        or not isinstance(lock_nb, int)
        or not isinstance(lock_un, int)
    ):
        raise ProfileCustodyRecordError("local custody flock support is unavailable")

    with _posix_directory_fd(path.parent) as parent_fd:
        try:
            descriptor = os.open(
                path.name,
                os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
                0o600,
                dir_fd=parent_fd,
            )
        except OSError as exc:
            raise ProfileCustodyRecordError("local custody lock cannot be no-follow opened") from exc
        try:
            deadline = time.monotonic() + timeout_seconds
            while True:
                try:
                    flock(descriptor, lock_ex | lock_nb)
                    break
                except OSError as exc:
                    if exc.errno not in {errno.EACCES, errno.EAGAIN} or time.monotonic() >= deadline:
                        raise ProfileCustodyRecordError("local custody lock cannot be exclusively opened") from exc
                    time.sleep(0.025)
            yield
        finally:
            flock(descriptor, lock_un)
            os.close(descriptor)


@contextmanager
def _profile_custody_windows_lock(path: Path, *, timeout_seconds: float) -> Generator[None]:
    ctypes, wintypes, kernel32, create_file = _windows_create_file_api()
    file_information_type = _windows_file_information_type()
    invalid_handle = wintypes.HANDLE(-1).value
    deadline = time.monotonic() + timeout_seconds
    with ExitStack() as anchors:
        _anchor_directory(anchors, path.parent, final_access=0x80000000)
        while True:
            handle = create_file(
                str(path),
                0x80000000 | 0x40000000,
                0,
                None,
                4,  # OPEN_ALWAYS: one kernel-owned lock object, never replace it.
                0x00200000,  # FILE_FLAG_OPEN_REPARSE_POINT
                None,
            )
            if handle != invalid_handle:
                break
            error = ctypes.get_last_error()
            if error not in {32, 33} or time.monotonic() >= deadline:  # sharing/lock violation
                raise ProfileCustodyRecordError("local custody lock cannot be exclusively opened")
            time.sleep(0.025)
        try:
            info = file_information_type()
            if not kernel32.GetFileInformationByHandle(handle, ctypes.byref(info)):
                raise ProfileCustodyRecordError("local custody lock leaf cannot be identity-verified")
            if info.dwFileAttributes & 0x400 or info.dwFileAttributes & 0x10:
                raise ProfileCustodyRecordError("local custody lock leaf is a reparse point or non-file")
            yield
        finally:
            kernel32.CloseHandle(handle)


@overload
def _read_regular_file(
    path: Path,
    *,
    maximum_bytes: int,
    trace: list[ProfileCustodyPasswordReadOperation] | None = None,
    missing_ok: Literal[False] = False,
) -> bytes: ...


@overload
def _read_regular_file(
    path: Path,
    *,
    maximum_bytes: int,
    trace: list[ProfileCustodyPasswordReadOperation] | None = None,
    missing_ok: Literal[True],
) -> bytes | None: ...


def _read_regular_file(
    path: Path,
    *,
    maximum_bytes: int,
    trace: list[ProfileCustodyPasswordReadOperation] | None = None,
    missing_ok: bool = False,
) -> bytes | None:
    _record_read_operation(trace, "open", path)
    if os.name != "nt":
        with _posix_directory_fd(path.parent) as parent_fd:
            return _read_regular_file_open(
                path,
                maximum_bytes=maximum_bytes,
                trace=trace,
                parent_fd=parent_fd,
                missing_ok=missing_ok,
            )
    with ExitStack() as anchors:
        _anchor_directory(anchors, path.parent, final_access=0x80000000)
        with _windows_regular_file_anchor(path, missing_ok=missing_ok) as present:
            if not present:
                return None
            return _read_regular_file_open(path, maximum_bytes=maximum_bytes, trace=trace)


def read_profile_custody_local_record(path: Path, *, maximum_bytes: int) -> bytes:
    """Read an auxiliary local custody record through the same anchored no-follow primitive."""
    return _read_regular_file(path, maximum_bytes=maximum_bytes)


def read_optional_profile_custody_local_record(path: Path, *, maximum_bytes: int) -> bytes | None:
    """Read a local record or prove its absence through the anchored primitive.

    Callers that need an absent-vs-corrupt distinction must not first inspect a
    pathname and then reopen it.  This keeps that distinction inside the same
    no-follow, identity-anchored operation as the bounded read.
    """
    return _read_regular_file(path, maximum_bytes=maximum_bytes, missing_ok=True)


def write_profile_custody_local_record(path: Path, payload: bytes, *, publish_once: bool) -> None:
    """Durably write an auxiliary local custody record under pinned ancestry.

    ``publish_once`` uses a no-replace publication; mutable journals are first
    read through the paired no-follow primitive and then atomically replaced.
    """
    if os.name != "nt":
        with _posix_directory_fd(path.parent) as parent_fd:
            temporary_name = f".{path.name}.{os.getpid()}.{uuid4().hex}.tmp"
            descriptor = _posix_open_exclusive_file(parent_fd, temporary_name)
            try:
                _write_descriptor_fsynced(descriptor, payload)
                if publish_once:
                    os.link(temporary_name, path.name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
                    os.unlink(temporary_name, dir_fd=parent_fd)
                else:
                    os.replace(temporary_name, path.name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
                os.fsync(parent_fd)
            except OSError as exc:
                with suppress(FileNotFoundError):
                    os.unlink(temporary_name, dir_fd=parent_fd)
                raise ProfileCustodyRecordError("local custody record cannot be atomically written") from exc
            finally:
                os.close(descriptor)
        return
    with ExitStack() as anchors:
        _anchor_directory(anchors, path.parent, final_access=0x80000000)
        if publish_once:
            try:
                descriptor = os.open(
                    path,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0),
                    0o600,
                )
            except FileExistsError as exc:
                raise ProfileCustodyRecordError("local custody record destination already exists") from exc
            except OSError as exc:
                raise ProfileCustodyRecordError("local custody record cannot be exclusively created") from exc
            try:
                _write_descriptor_fsynced(descriptor, payload)
            finally:
                os.close(descriptor)
            return
        from .....core.atomic_write import atomic_write_hardened_bytes

        deadline = time.monotonic() + _LOCAL_RECORD_REPLACE_BUDGET_SECONDS
        while True:
            try:
                atomic_write_hardened_bytes(path, payload, mode=0o600)
            except PermissionError as exc:
                if time.monotonic() >= deadline:
                    raise ProfileCustodyRecordError("local custody record cannot be atomically written") from exc
                time.sleep(_LOCAL_RECORD_REPLACE_POLL_SECONDS)
            except OSError as exc:
                raise ProfileCustodyRecordError("local custody record cannot be atomically written") from exc
            else:
                return


def compare_and_replace_profile_custody_local_record(
    path: Path,
    *,
    expected: bytes | None,
    replacement: bytes,
    maximum_bytes: int,
) -> None:
    """Atomically replace ``path`` only when its exact anchored bytes match.

    The comparison and mutation belong to one custody-owner operation.  A
    sibling that substitutes a different regular, canonical record after the
    comparison is detected at the exchange boundary; its bytes are restored
    before this function refuses.  ``expected=None`` is the one no-replace
    initial publication case.
    """
    if maximum_bytes < 1 or len(replacement) > maximum_bytes:
        raise ProfileCustodyRecordError("local custody record compare-and-replace payload exceeds its byte limit")
    if expected is None:
        write_profile_custody_local_record(path, replacement, publish_once=True)
        return
    if len(expected) < 1 or len(expected) > maximum_bytes:
        raise ProfileCustodyRecordError("local custody record compare-and-replace expectation is out of bounds")
    if os.name != "nt":
        _posix_compare_and_replace_local_record(
            path,
            expected=expected,
            replacement=replacement,
            maximum_bytes=maximum_bytes,
        )
        return
    _windows_compare_and_replace_local_record(
        path,
        expected=expected,
        replacement=replacement,
        maximum_bytes=maximum_bytes,
    )


def compare_and_replace_same_or_predecessor_profile_custody_local_record(
    path: Path,
    *,
    current: bytes,
    predecessor: bytes | None,
    maximum_bytes: int,
) -> None:
    """Idempotently publish ``current`` from only its exact predecessor.

    A durable retry whose requested bytes are already current is successful and
    performs no mutation.  Otherwise, one anchored compare-and-replace accepts
    only the exact predecessor (or a proven-absent first receipt); every other
    leaf is preserved and refused.
    """
    if len(current) < 1 or len(current) > maximum_bytes:
        raise ProfileCustodyRecordError("local custody record idempotent CAS payload is out of bounds")
    if predecessor is not None and (len(predecessor) < 1 or len(predecessor) > maximum_bytes):
        raise ProfileCustodyRecordError("local custody record idempotent CAS predecessor is out of bounds")
    if os.name != "nt":
        _posix_compare_and_replace_same_or_predecessor_local_record(
            path,
            current=current,
            predecessor=predecessor,
            maximum_bytes=maximum_bytes,
        )
        return
    _windows_compare_and_replace_same_or_predecessor_local_record(
        path,
        current=current,
        predecessor=predecessor,
        maximum_bytes=maximum_bytes,
    )


def _posix_compare_and_replace_same_or_predecessor_local_record(
    path: Path,
    *,
    current: bytes,
    predecessor: bytes | None,
    maximum_bytes: int,
) -> None:
    """Perform the idempotent receipt transition below one pinned POSIX parent."""
    if not sys.platform.startswith("linux"):
        raise ProfileCustodyRecordError(
            "atomic local custody record idempotent compare-and-replace is unavailable on this POSIX host"
        )
    with _posix_directory_fd(path.parent) as parent_fd:
        observed = _read_optional_posix_local_record(parent_fd, path.name, maximum_bytes=maximum_bytes)
        if observed == current:
            _posix_clear_idempotent_backup_if_predecessor(
                parent_fd,
                path,
                predecessor=predecessor,
                maximum_bytes=maximum_bytes,
            )
            return
        if predecessor is None:
            if observed is not None:
                raise ProfileCustodyRecordError("local custody record idempotent CAS differs from first receipt")
            _posix_publish_current_or_confirm_existing(
                parent_fd,
                path,
                current=current,
                maximum_bytes=maximum_bytes,
            )
            return
        if observed != predecessor:
            raise ProfileCustodyRecordError("local custody record idempotent CAS predecessor differs")
        stage_name = _local_record_idempotent_backup_name(path)
        descriptor = _posix_open_exclusive_file(parent_fd, stage_name)
        try:
            _write_descriptor_fsynced(descriptor, current)
        finally:
            os.close(descriptor)
        exchanged = False
        try:
            _renameat2_exchange(parent_fd=parent_fd, first_name=path.name, second_name=stage_name)
            exchanged = True
            displaced = _read_regular_file_fd(
                parent_fd,
                stage_name,
                display_path=path.with_name(stage_name),
                maximum_bytes=maximum_bytes,
                trace=None,
            )
            if displaced == predecessor:
                # The exact predecessor remains as the deterministic recovery
                # sidecar until a same-receipt retry clears it.  A process can
                # therefore distinguish publication from cleanup without
                # making a new target mutation or trusting an arbitrary file.
                os.fsync(parent_fd)
                return
            _renameat2_exchange(parent_fd=parent_fd, first_name=path.name, second_name=stage_name)
            exchanged = False
            if displaced == current:
                return
            raise ProfileCustodyRecordError("local custody record changed before idempotent CAS mutation")
        except OSError as exc:
            raise ProfileCustodyRecordError("local custody record cannot be idempotently compare-and-replaced") from exc
        finally:
            if not exchanged:
                with suppress(FileNotFoundError):
                    os.unlink(stage_name, dir_fd=parent_fd)


def _posix_clear_idempotent_backup_if_predecessor(
    parent_fd: int,
    path: Path,
    *,
    predecessor: bytes | None,
    maximum_bytes: int,
) -> None:
    """Clear only the exact predecessor sidecar left by a failed receipt cleanup."""
    backup_name = _local_record_idempotent_backup_name(path)
    observed_backup = _read_optional_posix_local_record(parent_fd, backup_name, maximum_bytes=maximum_bytes)
    if observed_backup is None:
        return
    if predecessor is None or observed_backup != predecessor:
        raise ProfileCustodyRecordError("local custody record idempotent CAS backup differs")
    _posix_compare_and_clear_local_record(
        path.with_name(backup_name),
        expected=predecessor,
        maximum_bytes=maximum_bytes,
    )


def _posix_publish_current_or_confirm_existing(
    parent_fd: int,
    path: Path,
    *,
    current: bytes,
    maximum_bytes: int,
) -> None:
    """No-replace publish the first receipt, accepting only a racing same receipt."""
    stage_name = _local_record_stage_name(path)
    descriptor = _posix_open_exclusive_file(parent_fd, stage_name)
    try:
        _write_descriptor_fsynced(descriptor, current)
    finally:
        os.close(descriptor)
    try:
        os.link(stage_name, path.name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
    except FileExistsError:
        observed = _read_optional_posix_local_record(parent_fd, path.name, maximum_bytes=maximum_bytes)
        if observed != current:
            raise ProfileCustodyRecordError("local custody record idempotent first receipt now differs") from None
    except OSError as exc:
        raise ProfileCustodyRecordError("local custody record cannot publish its first idempotent receipt") from exc
    finally:
        with suppress(FileNotFoundError):
            os.unlink(stage_name, dir_fd=parent_fd)
    os.fsync(parent_fd)


def _read_optional_posix_local_record(parent_fd: int, name: str, *, maximum_bytes: int) -> bytes | None:
    return _read_regular_file_open(
        Path(name),
        maximum_bytes=maximum_bytes,
        trace=None,
        parent_fd=parent_fd,
        missing_ok=True,
    )


def _windows_compare_and_replace_same_or_predecessor_local_record(
    path: Path,
    *,
    current: bytes,
    predecessor: bytes | None,
    maximum_bytes: int,
) -> None:
    """Use one ReplaceFileW transition, restoring a racing same receipt unchanged."""
    with ExitStack() as anchors:
        _anchor_directory(anchors, path.parent, final_access=0x80000000)
        observed = read_optional_profile_custody_local_record(path, maximum_bytes=maximum_bytes)
        backup = path.with_name(_local_record_idempotent_backup_name(path))
        if observed == current:
            _windows_clear_idempotent_backup_if_predecessor(
                backup,
                predecessor=predecessor,
                maximum_bytes=maximum_bytes,
            )
            return
        if predecessor is None:
            if observed is not None:
                raise ProfileCustodyRecordError("local custody record idempotent CAS differs from first receipt")
            try:
                write_profile_custody_local_record(path, current, publish_once=True)
            except ProfileCustodyRecordError:
                if read_optional_profile_custody_local_record(path, maximum_bytes=maximum_bytes) == current:
                    return
                raise
            return
        if observed != predecessor:
            raise ProfileCustodyRecordError("local custody record idempotent CAS predecessor differs")
        stage = path.with_name(_local_record_stage_name(path))
        _write_windows_local_stage(stage, current)
        try:
            _windows_replace_file(target=path, replacement=stage, backup=backup)
            displaced = read_profile_custody_local_record(backup, maximum_bytes=maximum_bytes)
            if displaced == predecessor:
                # Retain the verified predecessor until a same-receipt retry
                # clears it.  This keeps post-publication cleanup recoverable
                # instead of turning a cleanup failure into an ambiguous
                # target rewrite.
                return
            _windows_replace_file(target=path, replacement=backup, backup=stage)
            if displaced == current:
                clear_profile_custody_local_record(stage)
                return
            raise ProfileCustodyRecordError("local custody record changed before idempotent CAS mutation")
        except BaseException:
            with suppress(FileNotFoundError):
                clear_profile_custody_local_record(stage)
            raise


def _windows_clear_idempotent_backup_if_predecessor(
    backup: Path,
    *,
    predecessor: bytes | None,
    maximum_bytes: int,
) -> None:
    """Retire only the deterministic backup left by this exact receipt.

    A failed post-publication cleanup leaves the target already current and
    the predecessor in this sidecar.  A retry must neither replace the current
    target nor discard an unrelated sibling, so it removes the sidecar only
    through the anchored compare-and-clear operation after proving the exact
    predecessor bytes.
    """
    observed_backup = read_optional_profile_custody_local_record(backup, maximum_bytes=maximum_bytes)
    if observed_backup is None:
        return
    if predecessor is None or observed_backup != predecessor:
        raise ProfileCustodyRecordError("local custody record idempotent CAS backup differs")
    compare_and_clear_profile_custody_local_record(
        backup,
        expected=predecessor,
        maximum_bytes=maximum_bytes,
    )


def compare_and_clear_profile_custody_local_record(
    path: Path,
    *,
    expected: bytes,
    maximum_bytes: int,
) -> None:
    """Remove ``path`` only when its exact anchored bytes still match.

    Unlike a read followed by ``unlink``, this keeps the verified leaf pinned
    through the delete decision and refuses without deleting a substituted
    canonical record.
    """
    if len(expected) < 1 or len(expected) > maximum_bytes:
        raise ProfileCustodyRecordError("local custody record compare-and-clear expectation is out of bounds")
    if os.name != "nt":
        _posix_compare_and_clear_local_record(path, expected=expected, maximum_bytes=maximum_bytes)
        return
    _windows_compare_and_clear_local_record(path, expected=expected, maximum_bytes=maximum_bytes)


def _posix_compare_and_replace_local_record(
    path: Path,
    *,
    expected: bytes,
    replacement: bytes,
    maximum_bytes: int,
) -> None:
    """CAS through Linux ``renameat2(EXCHANGE)`` below one pinned directory."""
    if not sys.platform.startswith("linux"):
        raise ProfileCustodyRecordError(
            "atomic local custody record compare-and-replace is unavailable on this POSIX host"
        )
    with _posix_directory_fd(path.parent) as parent_fd:
        _compare_posix_local_record(parent_fd, path.name, expected=expected, maximum_bytes=maximum_bytes)
        stage_name = _local_record_stage_name(path)
        descriptor = _posix_open_exclusive_file(parent_fd, stage_name)
        try:
            _write_descriptor_fsynced(descriptor, replacement)
        finally:
            os.close(descriptor)
        exchanged = False
        try:
            _renameat2_exchange(parent_fd=parent_fd, first_name=path.name, second_name=stage_name)
            exchanged = True
            displaced = _read_regular_file_fd(
                parent_fd,
                stage_name,
                display_path=path.with_name(stage_name),
                maximum_bytes=maximum_bytes,
                trace=None,
            )
            if displaced != expected:
                _renameat2_exchange(parent_fd=parent_fd, first_name=path.name, second_name=stage_name)
                exchanged = False
                raise ProfileCustodyRecordError("local custody record changed before compare-and-replace mutation")
            os.unlink(stage_name, dir_fd=parent_fd)
            exchanged = False
            os.fsync(parent_fd)
        except OSError as exc:
            raise ProfileCustodyRecordError("local custody record cannot be compare-and-replaced") from exc
        finally:
            if not exchanged:
                with suppress(FileNotFoundError):
                    os.unlink(stage_name, dir_fd=parent_fd)


def _posix_compare_and_clear_local_record(path: Path, *, expected: bytes, maximum_bytes: int) -> None:
    """Move only the exact expected leaf aside, then delete that verified inode."""
    if not sys.platform.startswith("linux"):
        raise ProfileCustodyRecordError(
            "atomic local custody record compare-and-clear is unavailable on this POSIX host"
        )
    with _posix_directory_fd(path.parent) as parent_fd:
        _compare_posix_local_record(parent_fd, path.name, expected=expected, maximum_bytes=maximum_bytes)
        stage_name = _local_record_stage_name(path)
        try:
            _renameat2_noreplace(
                source_fd=parent_fd,
                source_name=path.name,
                destination_fd=parent_fd,
                destination_name=stage_name,
            )
            displaced = _read_regular_file_fd(
                parent_fd,
                stage_name,
                display_path=path.with_name(stage_name),
                maximum_bytes=maximum_bytes,
                trace=None,
            )
            if displaced != expected:
                _renameat2_noreplace(
                    source_fd=parent_fd,
                    source_name=stage_name,
                    destination_fd=parent_fd,
                    destination_name=path.name,
                )
                raise ProfileCustodyRecordError("local custody record changed before compare-and-clear mutation")
            os.unlink(stage_name, dir_fd=parent_fd)
            os.fsync(parent_fd)
        except OSError as exc:
            raise ProfileCustodyRecordError("local custody record cannot be compare-and-cleared") from exc


def _compare_posix_local_record(parent_fd: int, name: str, *, expected: bytes, maximum_bytes: int) -> None:
    """Read the no-follow leaf through its descriptor before a CAS mutation."""
    actual = _read_regular_file_fd(
        parent_fd,
        name,
        display_path=Path(name),
        maximum_bytes=maximum_bytes,
        trace=None,
    )
    if actual != expected:
        raise ProfileCustodyRecordError("local custody record compare-and-swap expectation differs")


def _windows_compare_and_replace_local_record(
    path: Path,
    *,
    expected: bytes,
    replacement: bytes,
    maximum_bytes: int,
) -> None:
    """CAS with ``ReplaceFileW`` and a verified backup of the displaced leaf."""
    with ExitStack() as anchors:
        _anchor_directory(anchors, path.parent, final_access=0x80000000)
        if read_profile_custody_local_record(path, maximum_bytes=maximum_bytes) != expected:
            raise ProfileCustodyRecordError("local custody record compare-and-swap expectation differs")
        stage = path.with_name(_local_record_stage_name(path))
        backup = path.with_name(_local_record_backup_name(path))
        _write_windows_local_stage(stage, replacement)
        try:
            _windows_replace_file(target=path, replacement=stage, backup=backup)
            displaced = read_profile_custody_local_record(backup, maximum_bytes=maximum_bytes)
            if displaced != expected:
                _windows_replace_file(target=path, replacement=backup, backup=stage)
                raise ProfileCustodyRecordError("local custody record changed before compare-and-replace mutation")
            clear_profile_custody_local_record(backup)
        except BaseException:
            with suppress(FileNotFoundError):
                clear_profile_custody_local_record(stage)
            raise


def _windows_compare_and_clear_local_record(path: Path, *, expected: bytes, maximum_bytes: int) -> None:
    """Read and delete through one no-delete-shared Windows leaf handle."""
    with ExitStack() as anchors:
        _anchor_directory(anchors, path.parent, final_access=0x80000000)
        ctypes, wintypes, kernel32, create_file = _windows_create_file_api()
        file_information_type = _windows_file_information_type()
        handle = create_file(
            str(path),
            0x80000000 | 0x00010000,  # GENERIC_READ | DELETE
            0x00000001,  # FILE_SHARE_READ only: pin contents and leaf name.
            None,
            3,  # OPEN_EXISTING
            0x00200000,  # FILE_FLAG_OPEN_REPARSE_POINT
            None,
        )
        if handle == wintypes.HANDLE(-1).value:
            raise ProfileCustodyRecordError("local custody record cannot be no-follow opened for compare-and-clear")
        try:
            info = file_information_type()
            if not kernel32.GetFileInformationByHandle(handle, ctypes.byref(info)):
                raise ProfileCustodyRecordError(
                    "local custody record identity cannot be verified before compare-and-clear"
                )
            if info.dwFileAttributes & 0x400 or info.dwFileAttributes & 0x10:
                raise ProfileCustodyRecordError("local custody record must not be a reparse point or directory")
            payload = _windows_read_handle_bounded(handle=int(handle), info=info, maximum_bytes=maximum_bytes)
            if payload != expected:
                raise ProfileCustodyRecordError("local custody record compare-and-swap expectation differs")
            _windows_mark_handle_for_deletion(int(handle))
        finally:
            kernel32.CloseHandle(handle)


def _local_record_stage_name(path: Path) -> str:
    return f".{path.name}.cas-stage.{os.getpid()}.{uuid4().hex}.tmp"


def _local_record_backup_name(path: Path) -> str:
    return f".{path.name}.cas-backup.{os.getpid()}.{uuid4().hex}.tmp"


def _local_record_idempotent_backup_name(path: Path) -> str:
    """Return the sole recoverable backup name for one idempotent receipt."""
    return f".{path.name}.cas-idempotent-backup"


def _write_windows_local_stage(path: Path, payload: bytes) -> None:
    try:
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0),
            0o600,
        )
    except OSError as exc:
        raise ProfileCustodyRecordError(
            "local custody record cannot be exclusively staged for compare-and-replace"
        ) from exc
    try:
        _write_descriptor_fsynced(descriptor, payload)
    finally:
        os.close(descriptor)


def _windows_replace_file(*, target: Path, replacement: Path, backup: Path) -> None:
    import ctypes
    from ctypes import wintypes

    replace_file = ctypes.WinDLL("kernel32", use_last_error=True).ReplaceFileW
    replace_file.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]
    replace_file.restype = wintypes.BOOL
    if replace_file(str(target), str(replacement), str(backup), 0x00000001, None, None):
        return
    error = ctypes.get_last_error()
    raise ProfileCustodyRecordError("local custody record cannot be atomically compare-and-replaced") from OSError(
        error,
        "ReplaceFileW",
    )


# info is the ctypes.Structure windows_file_information_type() builds as a
# function-local class returning type[Any]; ctypes itself types its field
# ADAPTER-INTERNAL-ALIAS-RATIONALE-WIN32-FILE-INFO: access as Any, so no concrete annotation is nameable here.
def _windows_read_handle_bounded(*, handle: int, info: Any, maximum_bytes: int) -> bytes:
    import ctypes
    from ctypes import wintypes

    size = (int(info.nFileSizeHigh) << 32) | int(info.nFileSizeLow)
    if size < 1 or size > maximum_bytes:
        raise ProfileCustodyRecordError("local custody record is not a bounded regular file")
    buffer = ctypes.create_string_buffer(size)
    read_count = wintypes.DWORD()
    read_file = ctypes.WinDLL("kernel32", use_last_error=True).ReadFile
    read_file.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p]
    read_file.restype = wintypes.BOOL
    if not read_file(wintypes.HANDLE(handle), buffer, size, ctypes.byref(read_count), None):
        raise ProfileCustodyRecordError("local custody record cannot be read for compare-and-clear")
    if read_count.value != size:
        raise ProfileCustodyRecordError("local custody record changed during compare-and-clear read")
    return bytes(buffer.raw)


def clear_profile_custody_local_record(path: Path) -> None:
    """Remove one local record through an anchored verified leaf handle.

    The operation opens and verifies the leaf before any unlink/delete action;
    it never performs a ``lexists``/``unlink`` path sequence.  The caller's
    custody root lock serializes cooperating writers, while the pinned parent
    and non-delete-shared Windows handle prevent ancestry or leaf substitution
    during this operation.
    """
    if os.name != "nt":
        with _posix_directory_fd(path.parent) as parent_fd:
            try:
                descriptor = os.open(
                    path.name,
                    os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                    dir_fd=parent_fd,
                )
            except FileNotFoundError:
                return
            except OSError as exc:
                raise ProfileCustodyRecordError("local custody record cannot be no-follow opened for clear") from exc
            try:
                metadata = os.fstat(descriptor)
                if not stat.S_ISREG(metadata.st_mode):
                    raise ProfileCustodyRecordError("local custody record is not a regular file")
                current = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
                if (current.st_dev, current.st_ino) != (metadata.st_dev, metadata.st_ino):
                    raise ProfileCustodyRecordError("local custody record identity changed before clear")
                os.unlink(path.name, dir_fd=parent_fd)
                os.fsync(parent_fd)
            except OSError as exc:
                raise ProfileCustodyRecordError("local custody record cannot be safely cleared") from exc
            finally:
                os.close(descriptor)
        return
    with ExitStack() as anchors:
        _anchor_directory(anchors, path.parent, final_access=0x80000000)
        ctypes, wintypes, kernel32, create_file = _windows_create_file_api()
        file_information_type = _windows_file_information_type()
        handle = create_file(
            str(path),
            0x80000000 | 0x00010000,  # GENERIC_READ | DELETE
            0x00000001 | 0x00000002,  # permit readers/writers, never delete replacement
            None,
            3,  # OPEN_EXISTING
            0x00200000,  # FILE_FLAG_OPEN_REPARSE_POINT
            None,
        )
        if handle == wintypes.HANDLE(-1).value:
            if ctypes.get_last_error() in {2, 3}:
                return
            raise ProfileCustodyRecordError("local custody record cannot be no-follow opened for clear")
        try:
            info = file_information_type()
            if not kernel32.GetFileInformationByHandle(handle, ctypes.byref(info)):
                raise ProfileCustodyRecordError("local custody record identity cannot be verified before clear")
            if info.dwFileAttributes & 0x400 or info.dwFileAttributes & 0x10:
                raise ProfileCustodyRecordError("local custody record must not be a reparse point or directory")
            _windows_mark_handle_for_deletion(int(handle))
        finally:
            kernel32.CloseHandle(handle)


def _posix_open_exclusive_file(parent_fd: int, name: str) -> int:
    try:
        return os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=parent_fd,
        )
    except OSError as exc:
        raise ProfileCustodyRecordError("local custody record cannot be exclusively staged") from exc


def _write_descriptor_fsynced(descriptor: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        written = os.write(descriptor, payload[offset:])
        if written <= 0:
            raise OSError("local custody record short write")
        offset += written
    os.fsync(descriptor)


def _read_regular_file_open(
    path: Path,
    *,
    maximum_bytes: int,
    trace: list[ProfileCustodyPasswordReadOperation] | None,
    parent_fd: int | None = None,
    missing_ok: bool = False,
) -> bytes | None:
    try:
        if parent_fd is None:
            descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0))
        else:
            descriptor = os.open(
                path.name,
                os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=parent_fd,
            )
    except FileNotFoundError:
        if missing_ok:
            return None
        raise ProfileCustodyRecordError("profile capsule record is unavailable") from None
    except OSError as exc:
        raise ProfileCustodyRecordError("profile capsule record is unavailable") from exc
    try:
        _record_read_operation(trace, "stat", path)
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size < 1 or metadata.st_size > maximum_bytes:
            raise ProfileCustodyRecordError("profile capsule record is not a bounded regular file")
        _record_read_operation(trace, "read", path)
        payload = os.read(descriptor, maximum_bytes + 1)
        if len(payload) != metadata.st_size or len(payload) > maximum_bytes:
            raise ProfileCustodyRecordError("profile capsule record changed during its bounded read")
        return payload
    except OSError as exc:
        raise ProfileCustodyRecordError("profile capsule record cannot be read") from exc
    finally:
        os.close(descriptor)


def _read_regular_file_fd(
    parent_fd: int,
    name: str,
    *,
    display_path: Path,
    maximum_bytes: int,
    trace: list[ProfileCustodyPasswordReadOperation] | None,
) -> bytes:
    _record_read_operation(trace, "open", display_path)
    payload = _read_regular_file_open(
        Path(name),
        maximum_bytes=maximum_bytes,
        trace=trace,
        parent_fd=parent_fd,
    )
    if payload is None:
        raise ProfileCustodyRecordError("profile capsule record is unavailable")
    return payload


@contextmanager
def _windows_regular_file_anchor(path: Path, *, missing_ok: bool = False):
    """Reject a final reparse point, then lock the verified leaf against replacement."""
    ctypes, wintypes, kernel32, create_file = _windows_create_file_api()
    file_information_type = _windows_file_information_type()
    handle = create_file(str(path), 0, 0x00000001 | 0x00000002, None, 3, 0x00200000, None)
    if handle == wintypes.HANDLE(-1).value:
        if missing_ok and ctypes.get_last_error() in {2, 3}:
            yield False
            return
        raise ProfileCustodyRecordError("profile capsule record cannot be no-follow opened")
    try:
        info = file_information_type()
        if not kernel32.GetFileInformationByHandle(handle, ctypes.byref(info)):
            raise ProfileCustodyRecordError("profile capsule record identity cannot be verified")
        if info.dwFileAttributes & 0x400 or info.dwFileAttributes & 0x10:
            raise ProfileCustodyRecordError("profile capsule record must not be a reparse point or directory")
        yield True
    finally:
        kernel32.CloseHandle(handle)


def _lexists(path: Path, *, trace: list[ProfileCustodyPasswordReadOperation] | None) -> bool:
    _record_read_operation(trace, "stat", path)
    if os.name == "nt":
        return os.path.lexists(path)
    try:
        with _posix_directory_fd(path.parent) as parent_fd:
            os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise ProfileCustodyRecordError("profile capsule path cannot be no-follow inspected") from exc
    return True


def _posix_child_exists(
    parent_fd: int,
    name: str,
    *,
    trace: list[ProfileCustodyPasswordReadOperation] | None,
    display_path: Path,
) -> bool:
    _record_read_operation(trace, "stat", display_path)
    try:
        os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise ProfileCustodyRecordError("profile capsule path cannot be no-follow inspected") from exc
    return True


def _record_read_operation(
    trace: list[ProfileCustodyPasswordReadOperation] | None,
    operation: Literal["stat", "open", "read"],
    path: Path,
) -> None:
    if trace is not None:
        trace.append(ProfileCustodyPasswordReadOperation(operation=operation, path=path))


def _renameat2_exchange(*, parent_fd: int, first_name: str, second_name: str) -> None:
    """Swap two named children atomically below the same pinned POSIX parent."""
    import ctypes

    renameat2 = getattr(ctypes.CDLL(None, use_errno=True), "renameat2", None)
    if renameat2 is None:
        raise ProfileCustodyRecordError("atomic local custody record exchange is unavailable")
    renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    renameat2.restype = ctypes.c_int
    if renameat2(parent_fd, os.fsencode(first_name), parent_fd, os.fsencode(second_name), 2) == 0:
        return
    error = ctypes.get_errno()
    raise ProfileCustodyRecordError("atomic local custody record exchange failed") from OSError(
        error,
        os.strerror(error),
    )


lexists = _lexists
posix_child_exists = _posix_child_exists
read_regular_file = _read_regular_file
read_regular_file_fd = _read_regular_file_fd
windows_regular_file_anchor = _windows_regular_file_anchor


__all__ = [
    "ProfileCustodyPasswordReadOperation",
    "clear_profile_custody_local_record",
    "compare_and_clear_profile_custody_local_record",
    "compare_and_replace_profile_custody_local_record",
    "compare_and_replace_same_or_predecessor_profile_custody_local_record",
    "ensure_profile_custody_local_directory",
    "profile_custody_local_lock",
    "profile_custody_root_lock",
    "read_optional_profile_custody_local_record",
    "read_profile_custody_local_record",
    "write_profile_custody_local_record",
]
