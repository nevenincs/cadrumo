"""Run the human Quickfile chain through its exact-profile worker operation."""

from __future__ import annotations

from typing import Never

import typer
from pydantic import BaseModel

from ...application.modelo.quickfile import QuickfileStage, QuickfileStageStatus
from ...application.modelo.quickfile_operation import QUICKFILE_OPERATION_DEFINITION_ID
from ...application.modelo.quickfile_operation_contracts import (
    QuickfileProjection,
    QuickfileRequest,
    QuickfileStageSnapshot,
)
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.operations import OperationTerminalCondition, profile_operation_subject
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import (
    RegisteredOperationCompletion,
    run_registered_operation,
    submitted_operation_error,
)


def _invalid[ProjectionT: BaseModel](completed: RegisteredOperationCompletion[ProjectionT]) -> Never:
    """Reject a result whose exact-profile chain facts contradict its receipt."""
    raise submitted_operation_error(
        completed.operation_id,
        RuntimeRefusalCode.INVALID_FRAME.value,
        terminal_condition=completed.terminal_condition,
        effect=completed.effect,
        refusal_code=completed.refusal_code,
    )


def _stage_error_is_consistent(projection: QuickfileProjection, stage: QuickfileStageSnapshot) -> bool:
    """Accept only the canonical verification refusal that carries a negative report."""
    if stage.status is not QuickfileStageStatus.REFUSED:
        return stage.error is None
    if stage.error is not None:
        return True
    report = projection.verification_report
    return stage.stage is QuickfileStage.VERIFY and report is not None and not report.granted_verificado_completo


def run_quickfile(ctx: typer.Context, request: QuickfileRequest) -> QuickfileProjection:
    """Submit one complete filing target and validate its worker result."""
    client = require_profile_client(ctx, expected_profile_id=request.profile_id)
    completed = run_registered_operation(
        client,
        request,
        definition_id=QUICKFILE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(request.profile_id)),
        result_type=QuickfileProjection,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    projection = completed.projection
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not projection.effect
        or projection.profile_id != request.profile_id
        or projection.modelo != request.modelo
        or projection.period != request.period
        or projection.filing_year != request.period.to_period().filing_year
        or any(not _stage_error_is_consistent(projection, stage) for stage in projection.stages)
        or (request.revision_id is not None and projection.registry_revision_id != request.revision_id)
        or (
            projection.completed and (projection.export is None or projection.export.output_path != request.output_path)
        )
    ):
        _invalid(completed)
    return projection


__all__ = ["run_quickfile"]
