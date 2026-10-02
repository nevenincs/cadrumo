"""CLI bridge for the registered exact-profile Modelo 100 comparison."""

from __future__ import annotations

import typer

from ...application.modelo.taxation_comparison_operation import (
    MODELO_TAXATION_COMPARISON_OPERATION_DEFINITION_ID,
    ModeloTaxationComparisonProjection,
    ModeloTaxationComparisonRequest,
)
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .errors import CliRefusedBoundaryError
from .runtime_modelo_metadata import read_modelo_work_unit
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import run_registered_operation, submitted_operation_error


def compare_modelo_taxation(
    ctx: typer.Context,
    *,
    work_unit_id: str | None,
    modelo: str | None,
    year: int | None,
    period: str | None,
    revision: str | None,
    bucket_id: str | None,
) -> ModeloTaxationComparisonProjection:
    """Select through metadata, then compare the exact selected work unit."""
    client = bound_profile_client(ctx)
    unit = read_modelo_work_unit(
        ctx,
        work_unit_id=work_unit_id,
        modelo=modelo,
        year=year,
        period=period,
        revision=revision,
        bucket_id=bucket_id,
        expected_profile_id=client.profile_id,
    )
    request = ModeloTaxationComparisonRequest(profile_id=client.profile_id, work_unit_id=unit.work_unit_id)
    try:
        completed = run_registered_operation(
            client,
            request,
            definition_id=MODELO_TAXATION_COMPARISON_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(client.profile_id)),
            result_type=ModeloTaxationComparisonProjection,
            request_version=1,
            result_version=1,
            timeout=120,
        )
    except CliRefusedBoundaryError as exc:
        if exc.context is None or exc.context.get("reason") != "REFUSED_TAXATION_COMPARISON":
            raise
        raise CliRefusedBoundaryError(
            translated_message="errors.refused.refused_taxation_comparison", context=exc.context
        ) from None
    projection = completed.projection
    if (
        not isinstance(projection, ModeloTaxationComparisonProjection)
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not OperationEffect.NONE
        or projection.profile_id != client.profile_id
        or projection.work_unit_id != unit.work_unit_id
        or projection.filing_year != unit.filing_year
        or projection.revision != str(unit.revision_id)
        or projection.modelo != str(unit.modelo)
    ):
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        )
    return projection


__all__ = ["compare_modelo_taxation"]
