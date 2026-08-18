"""Reentrant application transaction for the active-profile pointer.

The core pointer helpers own byte parsing and filesystem mutation. This module
adds the application coordination policy required when one logical profile
operation nests orchestration and repository pointer calls. The outermost
transaction locks the custody root sidecar shared with destructive pointer
CAS; same-root calls from the same process and thread reuse that ownership
without reacquiring the non-reentrant operating-system lock.

Ownership never crosses roots, processes, threads, or transaction lifetimes.
Every operation validates the live thread-local ownership record before it
delegates to the public core facade, so a transaction object retained after its
context exits cannot mutate the pointer.
"""

from __future__ import annotations

import os
import threading
from collections.abc import Generator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from ...adapters.persistence.storage import custody
from ...core import (
    BucketPointer,
    capture_pointer,
    clear_pointer,
    read_pointer,
    restore_pointer,
    write_pointer,
)
from ...core.config import load_settings
from ...core.errors import CadrumoError
from ...core.locks_errors import LockAcquisitionError
from ...core.paths import effective_storage_root
from ._profile_pointer_ports import ProfileCustodyRootLockPort


class ActiveProfilePointerTransactionError(CadrumoError):
    """Reject invalid nesting or use outside live transaction ownership."""


class ActiveProfilePointerTransaction:
    """Pointer operations available only while this transaction owns its lock."""

    __slots__ = ("_owner_pid", "_owner_thread_id", "_root")

    def __init__(self, *, root: Path, owner_pid: int, owner_thread_id: int) -> None:
        self._root = root
        self._owner_pid = owner_pid
        self._owner_thread_id = owner_thread_id

    def capture(self) -> bytes | None:
        """Capture the pointer's exact bytes under live transaction ownership."""
        self._assert_live_ownership()
        return capture_pointer(self._root)

    def read(self) -> BucketPointer | None:
        """Read and parse the pointer under live transaction ownership."""
        self._assert_live_ownership()
        return read_pointer(self._root)

    def write(self, pointer: BucketPointer) -> None:
        """Atomically write ``pointer`` under live transaction ownership."""
        self._assert_live_ownership()
        write_pointer(self._root, pointer)

    def compare_and_write(self, *, expected: bytes | None, pointer: BucketPointer) -> bytes:
        """Durably write ``pointer`` only when the captured bytes still match.

        The transaction holds the canonical custody-root lock, so cooperating
        writers cannot interleave the comparison and durable replacement.  The
        exact-byte comparison also detects an out-of-band writer rather than
        silently overwriting a selection it did not observe.
        """
        self._assert_live_ownership()
        observed = capture_pointer(self._root)
        if observed != expected:
            raise ActiveProfilePointerTransactionError(
                translated_message="errors.integrity.integrity_storage_profile_custody_record",
                context={"owner": "active-profile-pointer", "compare_and_swap": False},
            )
        write_pointer(self._root, pointer)
        published = capture_pointer(self._root)
        if published is None:
            raise ActiveProfilePointerTransactionError(
                translated_message="errors.integrity.integrity_storage_profile_custody_record",
                context={"owner": "active-profile-pointer", "published": False},
            )
        return published

    def compare_and_restore(self, *, expected: bytes | None, captured: bytes | None) -> None:
        """Restore exact bytes only while the expected post-write value remains."""
        self._assert_live_ownership()
        observed = capture_pointer(self._root)
        if observed != expected:
            raise ActiveProfilePointerTransactionError(
                translated_message="errors.integrity.integrity_storage_profile_custody_record",
                context={"owner": "active-profile-pointer", "compare_and_swap": False},
            )
        restore_pointer(self._root, captured)

    def restore(self, captured: bytes | None) -> None:
        """Atomically restore exact captured bytes under live ownership."""
        self._assert_live_ownership()
        restore_pointer(self._root, captured)

    def clear(self) -> None:
        """Idempotently clear the pointer under live transaction ownership."""
        self._assert_live_ownership()
        clear_pointer(self._root)

    def _assert_live_ownership(self) -> None:
        ownership = getattr(_THREAD_OWNERSHIP, "current", None)
        current_pid = os.getpid()
        current_thread_id = threading.get_ident()
        if (
            not isinstance(ownership, _Ownership)
            or ownership.transaction is not self
            or ownership.root != self._root
            or ownership.pid != self._owner_pid
            or ownership.thread_id != self._owner_thread_id
            or ownership.pid != current_pid
            or ownership.thread_id != current_thread_id
            or ownership.depth < 1
        ):
            raise ActiveProfilePointerTransactionError(
                translated_message="errors.internal.internal_active_profile_pointer_transaction",
                context={"live_ownership": False},
            )


