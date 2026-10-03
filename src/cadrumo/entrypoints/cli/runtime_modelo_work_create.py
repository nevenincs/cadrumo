"""Authenticated CLI projection of canonical work creation and its refusals."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import typer

from ...adapters.local_runtime.frontend_client import RuntimeFrontendRefusedError
from ...application.modelo.work_create_operation import (
    MODELO_WORK_CREATE_APPLICABILITY_REFUSAL_CODE,
    MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
    ModeloWorkCreateProjection,
    ModeloWorkCreateRefusal,
    ModeloWorkCreateRequest,
    ModeloWorkCreateSuccess,
)
from ...application.operations.public_period import PublicPeriod
from ...application.runtime.contracts import RuntimeRefusalCode
from ...application.user_profile.access_contracts import AccessDenialCode
from ...core.bucket_pointer import resolve_active_bucket_id
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.period import Period
from .common import no_active_profile_refusal
from .errors import CliRefusedBoundaryError
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import (
    RegisteredOperationCompletion,
    run_registered_operation,
    submitted_operation_error,
)


@dataclass(frozen=True, slots=True)
class ModeloWorkCreation:
    """A validated success whose operation receipt survives later presentation."""

    completion: RegisteredOperationCompletion[ModeloWorkCreateProjection]
    result: ModeloWorkCreateSuccess


def create_modelo_work(
    ctx: typer.Context,
    *,
    modelo: str,
    period: Period,
    revision_id: str | None,
    bucket_id: str | None,
    name: str | None,
    actor: str,
    causante_ccaa: str | None,
    allow_not_applicable: bool,
) -> ModeloWorkCreation:
    """Create or reuse work through the session's immutable profile worker."""
    target = resolve_active_bucket_id()
    if target is None:
        raise no_active_profile_refusal()
    client = require_profile_client(ctx, expected_profile_id=UUID(target))
    if bucket_id is not None and bucket_id.strip() and bucket_id.strip() != str(client.profile_id):
        raise RuntimeFrontendRefusedError(AccessDenialCode.PROFILE_MISMATCH.value)
    requested_period = PublicPeriod.from_period(period)
    completed = run_registered_operation(
        client,
        ModeloWorkCreateRequest(
            profile_id=client.profile_id,
            modelo=modelo.strip(),
            period=requested_period,
            revision_id=revision_id or None,
            name=name if name else None,
            actor=actor,
            causante_ccaa=causante_ccaa,
            allow_not_applicable=allow_not_applicable,
        ),
        definition_id=MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=ModeloWorkCreateProjection,
        request_version=1,
        result_version=1,
        timeout=120,
        allow_refusal_detail=True,
    )
    projection = completed.projection
    outcome = projection.outcome
    invalid = projection.profile_id != client.profile_id or projection.period != requested_period
    if isinstance(outcome, ModeloWorkCreateRefusal):
        invalid = invalid or (
            outcome.modelo != modelo.strip()
            or completed.terminal_condition is not OperationTerminalCondition.REFUSED
            or completed.refusal_code != MODELO_WORK_CREATE_APPLICABILITY_REFUSAL_CODE
            or completed.effect is not OperationEffect.NONE
            or allow_not_applicable
        )
        if not invalid:
            raise CliRefusedBoundaryError(
                translated_message="cli.app.modelo.work.create_not_applicable_refused",
                context={
                    "modelo": outcome.modelo,
                    "reason": outcome.reason,
                    "operation_id": str(completed.operation_id),
                    "refusal_code": completed.refusal_code,
                    "terminal_condition": completed.terminal_condition.value,
                    "effect": completed.effect.value,
                },
            )
    else:
        expected_effect = (
            OperationEffect.UPDATED if not outcome.reused or outcome.name_applied is not None else OperationEffect.NONE
        )
        invalid = invalid or (
            completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
            or completed.refusal_code is not None
            or completed.effect is not expected_effect
            or outcome.unit.bucket_id != str(client.profile_id)
            or outcome.unit.period != requested_period
            or outcome.unit.modelo != modelo.strip()
            or (bool(revision_id) and outcome.unit.revision_id != revision_id)
            or outcome.applicability_guard_bypassed is not allow_not_applicable
        )
        if not invalid:
            return ModeloWorkCreation(completion=completed, result=outcome)
    raise submitted_operation_error(
        completed.operation_id,
        RuntimeRefusalCode.INVALID_FRAME.value,
        terminal_condition=completed.terminal_condition,
        effect=completed.effect,
        refusal_code=completed.refusal_code,
    )
