"""CLI bridge for exact-profile invoice withholding aggregation."""

from __future__ import annotations

from dataclasses import dataclass

import typer

from ...application.aggregation.invoice_retencion import InvoiceWithholdingEvidenceRequest
from ...application.aggregation.service import PerModeloAggregationCommand, PerModeloAggregationContributor
from ...application.modelo.invoice_withholding_capture_operation import (
    MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID,
    MODELO_INVOICE_WITHHOLDING_CAPTURE_REFUSAL_CODE,
    ModeloInvoiceWithholdingCaptureProjection,
    ModeloInvoiceWithholdingCaptureRequest,
)
from ...application.operations.public_period import PublicPeriod
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import (
    RegisteredOperationCompletion,
    run_registered_operation,
    submitted_operation_error,
)


@dataclass(frozen=True, slots=True)
class ModeloInvoiceWithholdingCaptureRead:
    """Keep the settled receipt beside its bounded aggregate projection."""

    completion: RegisteredOperationCompletion[ModeloInvoiceWithholdingCaptureProjection]
    projection: ModeloInvoiceWithholdingCaptureProjection


def aggregate_modelo_with_received_invoice_retencion(
    ctx: typer.Context,
    *,
    command: PerModeloAggregationCommand,
    evidence: InvoiceWithholdingEvidenceRequest,
) -> ModeloInvoiceWithholdingCaptureRead:
    """Capture invoice evidence and aggregate inside its immutable profile worker."""
    client = bound_profile_client(ctx)
    request = ModeloInvoiceWithholdingCaptureRequest.from_inputs(
        profile_id=client.profile_id,
        command=command,
        evidence=evidence,
    )
    completed = run_registered_operation(
        client,
        request,
        definition_id=MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=ModeloInvoiceWithholdingCaptureProjection,
        request_version=1,
        result_version=1,
        timeout=120,
        allow_refusal_detail=True,
    )
    projection = completed.projection
    refusal_reason: str | None = None
    try:
        expected_period = PublicPeriod.from_period(command.period)
        if not isinstance(projection, ModeloInvoiceWithholdingCaptureProjection):
            raise ValueError("invoice withholding result differs from its exact request")
        if (
            projection.profile_id != client.profile_id
            or projection.modelo != command.modelo
            or projection.period != expected_period
        ):
            raise ValueError("invoice withholding result differs from its exact request")
        if projection.outcome == "refused":
            refusal_reason = projection.refusal_reason
            if (
                not refusal_reason
                or projection.provider is not None
                or projection.observation_count is not None
                or projection.source_kinds is not None
                or projection.result_row_count is not None
                or projection.withholding_window is not None
                or completed.terminal_condition is not OperationTerminalCondition.REFUSED
                or completed.refusal_code != MODELO_INVOICE_WITHHOLDING_CAPTURE_REFUSAL_CODE
                or completed.effect is not OperationEffect.NONE
            ):
                raise ValueError("invoice withholding refusal differs from its registered result")
        else:
            window = projection.withholding_window
            if (
                projection.outcome != "captured"
                or projection.refusal_reason is not None
                or projection.provider is not PerModeloAggregationContributor.RETENCIONES
                or projection.observation_count is None
                or projection.source_kinds is None
                or projection.result_row_count is None
                or window is None
                or not window.baseline.scope_token
                or not window.baseline.generation_id
                or window.generation < 1
                or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
                or completed.refusal_code is not None
                or completed.effect not in {OperationEffect.UPDATED, OperationEffect.NONE}
            ):
                raise ValueError("invoice withholding result differs from its exact request")
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
    return ModeloInvoiceWithholdingCaptureRead(completion=completed, projection=projection)


__all__ = ["ModeloInvoiceWithholdingCaptureRead", "aggregate_modelo_with_received_invoice_retencion"]
