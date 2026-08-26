"""Identity-anchored local filesystem substrate for profile custody."""

from __future__ import annotations

import os
import stat
import sys
import threading
import time
from collections.abc import Generator, Mapping
from contextlib import ExitStack, contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal, cast, overload
from uuid import uuid4

from ._filesystem_primitives import (
    PROFILE_CUSTODY_COMMIT_FILENAME,
    ProfileCustodyPasswordReadOperation,
    ensure_profile_custody_local_directory,
)
from ._filesystem_primitives import (
    anchor_directory as _anchor_directory,
)
from ._filesystem_primitives import (
    ensure_real_directory as _ensure_real_directory,
)
from ._filesystem_primitives import (
    is_reparse_metadata as _is_reparse_metadata,
)
from ._filesystem_primitives import (
    posix_directory_fd as _posix_directory_fd,
)
from ._filesystem_primitives import (
    posix_mkdir_child_directory as _posix_mkdir_child_directory,
)
from ._filesystem_primitives import (
    posix_open_child_directory as _posix_open_child_directory,
)
from ._filesystem_primitives import (
    windows_create_file_api as _windows_create_file_api,
)
from ._filesystem_primitives import (
    windows_file_information_type as _windows_file_information_type,
)
from ._filesystem_primitives import (
    write_exclusive_fsynced as _write_exclusive_fsynced,
)
from ._filesystem_primitives import (
    write_exclusive_fsynced_fd as _write_exclusive_fsynced_fd,
)
from .errors import ProfileCustodyRecordError

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


def _remove_posix_staging_if_same(parent_fd: int, name: str, identity: os.stat_result) -> None:
    try:
        current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    except OSError as exc:
        raise ProfileCustodyRecordError("unpublished profile capsule staging cannot be inspected") from exc
    if (current.st_dev, current.st_ino) != (identity.st_dev, identity.st_ino):
        raise ProfileCustodyRecordError("unpublished profile capsule staging identity changed before cleanup")
    _remove_posix_tree(parent_fd, name)


def _remove_posix_tree(parent_fd: int, name: str) -> None:
    target_fd = _posix_open_child_directory(parent_fd, name)
    try:
        with os.scandir(target_fd) as entries:
            for entry in entries:
                if entry.is_dir(follow_symlinks=False):
                    _remove_posix_tree(target_fd, entry.name)
                else:
                    os.unlink(entry.name, dir_fd=target_fd)
    finally:
        os.close(target_fd)
    os.rmdir(name, dir_fd=parent_fd)


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        # Windows does not expose a directory FlushFileBuffers contract. Every
        # staged file is already fsynced; publication uses MoveFileEx
        # WRITE_THROUGH below as the mandatory metadata durability fence.
        return
    descriptor: int
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError as exc:
        raise ProfileCustodyRecordError("profile capsule directory cannot be opened for durability") from exc
    else:
        try:
            os.fsync(descriptor)
        except OSError as exc:
            raise ProfileCustodyRecordError("profile capsule directory could not be fsynced") from exc
        finally:
            os.close(descriptor)


def _rename_directory_noreplace(
    staging: Path,
    destination: Path,
    *,
    root_handle: int | None,
    staging_handle: int | None = None,
) -> None:
    """Publish exactly once; fail closed where the platform has no no-replace rename."""
    if os.name == "nt":
        if root_handle is None:
            raise ProfileCustodyRecordError("profile capsule root is not identity-anchored")
        if staging_handle is None:
            raise ProfileCustodyRecordError("profile capsule staging is not identity-anchored")
        _rename_windows_directory_by_handle(staging_handle, destination, root_handle=root_handle)
        return
    if sys.platform.startswith("linux"):
        if staging.parent != destination.parent:
            raise ProfileCustodyRecordError("profile capsule staging and destination roots must match")
        with _posix_directory_fd(staging.parent) as parent_fd:
            _renameat2_noreplace(
                source_fd=parent_fd,
                source_name=staging.name,
                destination_fd=parent_fd,
                destination_name=destination.name,
            )
        return
    raise ProfileCustodyRecordError("atomic no-replace profile capsule publication is unavailable on this platform")


def _renameat2_noreplace(*, source_fd: int, source_name: str, destination_fd: int, destination_name: str) -> None:
    import ctypes
    import errno

    renameat2 = getattr(ctypes.CDLL(None, use_errno=True), "renameat2", None)
    if renameat2 is None:
        raise ProfileCustodyRecordError("atomic no-replace profile capsule publication is unavailable")
    renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    renameat2.restype = ctypes.c_int
    if renameat2(source_fd, os.fsencode(source_name), destination_fd, os.fsencode(destination_name), 1) == 0:
        return
    error = ctypes.get_errno()
    if error in {errno.EEXIST, errno.ENOTEMPTY}:
        raise ProfileCustodyRecordError("profile capsule destination already exists") from None
    raise ProfileCustodyRecordError("atomic no-replace profile capsule publication failed") from OSError(
        error, os.strerror(error)
    )


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


