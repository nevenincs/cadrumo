"""Canonical application errors for supervised operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.errors.hierarchy import CadrumoError, CoreValidationError, InternalInvariantError

if TYPE_CHECKING:
    from .persistence.journal import OperationPersistedSnapshot


class OperationDeclarationError(CoreValidationError):
    """An executor attempted behavior outside its registered declaration."""


class OperationExecutorReturnedNoResultError(InternalInvariantError):
    """An executor returned no result while its operation was neither suspended nor stopped.

    Returning ``None`` is only meaningful when the executor published a pending
    interaction or external wait, or acknowledged a cancellation. Any other
    ``None`` leaves nothing that could ever settle the operation, so the
    supervisor settles it as failed with this code instead of leaving it running.
    """

    def __init__(self) -> None:
        """Carry no executor detail; the registered code is the whole report."""
        super().__init__(translated_message="errors.internal.internal_operation_executor_returned_no_result")


class OperationSubjectBusyError(CadrumoError):
    """Another operation of the same definition still owns this subject.

    A submission is refused while the definition-and-subject conflict lease
    belongs to an operation that has not settled -- one still running, or one
    whose owner lapsed and awaits recovery. The operator waits for it; nothing
    about the holder is carried, so the refusal exposes no operation internals.
    """

    def __init__(self) -> None:
        """Refuse without naming the operation that holds the subject."""
        super().__init__("another operation still owns this definition subject")


class OperationUnsettledError(InternalInvariantError):
    """Supervised execution stopped without reaching a settlement it could commit.

    ``snapshot`` is the journal's state when the failure was observed; the
    stopping error is chained as the cause. The operation is left for owner
    recovery rather than settled with a claim the supervisor cannot prove.
    """

    def __init__(self, snapshot: OperationPersistedSnapshot) -> None:
        """Carry the durable state a waiter reads instead of a bare task failure."""
        super().__init__(
            translated_message="errors.internal.internal_operation_unsettled",
            context={
                "operation_id": snapshot.identity.operation_id,
                "lifecycle": snapshot.lifecycle.value,
                "revision": snapshot.revision,
            },
        )
        self.snapshot = snapshot


__all__ = [
    "OperationDeclarationError",
    "OperationExecutorReturnedNoResultError",
    "OperationSubjectBusyError",
    "OperationUnsettledError",
]
