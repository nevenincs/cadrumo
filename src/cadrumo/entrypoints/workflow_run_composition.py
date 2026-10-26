"""Compose workflow history against the worker's explicit profile store."""

from __future__ import annotations

from uuid import UUID

from ..application.workflow.run_read_ports import WorkflowRunReadPorts


def build_workflow_run_read_ports(*, bucket_id: str) -> WorkflowRunReadPorts:
    """Return a read capability with canonical, exact-profile custody."""
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from ..application.workflow.persistence import WorkflowRunRepository

    normalized = str(UUID(bucket_id))
    return WorkflowRunReadPorts(
        bucket_id=normalized,
        runs=WorkflowRunRepository(objects=secure_object_repository_for_bucket(normalized)),
    )