def _rename_windows_directory_by_handle(staging_handle: int, destination: Path, *, root_handle: int) -> None:
    """Rename the exact open stage while the complete destination ancestry is locked."""
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class _FileRenameInfo(ctypes.Structure):
        _fields_ = [
            ("replace_if_exists", wintypes.BOOLEAN),
            ("root_directory", wintypes.HANDLE),
            ("file_name_length", wintypes.DWORD),
            ("file_name", wintypes.WCHAR * 1),
        ]

    # A mapped/network volume may reject a non-null RootDirectory.  The source
    # is still renamed by its already-open handle, while the component-wise
    # root anchor makes this absolute destination immutable for the call.
    destination_name = str(destination)
    encoded_name = destination_name.encode("utf-16-le")
    name_offset = _FileRenameInfo.file_name.offset
    # FILE_RENAME_INFO declares one WCHAR in the flexible tail.  The Win32
    # information length is the declared structure plus the remaining UTF-16
    # code units, not the structure's alignment padding.
    rename_buffer = ctypes.create_string_buffer(
        ctypes.sizeof(_FileRenameInfo) + len(encoded_name) - ctypes.sizeof(wintypes.WCHAR)
    )
    rename = _FileRenameInfo.from_buffer(rename_buffer)
    rename.replace_if_exists = False
    rename.root_directory = wintypes.HANDLE()
    rename.file_name_length = len(encoded_name)
    ctypes.memmove(ctypes.addressof(rename_buffer) + name_offset, encoded_name, len(encoded_name))
    set_information = kernel32.SetFileInformationByHandle
    set_information.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    set_information.restype = wintypes.BOOL
    if set_information(
        wintypes.HANDLE(staging_handle),
        3,  # FileRenameInfo: ReplaceIfExists=False is the no-replace contract.
        ctypes.byref(rename),
        len(rename_buffer),
    ):
        return
    error = ctypes.get_last_error()
    if error in {80, 183}:
        raise ProfileCustodyRecordError("profile capsule destination already exists") from None
    raise ProfileCustodyRecordError("atomic no-replace profile capsule publication failed") from OSError(
        error, "SetFileInformationByHandle(FileRenameInfo)"
    )


def _write_through_windows_publication_fence(destination: Path, *, root_handle: int | None) -> None:
    """Commit the prior handle-relative rename through Windows' supported fence."""
    if root_handle is None:
        raise ProfileCustodyRecordError("profile capsule root is not identity-anchored for durability")
    import ctypes
    from ctypes import wintypes

    # FlushFileBuffers rejects directory handles on the supported filesystem
    # stack here.  MoveFileExW with MOVEFILE_WRITE_THROUGH is the documented
    # Windows metadata durability contract and remains safe because the entire
    # absolute ancestry is held by no-delete, no-reparse anchors.
    move_file = ctypes.WinDLL("kernel32", use_last_error=True).MoveFileExW
    move_file.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, wintypes.DWORD]
    move_file.restype = wintypes.BOOL
    if not move_file(str(destination), str(destination), 0x00000008):
        error = ctypes.get_last_error()
        if error == 109:  # ERROR_BROKEN_PIPE from a mapped/server volume.
            _fsync_windows_published_commit(destination)
            return
        raise ProfileCustodyRecordError("profile capsule root durability fence failed") from OSError(
            error, "MoveFileExW(MOVEFILE_WRITE_THROUGH)"
        )


def _fsync_windows_published_commit(destination: Path) -> None:
    """Use the server-backed commit record as the remote-volume durability fence."""
    try:
        descriptor = os.open(
            destination / PROFILE_CUSTODY_COMMIT_FILENAME,
            os.O_RDWR | getattr(os, "O_BINARY", 0),
        )
    except OSError as exc:
        raise ProfileCustodyRecordError("published profile capsule commit cannot be durability-fenced") from exc
    try:
        import ctypes
        import msvcrt
        from ctypes import wintypes

        flush = ctypes.WinDLL("kernel32", use_last_error=True).FlushFileBuffers
        flush.argtypes = [wintypes.HANDLE]
        flush.restype = wintypes.BOOL
        if not flush(wintypes.HANDLE(msvcrt.get_osfhandle(descriptor))):
            raise OSError(ctypes.get_last_error(), "FlushFileBuffers")
    except OSError as exc:
        raise ProfileCustodyRecordError("published profile capsule commit durability fence failed") from exc
    finally:
        os.close(descriptor)


def _windows_stage_snapshot(staging: Path) -> dict[str, tuple[int, int, bool]]:
    """Capture the exact transaction-owned tree before any cleanup can occur."""
    try:
        snapshot: dict[str, tuple[int, int, bool]] = {}
        for current, directories, files in os.walk(staging, topdown=True, followlinks=False):
            current_path = Path(current)
            relative = current_path.relative_to(staging).as_posix()
            metadata = current_path.lstat()
            if stat.S_ISLNK(metadata.st_mode) or is_reparse_metadata(metadata):
                raise ProfileCustodyRecordError("unpublished profile capsule staging contains a reparse point")
            snapshot[relative] = (metadata.st_dev, metadata.st_ino, True)
            for name in [*directories, *files]:
                entry = current_path / name
                entry_metadata = entry.lstat()
                if stat.S_ISLNK(entry_metadata.st_mode) or is_reparse_metadata(entry_metadata):
                    raise ProfileCustodyRecordError("unpublished profile capsule staging contains a reparse point")
                snapshot[entry.relative_to(staging).as_posix()] = (
                    entry_metadata.st_dev,
                    entry_metadata.st_ino,
                    stat.S_ISDIR(entry_metadata.st_mode),
                )
        return snapshot
    except OSError as exc:
        raise ProfileCustodyRecordError("unpublished profile capsule staging cannot be identity-inventoried") from exc


