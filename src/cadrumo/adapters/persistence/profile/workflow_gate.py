"""Persistence adapters for the Modelo workflow-gate capabilities."""

from __future__ import annotations

from collections.abc import Iterator
from typing import override

from ....application.modelo.workflow_gate_ports import (
    WorkflowGateDraftRepositoryProtocol,
    WorkflowGatePersistenceError,
    WorkflowGatePorts,
    WorkflowGateSubmissionRepositoryProtocol,
)
from ....domain.filing.schema import ModeloDraft
from ....domain.submission.models import ModeloPresentado
from ..storage.errors import StorageError
from ..storage.runtime_repository import secure_object_repository_for_bucket
from .filing_drafts import ModeloDraftRepository
from .submission import SubmissionRepository


class WorkflowGateDraftRepositoryAdapter(WorkflowGateDraftRepositoryProtocol):
    """Translate the encrypted filing-draft repository to the app contract."""

    def __init__(self, *, repository: ModeloDraftRepository) -> None:
        """Bind an already-composed draft repository."""
        self._repository = repository

    @override
    def save(self, payload: ModeloDraft, /) -> None:
        """Persist an approved draft and translate storage failures."""
        try:
            self._repository.save(payload)
        except (StorageError, OSError) as exc:
            raise WorkflowGatePersistenceError("draft_save") from exc


class WorkflowGateSubmissionRepositoryAdapter(WorkflowGateSubmissionRepositoryProtocol):
    """Translate the encrypted submission repository to the app contract."""

    def __init__(self, *, repository: SubmissionRepository) -> None:
        """Bind an already-composed submission repository."""
        self._repository = repository

    @override
    def load(self, record_id: str, /) -> ModeloPresentado | None:
        """Load one historical submission and translate storage failures."""
        try:
            return self._repository.load(record_id)
        except (StorageError, OSError) as exc:
            raise WorkflowGatePersistenceError("submission_load") from exc

    @override
    def iter_submissions(self) -> Iterator[ModeloPresentado]:
        """Yield historical submissions while translating iteration failures."""
        try:
            yield from self._repository.iter_submissions()
        except (StorageError, OSError) as exc:
            raise WorkflowGatePersistenceError("submission_iter") from exc

    @override
    def list_submission_ids(self) -> tuple[str, ...]:
        """List historical submission ids and translate storage failures."""
        try:
            return self._repository.list_submission_ids()
        except (StorageError, OSError) as exc:
            raise WorkflowGatePersistenceError("submission_list") from exc


def build_workflow_gate_ports(*, bucket_id: str) -> WorkflowGatePorts:
    """Compose workflow-gate persistence capabilities for one profile bucket."""
    normalized_bucket_id = bucket_id.strip()
    objects = secure_object_repository_for_bucket(normalized_bucket_id)
    return WorkflowGatePorts(
        draft_repository=WorkflowGateDraftRepositoryAdapter(
            repository=ModeloDraftRepository(bucket_id=normalized_bucket_id, objects=objects),
        ),
        submission_repository=WorkflowGateSubmissionRepositoryAdapter(
            repository=SubmissionRepository(objects=objects),
        ),
    )


__all__ = [
    "WorkflowGateDraftRepositoryAdapter",
    "WorkflowGateSubmissionRepositoryAdapter",
    "build_workflow_gate_ports",
]
