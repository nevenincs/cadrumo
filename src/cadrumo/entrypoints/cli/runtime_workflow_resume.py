"""CLI transport for authenticated resume context and bounded refusal guidance."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import typer

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient, RuntimeFrontendRefusedError
from ...application.modelo.selectors import ModeloCalculationRevisionSelector
from ...application.operations.public_period import PublicPeriod
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
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import run_registered_operation


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
    _require_resume_profile(client, bucket_id)
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
        success = _resume_success(completed, request, outcome, constraint, invalid)
        if success is not None:
            return success
    else:
        _resume_refusal(completed, request, outcome, constraint, invalid)
    raise invalid_completion_error(completed)


def _resume_success(
    completed: RegisteredOperationCompletion[WorkflowResumeProjection],
    request: WorkflowResumeRequest,
    outcome: WorkflowResumeSuccess,
    constraint: PublicPeriod | None,
    invalid: bool,
) -> WorkflowResumeCompletion | None:
    """Build resume context only from a correlated successful receipt."""
    address = outcome.address
    expected_run = request.target if request.target is not None and len(request.target) == 16 else None
    expected_unit = request.work_unit_id or (
        request.target if request.target is not None and len(request.target) == 64 else None
    )
    invalid = (
        invalid
        or _invalid_resume_terminal(completed)
        or _invalid_resume_address(request, outcome, expected_run, expected_unit)
        or _invalid_resume_obligation(request, outcome, constraint)
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
    return None


def _invalid_resume_terminal(completed: RegisteredOperationCompletion[WorkflowResumeProjection]) -> bool:
    """Require an unrefused successful terminal receipt."""
    return (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED or completed.refusal_code is not None
    )


def _invalid_resume_address(
    request: WorkflowResumeRequest, outcome: WorkflowResumeSuccess, expected_run: str | None, expected_unit: str | None
) -> bool:
    """Correlate the selected run, work unit, and calculation revision."""
    address = outcome.address
    return (
        (expected_run is not None and address.run_id != expected_run)
        or (expected_unit is not None and address.work_unit_id != expected_unit)
        or (
            request.calculation_revision_id is not None
            and address.calculation_revision_id != request.calculation_revision_id
        )
    )


def _invalid_resume_obligation(
    request: WorkflowResumeRequest, outcome: WorkflowResumeSuccess, constraint: PublicPeriod | None
) -> bool:
    """Correlate the requested period and modelo obligation."""
    return (constraint is not None and outcome.obligation.period != constraint) or (
        request.modelo is not None and outcome.obligation.modelo != request.modelo
    )


def _resume_refusal(
    completed: RegisteredOperationCompletion[WorkflowResumeProjection],
    request: WorkflowResumeRequest,
    outcome: WorkflowResumeRefusal | WorkflowResumeAmbiguity,
    constraint: PublicPeriod | None,
    invalid: bool,
) -> None:
    """Validate refusal identity before presenting its bounded guidance."""
    code = (
        WORKFLOW_RESUME_REFUSAL_CODE if isinstance(outcome, WorkflowResumeRefusal) else WORKFLOW_RESUME_AMBIGUITY_CODE
    )
    invalid = invalid or (
        completed.terminal_condition is not OperationTerminalCondition.REFUSED or completed.refusal_code != code
    )
    if isinstance(outcome, WorkflowResumeAmbiguity):
        invalid = invalid or _invalid_resume_ambiguity(request, outcome, constraint)
    elif request.target is not None and len(request.target) == 16:
        invalid = invalid or outcome.run_id != request.target
    if not invalid:
        _present_resume_refusal(completed, outcome, code)


def _require_resume_profile(client: RuntimeFrontendClient, bucket_id: str | None) -> None:
    """Refuse a nonempty requested profile that differs from the bound client."""
    if bucket_id is not None and bucket_id.strip() and bucket_id.strip() != str(client.profile_id):
        raise RuntimeFrontendRefusedError(AccessDenialCode.PROFILE_MISMATCH.value)


def _invalid_resume_ambiguity(
    request: WorkflowResumeRequest, outcome: WorkflowResumeAmbiguity, constraint: PublicPeriod | None
) -> bool:
    """Correlate the ambiguous candidate set with its requested obligation."""
    return (constraint is not None and outcome.period != constraint) or (
        request.modelo is not None and outcome.modelo != request.modelo
    )


def _present_resume_refusal(
    completed: RegisteredOperationCompletion[WorkflowResumeProjection],
    outcome: WorkflowResumeRefusal | WorkflowResumeAmbiguity,
    code: str,
) -> None:
    """Present only the guidance belonging to an already correlated refusal."""
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
            "candidates": workflow_resume_candidate_lines(tuple(item.to_candidate() for item in outcome.candidates)),
        },
    )
