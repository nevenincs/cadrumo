"""Canonical application errors for supervised operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.errors.hierarchy import CoreValidationError, InternalInvariantError

if TYPE_CHECKING:
    from .persistence.journal import OperationPersistedSnapshot


class OperationDeclarationError(CoreValidationError):
    """An executor attempted behavior outside its registered declaration."""


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


__all__ = ["OperationDeclarationError", "OperationUnsettledError"]
