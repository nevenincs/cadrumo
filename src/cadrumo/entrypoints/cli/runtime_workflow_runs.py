"""Authenticated workflow-history reads for the installed CLI."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import typer

from ...application.runtime.contracts import RuntimeRefusalCode
from ...application.workflow.run_projection import WorkflowRunSnapshot
from ...application.workflow.run_read_operation import (
    WORKFLOW_RUN_LIST_OPERATION_DEFINITION_ID,
    WORKFLOW_RUN_READ_OPERATION_DEFINITION_ID,
    WorkflowRunListProjection,
    WorkflowRunListRequest,
    WorkflowRunReadProjection,
    WorkflowRunReadRequest,
)
from ...core.bucket_pointer import require_active_bucket_id
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import (
    RegisteredOperationCompletion,
    run_registered_operation,
    submitted_operation_error,
)


@dataclass(frozen=True, slots=True)
class WorkflowRunReadCompletion:
    """Keep an exact terminal receipt beside its correlated run snapshot."""

    completion: RegisteredOperationCompletion[WorkflowRunReadProjection]
    run: WorkflowRunSnapshot


@dataclass(frozen=True, slots=True)
class WorkflowRunsReadCompletion:
    """Keep an exact inventory receipt beside its correlated run snapshots."""

    completion: RegisteredOperationCompletion[WorkflowRunListProjection]
    runs: tuple[WorkflowRunSnapshot, ...]


def read_workflow_run(ctx: typer.Context, *, run_id: str) -> WorkflowRunReadCompletion:
    """Read one run under the profile session's current result authorization."""
    client = require_profile_client(ctx, expected_profile_id=UUID(require_active_bucket_id()))
    completed = run_registered_operation(
        client,
        WorkflowRunReadRequest(profile_id=client.profile_id, run_id=run_id),
        definition_id=WORKFLOW_RUN_READ_OPERATION_DEFINITION_ID,
        subject_ref=run_id,
        result_type=WorkflowRunReadProjection,
        request_version=1,
        result_version=1,
        timeout=60,
    )
    projection = completed.projection
    if (
        projection.profile_id != client.profile_id
        or projection.run.run_id != run_id
        or projection.expected_period is not None
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not OperationEffect.NONE
    ):
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        )
    return WorkflowRunReadCompletion(completion=completed, run=projection.run)


def read_workflow_runs(ctx: typer.Context) -> WorkflowRunsReadCompletion:
    """Capture the complete history only with all-period profile authority."""
    client = require_profile_client(ctx, expected_profile_id=UUID(require_active_bucket_id()))
    completed = run_registered_operation(
        client,
        WorkflowRunListRequest(profile_id=client.profile_id),
        definition_id=WORKFLOW_RUN_LIST_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=WorkflowRunListProjection,
        request_version=1,
        result_version=1,
        timeout=60,
    )
    projection = completed.projection
    if (
        projection.profile_id != client.profile_id
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not OperationEffect.NONE
    ):
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        )
    return WorkflowRunsReadCompletion(completion=completed, runs=projection.runs)
