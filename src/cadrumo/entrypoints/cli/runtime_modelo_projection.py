"""Exact-profile registered transport for modelo project and compare."""

from __future__ import annotations

from uuid import UUID

import typer

from ...application.modelo.projection_operation import (
    MODELO_COMPARE_OPERATION_DEFINITION_ID,
    MODELO_PROJECT_OPERATION_DEFINITION_ID,
    ModeloCompareOperationProjection,
    ModeloCompareOperationRequest,
    ModeloProjectOperationProjection,
    ModeloProjectOperationRequest,
)
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .common import active_bucket_id_or_refuse
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import run_registered_operation


def run_modelo_project(ctx: typer.Context, request: ModeloProjectOperationRequest) -> ModeloProjectOperationProjection:
    """Receive only a settled, exact-profile annual projection."""
    profile_id = UUID(active_bucket_id_or_refuse())
    if request.profile_id != profile_id:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    client = require_profile_client(ctx, expected_profile_id=profile_id)
    completed = run_registered_operation(
        client,
        request,
        definition_id=MODELO_PROJECT_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        result_type=ModeloProjectOperationProjection,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    result = completed.projection
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect not in {OperationEffect.NONE, OperationEffect.UPDATED}
        or completed.refusal_code is not None
        or result.profile_id != profile_id
        or result.year != request.year
        or result.ccaa != request.ccaa
    ):
        raise invalid_completion_error(completed)
    return result


def run_modelo_compare(ctx: typer.Context, request: ModeloCompareOperationRequest) -> ModeloCompareOperationProjection:
    """Receive only a settled, exact-profile, exact-year comparison."""
    profile_id = UUID(active_bucket_id_or_refuse())
    if request.profile_id != profile_id:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    client = require_profile_client(ctx, expected_profile_id=profile_id)
    completed = run_registered_operation(
        client,
        request,
        definition_id=MODELO_COMPARE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        result_type=ModeloCompareOperationProjection,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    result = completed.projection
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect not in {OperationEffect.NONE, OperationEffect.UPDATED}
        or completed.refusal_code is not None
        or result.profile_id != profile_id
        or result.modelo != request.modelo
        or (result.year_a, result.year_b) != tuple(sorted(request.years))
    ):
        raise invalid_completion_error(completed)
    return result


__all__ = ["run_modelo_compare", "run_modelo_project"]
