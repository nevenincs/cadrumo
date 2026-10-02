"""CLI bridge for exact-profile modelo aggregation operations."""

from __future__ import annotations

import typer

from ...application.aggregation.ledger_payment_withholding import LedgerPaymentWithholdingEvidenceRequest
from ...application.aggregation.service import PerModeloAggregationCommand
from ...application.modelo.aggregate_operation import (
    MODELO_AGGREGATE_OPERATION_DEFINITION_ID,
    MODELO_AGGREGATE_REFUSAL_CODES,
    ModeloAggregateOperationRequest,
    ModeloAggregateProjection,
)
from ...application.operations.public_period import PublicPeriod
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import (
    run_registered_operation,
    submitted_operation_error,
)


def run_modelo_aggregate(
    ctx: typer.Context,
    *,
    command: PerModeloAggregationCommand,
    ledger_payment: LedgerPaymentWithholdingEvidenceRequest | None = None,
) -> ModeloAggregateProjection:
    """Submit one aggregate request to its invocation's bound profile worker."""
    client = bound_profile_client(ctx)
    request = ModeloAggregateOperationRequest.from_inputs(
        profile_id=client.profile_id,
        command=command,
        ledger_payment=ledger_payment,
    )
    completed = run_registered_operation(
        client,
        request,
        definition_id=MODELO_AGGREGATE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=ModeloAggregateProjection,
        request_version=1,
        result_version=1,
        timeout=120,
        allow_refusal_detail=True,
    )
    projection = completed.projection
    refusal_reason: str | None = None
    try:
        if not isinstance(projection, ModeloAggregateProjection):
            raise ValueError("modelo aggregate result has an unexpected type")
        projection = ModeloAggregateProjection.model_validate(projection.model_dump(mode="python"), strict=True)
        if (
            projection.profile_id != client.profile_id
            or projection.modelo != command.modelo
            or projection.period != PublicPeriod.from_period(command.period)
        ):
            raise ValueError("modelo aggregate result differs from its exact request")
        if projection.outcome == "refused":
            refusal_reason = projection.refusal_reason
            if (
                not refusal_reason
                or projection.provider is not None
                or projection.observation_count is not None
                or projection.source_kinds is not None
                or projection.result_row_count is not None
                or projection.clave_breakdown is not None
                or projection.withholding_window is not None
                or completed.terminal_condition is not OperationTerminalCondition.REFUSED
                or completed.refusal_code not in MODELO_AGGREGATE_REFUSAL_CODES
                or completed.effect is not OperationEffect.NONE
            ):
                raise ValueError("modelo aggregate refusal differs from its registered result")
        else:
            expected_effects = (
                {OperationEffect.UPDATED, OperationEffect.NONE}
                if ledger_payment is not None
                else {OperationEffect.NONE}
            )
            window = projection.withholding_window
            expects_window = command.modelo in {"111", "115", "123"}
            if (
                projection.outcome != "aggregated"
                or projection.refusal_reason is not None
                or projection.provider is None
                or projection.observation_count is None
                or projection.source_kinds is None
                or projection.result_row_count is None
                or projection.clave_breakdown is None
                or expects_window != (window is not None)
                or (
                    window is not None
                    and (not window.baseline.scope_token or not window.baseline.generation_id or window.generation < 0)
                )
                or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
                or completed.refusal_code is not None
                or completed.effect not in expected_effects
            ):
                raise ValueError("modelo aggregate result differs from its exact request")
    except Exception:
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        ) from None
    if refusal_reason is not None:
        raise typer.BadParameter(refusal_reason)
    return projection


__all__ = ["run_modelo_aggregate"]