def _remove_windows_unpublished_staging(
    staging: Path,
    *,
    staging_handle: int | None,
    snapshot: Mapping[str, tuple[int, int, bool]],
) -> None:
    """Delete only entries proven unchanged while the exact stage is pinned."""
    if staging_handle is None:
        raise ProfileCustodyRecordError("unpublished profile capsule staging is not identity-anchored")
    current_snapshot = _windows_stage_snapshot(staging)
    if current_snapshot != snapshot:
        raise ProfileCustodyRecordError("unpublished profile capsule staging changed before safe cleanup")
    # A native delete disposition is attached to an exact no-reparse handle;
    # postorder guarantees directory emptiness and refuses any swap before it
    # can be marked for removal.
    entries = sorted(snapshot.items(), key=lambda item: item[0].count("/"), reverse=True)
    for relative_name, expected in entries:
        if relative_name == ".":
            continue
        target = staging if relative_name == "." else staging.joinpath(*relative_name.split("/"))
        _windows_delete_exact_entry(target, expected)
    _windows_mark_handle_for_deletion(staging_handle)


def _windows_delete_exact_entry(target: Path, expected: tuple[int, int, bool]) -> None:
    ctypes, wintypes, kernel32, create_file = _windows_create_file_api()
    file_information_type = _windows_file_information_type()
    handle = create_file(str(target), 0x00010000, 0x00000001 | 0x00000002, None, 3, 0x02000000 | 0x00200000, None)
    if handle == wintypes.HANDLE(-1).value:
        raise ProfileCustodyRecordError("unpublished profile capsule entry cannot be identity-opened")
    try:
        info = file_information_type()
        if not kernel32.GetFileInformationByHandle(handle, ctypes.byref(info)):
            raise ProfileCustodyRecordError("unpublished profile capsule entry identity cannot be verified")
        # Python's volume/inode identity is the stable comparison surface used
        # for the recorded inventory; lstat immediately follows each native
        # handle operation so a provider with a different mapping still fails
        # closed if the path changed.
        metadata = target.lstat()
        actual = (metadata.st_dev, metadata.st_ino, stat.S_ISDIR(metadata.st_mode))
        if actual != expected or is_reparse_metadata(metadata) or stat.S_ISLNK(metadata.st_mode):
            raise ProfileCustodyRecordError("unpublished profile capsule entry changed before safe cleanup")
        _windows_mark_handle_for_deletion(int(handle))
    finally:
        kernel32.CloseHandle(handle)


def _windows_mark_handle_for_deletion(handle: int) -> None:
    import ctypes
    from ctypes import wintypes

    class _FileDispositionInfo(ctypes.Structure):
        _fields_ = [("delete_file", wintypes.BOOLEAN)]

    disposition = _FileDispositionInfo(True)
    set_information = ctypes.WinDLL("kernel32", use_last_error=True).SetFileInformationByHandle
    set_information.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    set_information.restype = wintypes.BOOL
    if not set_information(wintypes.HANDLE(handle), 4, ctypes.byref(disposition), ctypes.sizeof(disposition)):
        raise ProfileCustodyRecordError("unpublished profile capsule entry cannot be safely removed")


# Capsule publication is the sole consumer of these component-level primitives.
# They are intentionally public to this custody package so the capsule does not
# reach across a module boundary through private names.
anchor_directory = _anchor_directory
ensure_real_directory = _ensure_real_directory
fsync_directory = _fsync_directory
fsync_windows_published_commit = _fsync_windows_published_commit
is_reparse_metadata = _is_reparse_metadata
lexists = _lexists
posix_child_exists = _posix_child_exists
posix_directory_fd = _posix_directory_fd
posix_mkdir_child_directory = _posix_mkdir_child_directory
posix_open_child_directory = _posix_open_child_directory
read_regular_file = _read_regular_file
read_regular_file_fd = _read_regular_file_fd
remove_posix_staging_if_same = _remove_posix_staging_if_same
remove_posix_tree = _remove_posix_tree
remove_windows_unpublished_staging = _remove_windows_unpublished_staging
rename_directory_noreplace = _rename_directory_noreplace
rename_windows_directory_by_handle = _rename_windows_directory_by_handle
renameat2_noreplace = _renameat2_noreplace
windows_regular_file_anchor = _windows_regular_file_anchor
windows_stage_snapshot = _windows_stage_snapshot
write_exclusive_fsynced = _write_exclusive_fsynced
write_exclusive_fsynced_fd = _write_exclusive_fsynced_fd
write_through_windows_publication_fence = _write_through_windows_publication_fence


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