@dataclass(slots=True)
class _Ownership:
    root: Path
    pid: int
    thread_id: int
    depth: int
    transaction: ActiveProfilePointerTransaction


_THREAD_OWNERSHIP = threading.local()


def _canonical_root(root: Path | None) -> Path:
    return effective_storage_root(root)


def _default_root_lock_port() -> ProfileCustodyRootLockPort:
    """Resolve the concrete storage lock through the storage facade."""
    provider = custody.profile_custody_root_lock
    if not callable(provider):
        raise TypeError("profile custody root-lock provider is unavailable")
    return cast(ProfileCustodyRootLockPort, provider)


@contextmanager
def _acquire_root_lock(
    root: Path,
    *,
    timeout_seconds: float,
    root_lock: ProfileCustodyRootLockPort,
) -> Generator[None]:
    """Adapt the injected root-lock port to the application error contract."""
    with ExitStack() as stack:
        try:
            stack.enter_context(root_lock(root, timeout_seconds=timeout_seconds))
        except Exception as exc:
            raise LockAcquisitionError(str(exc)) from exc
        yield


@contextmanager
def active_profile_pointer_transaction(
    root: Path | None = None,
    *,
    root_lock: ProfileCustodyRootLockPort | None = None,
) -> Generator[ActiveProfilePointerTransaction]:
    """Acquire or re-enter the active-profile pointer transaction.

    Re-entry is valid only for the same canonical root, process, and thread.
    Nested use for another root and inherited ownership after ``fork`` fail
    closed. The outermost call waits only for the bounded timeout enforced by
    :func:`~cadrumo.adapters.persistence.storage.custody.profile_custody_local_lock`.

    Args:
        root: Local storage root. The configured root is used when omitted.
        root_lock: Optional application-owned lock provider for dependency
            injection; the public custody provider is used by default.

    Yields:
        The same :class:`ActiveProfilePointerTransaction` object for every
        valid nested acquisition.

    Raises:
        ActiveProfilePointerTransactionError: If nested ownership targets a
            different root or was inherited from another process.
        LockAcquisitionError: If the custody root sidecar remains contended until
            the configured lock timeout expires.
    """
    canonical_root = _canonical_root(root)
    current_pid = os.getpid()
    current_thread_id = threading.get_ident()
    ownership = getattr(_THREAD_OWNERSHIP, "current", None)

    if isinstance(ownership, _Ownership):
        if ownership.pid != current_pid:
            raise ActiveProfilePointerTransactionError(
                translated_message="errors.internal.internal_active_profile_pointer_transaction",
                context={"owning_process_is_current": False},
            )
        if ownership.thread_id != current_thread_id:
            raise ActiveProfilePointerTransactionError(
                translated_message="errors.internal.internal_active_profile_pointer_transaction",
                context={"owning_thread_is_current": False},
            )
        if ownership.root != canonical_root:
            raise ActiveProfilePointerTransactionError(
                translated_message="errors.internal.internal_active_profile_pointer_transaction",
                context={"nested_root_matches": False},
            )
        ownership.depth += 1
        try:
            yield ownership.transaction
        finally:
            ownership.depth -= 1
        return

    # The custody root lock is the one lock identity shared with destructive
    # profile-custody CAS.  Pointer writers cannot publish between the
    # captured-byte comparison and mutation performed under that root lock.
    root_lock_port = root_lock or _default_root_lock_port()
    with _acquire_root_lock(
        canonical_root,
        timeout_seconds=load_settings().cadrumo_file_lock_timeout_s,
        root_lock=root_lock_port,
    ):
        transaction = ActiveProfilePointerTransaction(
            root=canonical_root,
            owner_pid=current_pid,
            owner_thread_id=current_thread_id,
        )
        ownership = _Ownership(
            root=canonical_root,
            pid=current_pid,
            thread_id=current_thread_id,
            depth=1,
            transaction=transaction,
        )
        _THREAD_OWNERSHIP.current = ownership
        try:
            yield transaction
        finally:
            ownership.depth = 0
            del _THREAD_OWNERSHIP.current


__all__ = [
    "ActiveProfilePointerTransaction",
    "ActiveProfilePointerTransactionError",
    "active_profile_pointer_transaction",
]
