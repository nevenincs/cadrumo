"""Revision-guarded mutation mechanics shared by profile singleton kernels."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from ..storage.errors import SecureObjectRevisionConflictError


class _RevisionedSingletonLoader[DocumentT](Protocol):
    """Load one singleton document together with its compare-and-swap revision."""

    def __call__(self) -> tuple[DocumentT, str]: ...


class _RevisionedSingletonWrite[DocumentT, WriteT](Protocol):
    """Build a write that asserts the revision read for a singleton document."""

    def __call__(self, document: DocumentT, *, expected_revision_id: str) -> WriteT: ...


class _RevisionedSingletonSave[WriteT](Protocol):
    """Persist one already revision-guarded singleton write."""

    def __call__(self, write: WriteT) -> None: ...


def mutate_revision_guarded_singleton[DocumentT, WriteT](
    mutation: Callable[[DocumentT], DocumentT],
    *,
    load_revisioned: _RevisionedSingletonLoader[DocumentT],
    write: _RevisionedSingletonWrite[DocumentT, WriteT],
    save: _RevisionedSingletonSave[WriteT],
    attempts: int,
) -> DocumentT:
    """Apply a pure singleton mutation, retrying only revision conflicts.

    The caller keeps decoding and wire-format-specific write construction at its
    own boundary. This helper owns only the invariant shared by both singleton
    kernels: the write asserts the revision that the same attempt loaded.
    """
    last_conflict: SecureObjectRevisionConflictError | None = None
    for _attempt in range(attempts):
        current, revision_id = load_revisioned()
        updated = mutation(current)
        try:
            save(write(updated, expected_revision_id=revision_id))
        except SecureObjectRevisionConflictError as exc:
            last_conflict = exc
            continue
        return updated
    raise last_conflict if last_conflict is not None else AssertionError("mutate exhausted without a conflict")
