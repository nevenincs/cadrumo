"""Application-owned capabilities required by the Modelo workflow gate.

The workflow gate builds and persists a filing draft and gives the submission
preflight engine a read-only view of historical submissions.  Those two
surfaces are application contracts; encrypted repository construction belongs
to an outer composition root.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol

from ...domain.filing.schema import ModeloDraft
from ...domain.submission.models import ModeloPresentado


class WorkflowGatePersistenceError(RuntimeError):
    """Translated persistence failure raised by a workflow-gate capability."""

    def __init__(self, operation: str) -> None:
        """Carry the stable application operation without storage details."""
        self.operation = operation
        super().__init__(f"workflow gate persistence operation failed: {operation}")


class WorkflowGateDraftRepositoryProtocol(Protocol):
    """Write capability for the bucket-scoped filing-draft store."""

    def save(self, payload: ModeloDraft, /) -> None:
        """Persist one approved draft."""
        ...


class WorkflowGateSubmissionRepositoryProtocol(Protocol):
    """Read capability for historical submission records."""

    def load(self, record_id: str, /) -> ModeloPresentado | None:
        """Load one historical submission by stable identifier."""
        ...

    def iter_submissions(self) -> Iterator[ModeloPresentado]:
        """Yield persisted submission records in stable order."""
        ...

    def list_submission_ids(self) -> tuple[str, ...]:
        """Return all persisted submission identifiers."""
        ...


@dataclass(frozen=True, slots=True)
class WorkflowGatePorts:
    """Required persistence capabilities for one workflow-gate invocation."""

    draft_repository: WorkflowGateDraftRepositoryProtocol
    submission_repository: WorkflowGateSubmissionRepositoryProtocol


__all__ = [
    "WorkflowGateDraftRepositoryProtocol",
    "WorkflowGatePersistenceError",
    "WorkflowGatePorts",
    "WorkflowGateSubmissionRepositoryProtocol",
]
