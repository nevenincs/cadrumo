"""Bounded CLI client for registered modelo revision, verification and filing."""

from __future__ import annotations

from uuid import UUID

import typer

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient, RuntimeFrontendRefusedError
from ...application.modelo.operation_definitions import (
    MODELO_WORK_FILE_OPERATION_DEFINITION_ID,
    MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
    ModeloWorkFilePublicResultV2,
    ModeloWorkFileRequest,
    ModeloWorkVerifyPublicResultV2,
    ModeloWorkVerifyRequest,
)
from ...application.modelo.revision_selection_operation import (
    MODELO_WORK_REVISION_OPERATION_DEFINITION_ID,
    ModeloWorkRevisionProjection,
    ModeloWorkRevisionRequest,
)
from ...application.modelo.selectors import ModeloCalculationRevisionDefault, ModeloCalculationRevisionSelector
from ...application.modelo.work_addressing import ModeloWorkAddressNotFoundError
from ...application.operations.public_period import PublicPeriod
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.user_profile.access_contracts import AccessDenialCode
from ...core.bucket_pointer import resolve_active_bucket_id
from ...core.operations import (
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ._modelo_behavior_support import work_address_for_cli
from ._modelo_cli_support import selector_bad_parameter, validate_calculation_revision_id
from .common import no_active_profile_refusal
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import (
    RegisteredOperationCompletion,
    run_registered_operation,
    submitted_operation_error,
)


def read_modelo_work_revision(
    client: RuntimeFrontendClient, request: ModeloWorkRevisionRequest, *, timeout: float = 60
) -> RegisteredOperationCompletion[ModeloWorkRevisionProjection]:
    """Select a revision through the exact-profile registered read."""
    if request.profile_id != client.profile_id:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    completed = run_registered_operation(
        client,
        request,
        definition_id=MODELO_WORK_REVISION_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=ModeloWorkRevisionProjection,
        request_version=1,
        result_version=1,
        timeout=timeout,
    )
    projection = completed.projection
    if (
        not isinstance(projection, ModeloWorkRevisionProjection)
        or projection.profile_id != client.profile_id
        or projection.unit.bucket_id != str(client.profile_id)
        or completed.effect is not OperationEffect.NONE
    ):
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
            effect=completed.effect,
        )
    return completed


def select_modelo_work_revision_for_cli(
    ctx: typer.Context,
    *,
    calculation_revision_id: str | None,
    work_unit_id: str | None,
    modelo: str | None,
    year: int | None,
    period: str | None,
    revision: str | None,
    bucket_id: str | None,
    selector: ModeloCalculationRevisionSelector,
    default_for: ModeloCalculationRevisionDefault | None,
    timeout: float = 60,
) -> tuple[RuntimeFrontendClient, ModeloWorkRevisionProjection]:
    """Resolve an operator revision address only inside its admitted profile."""
    target = resolve_active_bucket_id()
    if target is None:
        raise no_active_profile_refusal()
    client = require_profile_client(ctx, expected_profile_id=UUID(target))
    if bucket_id is not None and bucket_id.strip() and bucket_id.strip() != str(client.profile_id):
        raise RuntimeFrontendRefusedError(AccessDenialCode.PROFILE_MISMATCH.value)
    validated_id = (
        validate_calculation_revision_id(calculation_revision_id) if calculation_revision_id is not None else None
    )
    has_work_address = any(value is not None for value in (work_unit_id, modelo, year, period, revision))
    if has_work_address or validated_id is None:
        try:
            address = work_address_for_cli(
                work_unit_id=work_unit_id,
                modelo=modelo,
                year=year,
                period=period,
                revision=revision,
                bucket_id=bucket_id,
            )
        except ModeloWorkAddressNotFoundError as error:
            raise selector_bad_parameter(error) from error
        selected_work_unit_id = address.work_unit_id or address.operator_work_unit_id
        selected_modelo = address.modelo
        selected_year = address.filing_year
        selected_period = address.period
        selected_revision = address.registry_revision_id
    else:
        selected_work_unit_id = selected_modelo = selected_year = selected_period = selected_revision = None
    request = ModeloWorkRevisionRequest(
        profile_id=client.profile_id,
        calculation_revision_id=validated_id,
        work_unit_id=selected_work_unit_id,
        modelo=selected_modelo,
        year=selected_year,
        period=PublicPeriod.from_period(selected_period) if selected_period is not None else None,
        revision=selected_revision,
        selector=selector,
        default_for=default_for,
    )
    completed = read_modelo_work_revision(client, request, timeout=timeout)
    projection = completed.projection
    if not isinstance(projection, ModeloWorkRevisionProjection):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return client, projection


def run_modelo_work_verification(
    client: RuntimeFrontendClient, *, work_unit_id: str, request: ModeloWorkVerifyRequest, timeout: float = 60
) -> RegisteredOperationCompletion[ModeloWorkVerifyPublicResultV2]:
    """Submit one selected exact revision to the canonical verify executor."""
    completed = run_registered_operation(
        client,
        request,
        definition_id=MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
        subject_ref=work_unit_id,
        result_type=ModeloWorkVerifyPublicResultV2,
        request_version=1,
        result_version=2,
        timeout=timeout,
    )
    projection = completed.projection
    if (
        not isinstance(projection, ModeloWorkVerifyPublicResultV2)
        or projection.calculation_revision_id != request.calculation_revision_id
        or projection.advisories.work_unit_id != work_unit_id
        or projection.advisories.calculation_revision_id != request.calculation_revision_id
        or completed.effect not in {OperationEffect.NONE, OperationEffect.UPDATED}
    ):
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
            effect=completed.effect,
        )
    return completed


def run_modelo_work_filing(
    client: RuntimeFrontendClient, *, work_unit_id: str, request: ModeloWorkFileRequest, timeout: float = 60
) -> RegisteredOperationCompletion[ModeloWorkFilePublicResultV2]:
    """Submit one exact reviewed revision for local filing only."""
    completed = run_registered_operation(
        client,
        request,
        definition_id=MODELO_WORK_FILE_OPERATION_DEFINITION_ID,
        subject_ref=work_unit_id,
        result_type=ModeloWorkFilePublicResultV2,
        request_version=2,
        result_version=2,
        timeout=timeout,
    )
    projection = completed.projection
    if (
        not isinstance(projection, ModeloWorkFilePublicResultV2)
        or projection.work_unit_id != work_unit_id
        or projection.record.bucket_id != str(client.profile_id)
        or projection.calculation_revision_id != request.approval.calculation_revision_id
        or projection.advisories.work_unit_id != work_unit_id
        or projection.advisories.calculation_revision_id != request.approval.calculation_revision_id
        or not projection.handoff_required
        or completed.effect not in {OperationEffect.NONE, OperationEffect.UPDATED}
    ):
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
            effect=completed.effect,
        )
    return completed


__all__ = [
    "read_modelo_work_revision",
    "run_modelo_work_filing",
    "run_modelo_work_verification",
    "select_modelo_work_revision_for_cli",
]
