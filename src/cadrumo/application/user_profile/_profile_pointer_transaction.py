"""Reentrant application transaction for the active-profile pointer.

The core pointer helpers own byte parsing and filesystem mutation. This module
adds the application coordination policy required when one logical profile
operation nests orchestration and repository pointer calls. The outermost
transaction locks the active-pointer sidecar; same-root calls from the same
process and thread reuse that ownership without reacquiring the non-reentrant
operating-system lock.

Ownership never crosses roots, processes, threads, or transaction lifetimes.
Every operation validates the live thread-local ownership record before it
delegates to the public core facade, so a transaction object retained after its
context exits cannot mutate the pointer.
"""

from __future__ import annotations

import os
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from ...core import (
    BucketPointer,
    capture_pointer,
    clear_pointer,
    exclusive_file_lock,
    pointer_path,
    read_pointer,
    restore_pointer,
    write_pointer,
)
from ...core.config import load_settings
from ...core.errors import AeatError


class ActiveProfilePointerTransactionError(AeatError):
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
                "active-profile pointer transaction has no live ownership in this process and thread"
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
    configured = load_settings().cadrumo_local_storage_root if root is None else root
    return configured.expanduser().resolve(strict=False)


@contextmanager
def active_profile_pointer_transaction(
    root: Path | None = None,
) -> Iterator[ActiveProfilePointerTransaction]:
    """Acquire or re-enter the active-profile pointer transaction.

    Re-entry is valid only for the same canonical root, process, and thread.
    Nested use for another root and inherited ownership after ``fork`` fail
    closed. The outermost call waits only for the bounded timeout enforced by
    :func:`~cadrumo.core.exclusive_file_lock`.

    Args:
        root: Local storage root. The configured root is used when omitted.

    Yields:
        The same :class:`ActiveProfilePointerTransaction` object for every
        valid nested acquisition.

    Raises:
        ActiveProfilePointerTransactionError: If nested ownership targets a
            different root or was inherited from another process.
        LockAcquisitionError: If the pointer sidecar remains contended until
            the configured lock timeout expires.
    """
    canonical_root = _canonical_root(root)
    current_pid = os.getpid()
    current_thread_id = threading.get_ident()
    ownership = getattr(_THREAD_OWNERSHIP, "current", None)

    if isinstance(ownership, _Ownership):
        if ownership.pid != current_pid:
            raise ActiveProfilePointerTransactionError(
                "active-profile pointer transaction ownership was inherited from another process"
            )
        if ownership.thread_id != current_thread_id:
            raise ActiveProfilePointerTransactionError(
                "active-profile pointer transaction ownership belongs to another thread"
            )
        if ownership.root != canonical_root:
            raise ActiveProfilePointerTransactionError(
                "nested active-profile pointer transaction targets a different storage root"
            )
        ownership.depth += 1
        try:
            yield ownership.transaction
        finally:
            ownership.depth -= 1
        return

    with exclusive_file_lock(pointer_path(canonical_root)):
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
