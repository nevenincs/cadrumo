"""Reentrant transition authority for the active-profile pointer.

The core record IO owns strict parsing and atomic replacement. This application
authority owns the canonical custody-root lock and is consequently the only
owner that may advance the durable pointer transition revision.
"""

from __future__ import annotations

import os
import threading
from collections.abc import Generator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path

from ...core import (
    BucketPointer,
    read_pointer,
    write_pointer,
)
from ...core.config import load_settings
from ...core.errors import CadrumoError
from ...core.locks_errors import LockAcquisitionError
from ...core.paths import effective_storage_root
from ._custody_ports import default_profile_custody_local_record_store
from ._profile_pointer_ports import ProfileCustodyRootLockPort


class ActiveProfilePointerTransactionError(CadrumoError):
    """Reject invalid nesting or use outside live transaction ownership."""


class ActiveProfilePointerTransaction:
    """Pointer observations and transitions under the canonical root lock."""

    __slots__ = ("_owner_pid", "_owner_thread_id", "_root")

    def __init__(self, *, root: Path, owner_pid: int, owner_thread_id: int) -> None:
        self._root = root
        self._owner_pid = owner_pid
        self._owner_thread_id = owner_thread_id

    def read(self) -> BucketPointer:
        """Return the sole selection-plus-coordinate observation."""
        self._assert_live_ownership()
        return read_pointer(self._root)

    def select(self, bucket_id: str) -> BucketPointer:
        """Select ``bucket_id`` and advance once unless it is already selected."""
        self._assert_live_ownership()
        return self._publish(expected=None, bucket_id=bucket_id)

    def compare_and_select(self, *, expected: BucketPointer, bucket_id: str) -> BucketPointer:
        """Select only when the exact observed record remains current."""
        self._assert_live_ownership()
        return self._publish(expected=expected, bucket_id=bucket_id)

    def compare_and_restore(self, *, expected: BucketPointer, captured: BucketPointer) -> BucketPointer:
        """Restore a prior selection without ever restoring its old revision."""
        self._assert_live_ownership()
        return self._publish(expected=expected, bucket_id=captured.bucket_id)

    def clear(self) -> BucketPointer:
        """Persist an absent tombstone unless the selection is already absent."""
        self._assert_live_ownership()
        return self._publish(expected=None, bucket_id=None)

    def _publish(self, *, expected: BucketPointer | None, bucket_id: str | None) -> BucketPointer:
        observed = read_pointer(self._root)
        if expected is not None and observed != expected:
            raise ActiveProfilePointerTransactionError(
                translated_message="errors.integrity.integrity_storage_profile_custody_record",
                context={"owner": "active-profile-pointer", "compare_and_swap": False},
            )
        if observed.bucket_id == bucket_id:
            return observed
        successor = (
            BucketPointer.absent(transition_revision=observed.transition_revision + 1)
            if bucket_id is None
            else BucketPointer.selected(
                bucket_id=bucket_id,
                transition_revision=observed.transition_revision + 1,
            )
        )
        write_pointer(self._root, successor)
        return successor

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
    return default_profile_custody_local_record_store().root_lock


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


def observe_active_profile_pointer(root: Path | None = None) -> BucketPointer:
    """Return one lock-scoped public pointer observation.

    Purpose-specific application readers use this facade instead of opening a
    parallel core read path; core bootstrap remains the sole inner-layer
    exception because it cannot depend outward on this application owner.
    """
    with active_profile_pointer_transaction(root) as transaction:
        return transaction.read()


__all__ = [
    "ActiveProfilePointerTransaction",
    "ActiveProfilePointerTransactionError",
    "active_profile_pointer_transaction",
    "observe_active_profile_pointer",
]
