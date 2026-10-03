"""CLI bridge for exact-profile modelo aggregation operations."""

from __future__ import annotations

import typer

from ...application.aggregation.ledger_payment_withholding import LedgerPaymentWithholdingEvidenceRequest
from ...application.aggregation.service import PerModeloAggregationCommand
from ...application.aggregation.withholding_filing_cadence import PERIODIC_WITHHOLDING_MODELOS
from ...application.modelo.aggregate_operation import (
    MODELO_AGGREGATE_OPERATION_DEFINITION_ID,
    MODELO_AGGREGATE_REFUSAL_CODES,
    ModeloAggregateOperationRequest,
    ModeloAggregateProjection,
)
from ...application.operations.public_period import PublicPeriod
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import run_registered_operation

_PERIODIC_WINDOW_MODELOS = frozenset(modelo.value for modelo in PERIODIC_WITHHOLDING_MODELOS)


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
        request_version=2,
        result_version=2,
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
            refusal_reason = _require_aggregate_refusal(projection, completed)
        else:
            _require_aggregate_success(projection, completed, command, ledger_payment)
    except Exception:
        raise invalid_completion_error(completed) from None
    if refusal_reason is not None:
        raise typer.BadParameter(refusal_reason)
    return projection


def _has_aggregate_refusal_payload(projection: ModeloAggregateProjection) -> bool:
    """Detect success-only data attached to a refused aggregation."""
    return (
        projection.provider is not None
        or projection.observation_count is not None
        or projection.source_kinds is not None
        or projection.result_row_count is not None
        or projection.clave_breakdown is not None
        or projection.absent_source_families is not None
        or projection.calculation_revision_id is not None
        or projection.withholding_window is not None
    )


def _require_aggregate_refusal(
    projection: ModeloAggregateProjection, completed: RegisteredOperationCompletion[ModeloAggregateProjection]
) -> str | None:
    """Correlate an empty refusal projection with its registered receipt."""
    refusal_reason = projection.refusal_reason
    if (
        not refusal_reason
        or _has_aggregate_refusal_payload(projection)
        or completed.terminal_condition is not OperationTerminalCondition.REFUSED
        or completed.refusal_code not in MODELO_AGGREGATE_REFUSAL_CODES
        or completed.effect is not OperationEffect.NONE
    ):
        raise ValueError("modelo aggregate refusal differs from its registered result")
    return refusal_reason


def _missing_aggregate_success_payload(projection: ModeloAggregateProjection) -> bool:
    """Require the complete result vocabulary of an aggregation."""
    return (
        projection.outcome != "aggregated"
        or projection.refusal_reason is not None
        or projection.provider is None
        or projection.observation_count is None
        or projection.source_kinds is None
        or projection.result_row_count is None
        or projection.clave_breakdown is None
        or projection.absent_source_families is None
    )


def _invalid_aggregate_window(projection: ModeloAggregateProjection, expects_window: bool) -> bool:
    """Correlate the periodic withholding window and its baseline identity."""
    window = projection.withholding_window
    return bool(
        (expects_window and (projection.clave_breakdown or projection.absent_source_families))
        or expects_window != (window is not None)
        or (
            window is not None
            and (not window.baseline.scope_token or not window.baseline.generation_id or window.generation < 0)
        )
    )


def _require_aggregate_success(
    projection: ModeloAggregateProjection,
    completed: RegisteredOperationCompletion[ModeloAggregateProjection],
    command: PerModeloAggregationCommand,
    ledger_payment: LedgerPaymentWithholdingEvidenceRequest | None,
) -> None:
    """Correlate aggregation data, withholding scope, and admitted effects."""
    expected_effects = (
        {OperationEffect.UPDATED, OperationEffect.NONE} if ledger_payment is not None else {OperationEffect.NONE}
    )
    expects_window = command.modelo in _PERIODIC_WINDOW_MODELOS
    if (
        _missing_aggregate_success_payload(projection)
        or _invalid_aggregate_window(projection, expects_window)
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect not in expected_effects
    ):
        raise ValueError("modelo aggregate result differs from its exact request")


__all__ = ["run_modelo_aggregate"]
