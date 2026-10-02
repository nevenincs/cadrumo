"""CLI access to worker-owned discovery of private Modelo wizard inputs."""

from __future__ import annotations

from uuid import UUID

import typer

from ...application.modelo.wizard_attempt_operation import (
    MODELO_WORK_WIZARD_ATTEMPT_OPERATION_DEFINITION_ID,
    ModeloWorkWizardAttemptCalculated,
    ModeloWorkWizardAttemptProjection,
    ModeloWorkWizardAttemptRequest,
)
from ...application.modelo.wizard_context_operation import (
    MODELO_WORK_WIZARD_CONTEXT_OPERATION_DEFINITION_ID,
    ModeloWorkWizardContextProjection,
    ModeloWorkWizardContextRequest,
)
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.external_constants import OutputLanguage
from ...core.identity.hex_ids import WorkUnitId
from ...core.operations import OperationEffect, OperationTerminalCondition
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import (
    RegisteredOperationCompletion,
    run_registered_operation,
    submitted_operation_error,
)


def read_modelo_work_wizard_context(
    ctx: typer.Context, *, profile_id: UUID, work_unit_id: WorkUnitId, output_language: OutputLanguage
) -> ModeloWorkWizardContextProjection:
    """Return only the exact admitted unit's prompt snapshot in the requested language."""
    client = require_profile_client(ctx, expected_profile_id=profile_id)
    completed = run_registered_operation(
        client,
        ModeloWorkWizardContextRequest(
            profile_id=client.profile_id, work_unit_id=work_unit_id, output_language=output_language
        ),
        definition_id=MODELO_WORK_WIZARD_CONTEXT_OPERATION_DEFINITION_ID,
        subject_ref=work_unit_id,
        result_type=ModeloWorkWizardContextProjection,
        request_version=1,
        result_version=1,
        timeout=60,
    )
    projection = completed.projection
    if (
        projection.profile_id != client.profile_id
        or projection.unit.work_unit_id != work_unit_id
        or projection.output_language is not output_language
        or completed.effect is not OperationEffect.NONE
    ):
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
            effect=completed.effect,
        )
    return projection


def run_modelo_work_wizard_attempt(
    ctx: typer.Context, request: ModeloWorkWizardAttemptRequest
) -> RegisteredOperationCompletion[ModeloWorkWizardAttemptProjection]:
    """Accept a follow-up only from a completed, exactly bound worker attempt."""
    client = require_profile_client(ctx, expected_profile_id=request.profile_id)
    completed = run_registered_operation(
        client,
        request,
        definition_id=MODELO_WORK_WIZARD_ATTEMPT_OPERATION_DEFINITION_ID,
        subject_ref=request.calculation.work_unit_id,
        result_type=ModeloWorkWizardAttemptProjection,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    projection = completed.projection
    outcome = projection.outcome
    if isinstance(outcome, ModeloWorkWizardAttemptCalculated):
        result = outcome.result
        unit = result.unit
        invalid_effect = (
            result.revision_published and completed.effect is not OperationEffect.UPDATED
        ) or completed.effect not in {OperationEffect.UPDATED, OperationEffect.UNKNOWN}
        invalid_revision = unit.current_calculation_revision_id != result.calculation_revision_id
    else:
        unit = outcome.unit
        invalid_effect = completed.effect is not OperationEffect.UNKNOWN
        invalid_revision = False
    if (
        projection.profile_id != client.profile_id
        or projection.output_language is not request.output_language
        or unit.work_unit_id != request.calculation.work_unit_id
        or unit.bucket_id != str(client.profile_id)
        or invalid_effect
        or invalid_revision
    ):
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
            effect=completed.effect,
        )
    return completed
