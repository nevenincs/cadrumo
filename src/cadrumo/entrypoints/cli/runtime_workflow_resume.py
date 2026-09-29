"""CLI transport for authenticated resume context and bounded refusal guidance."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import typer

from ...adapters.local_runtime.frontend_client import RuntimeFrontendRefusedError
from ...application.modelo.selectors import ModeloCalculationRevisionSelector
from ...application.operations.public_period import PublicPeriod
from ...application.runtime.contracts import RuntimeRefusalCode
from ...application.user_profile.access_contracts import AccessDenialCode
from ...application.workflow.resume import (
    WorkflowResumeContext,
    WorkflowResumeTargetResolution,
    validate_workflow_resume_target_token,
    workflow_resume_candidate_lines,
)
from ...application.workflow.resume_operation import (
    WORKFLOW_RESUME_AMBIGUITY_CODE,
    WORKFLOW_RESUME_OPERATION_DEFINITION_ID,
    WORKFLOW_RESUME_REFUSAL_CODE,
    WorkflowResumeAmbiguity,
    WorkflowResumeProjection,
    WorkflowResumeRefusal,
    WorkflowResumeRequest,
    WorkflowResumeSuccess,
)
from ...core.bucket_pointer import require_active_bucket_id
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.period import Period
from .errors import CliRefusedBoundaryError
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import (
    RegisteredOperationCompletion,
    run_registered_operation,
    submitted_operation_error,
)


@dataclass(frozen=True, slots=True)
class WorkflowResumeCompletion:
    """Retain the terminal receipt through resume-context presentation."""

    completion: RegisteredOperationCompletion[WorkflowResumeProjection]
    context: WorkflowResumeContext
    resolution: WorkflowResumeTargetResolution


def read_workflow_resume_context(
    ctx: typer.Context,
    *,
    target: str | None,
    work_unit_id: str | None,
    calculation_revision_id: str | None,
    modelo: str | None,
    period: Period | None,
    revision_id: str | None,
    selector: ModeloCalculationRevisionSelector | None,
    bucket_id: str | None,
) -> WorkflowResumeCompletion:
    """Obtain context through the current profile session, never a local fallback."""
    client = require_profile_client(ctx, expected_profile_id=UUID(require_active_bucket_id()))
    if bucket_id is not None and bucket_id.strip() and bucket_id.strip() != str(client.profile_id):
        raise RuntimeFrontendRefusedError(AccessDenialCode.PROFILE_MISMATCH.value)
    exact = any(item is not None for item in (target, work_unit_id, calculation_revision_id))
    constraint = PublicPeriod.from_period(period) if period is not None else None
    request = WorkflowResumeRequest(
        profile_id=client.profile_id,
        target=validate_workflow_resume_target_token(target) if target is not None else None,
        work_unit_id=work_unit_id,
        calculation_revision_id=calculation_revision_id,
        modelo=modelo,
        period=None if exact else constraint,
        expected_period=constraint if exact else None,
        revision_id=revision_id,
        selector=selector,
    )
    completed = run_registered_operation(
        client,
        request,
        definition_id=WORKFLOW_RESUME_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=WorkflowResumeProjection,
        request_version=1,
        result_version=1,
        timeout=60,
        allow_refusal_detail=True,
    )
    outcome = completed.projection.outcome
    invalid = completed.projection.profile_id != client.profile_id or completed.effect is not OperationEffect.NONE
    if isinstance(outcome, WorkflowResumeSuccess):
        address = outcome.address
        expected_run = request.target if request.target is not None and len(request.target) == 16 else None
        expected_unit = request.work_unit_id or (
            request.target if request.target is not None and len(request.target) == 64 else None
        )
        invalid = invalid or (
            completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
            or completed.refusal_code is not None
            or (expected_run is not None and address.run_id != expected_run)
            or (expected_unit is not None and address.work_unit_id != expected_unit)
            or (
                request.calculation_revision_id is not None
                and address.calculation_revision_id != request.calculation_revision_id
            )
            or (constraint is not None and outcome.obligation.period != constraint)
            or (request.modelo is not None and outcome.obligation.modelo != request.modelo)
        )
        if not invalid:
            obligation = outcome.obligation.to_obligation()
            return WorkflowResumeCompletion(
                completion=completed,
                context=WorkflowResumeContext(
                    resumed_from_run_id=address.run_id,
                    modelo=obligation.modelo,
                    period=obligation.period,
                    obligation=obligation,
                    aborted_reason=outcome.aborted_reason,
                ),
                resolution=address.to_resolution(),
            )
    else:
        code = (
            WORKFLOW_RESUME_REFUSAL_CODE
            if isinstance(outcome, WorkflowResumeRefusal)
            else WORKFLOW_RESUME_AMBIGUITY_CODE
        )
        invalid = invalid or (
            completed.terminal_condition is not OperationTerminalCondition.REFUSED or completed.refusal_code != code
        )
        if isinstance(outcome, WorkflowResumeAmbiguity):
            invalid = invalid or (
                (constraint is not None and outcome.period != constraint)
                or (request.modelo is not None and outcome.modelo != request.modelo)
            )
        elif request.target is not None and len(request.target) == 16:
            invalid = invalid or outcome.run_id != request.target
        if not invalid:
            receipt_facts = {
                "operation_id": str(completed.operation_id),
                "refusal_code": code,
                "terminal_condition": completed.terminal_condition.value,
                "effect": completed.effect.value,
            }
            if isinstance(outcome, WorkflowResumeRefusal):
                raise CliRefusedBoundaryError(
                    translated_message=f"application.workflow.errors.resume_refused_{outcome.reason.value}",
                    context=receipt_facts
                    | {
                        "run_id": outcome.run_id,
                        "final_stage": outcome.final_stage.value,
                        "reason": outcome.aborted_reason.value if outcome.aborted_reason is not None else "",
                    },
                )
            raise CliRefusedBoundaryError(
                translated_message="application.workflow.errors.resume_run_ambiguous",
                context=receipt_facts
                | {
                    "modelo": outcome.modelo,
                    "period": str(outcome.period.to_period()),
                    "candidate_count": str(len(outcome.candidates)),
                    "candidates": workflow_resume_candidate_lines(
                        tuple(item.to_candidate() for item in outcome.candidates)
                    ),
                },
            )
    raise submitted_operation_error(
        completed.operation_id,
        RuntimeRefusalCode.INVALID_FRAME.value,
        terminal_condition=completed.terminal_condition,
        effect=completed.effect,
        refusal_code=completed.refusal_code,
    )
