"""CLI bridge for exact-profile invoice withholding aggregation."""

from __future__ import annotations

from dataclasses import dataclass

import typer

from ...application.aggregation.invoice_retencion import (
    InvoiceRetencionProjectionDefect,
    InvoiceWithholdingDefectsError,
    InvoiceWithholdingEvidenceRequest,
)
from ...application.aggregation.service import PerModeloAggregationCommand, PerModeloAggregationContributor
from ...application.modelo.invoice_withholding_capture_operation import (
    MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID,
    ModeloInvoiceWithholdingCaptureProjection,
    ModeloInvoiceWithholdingCaptureRequest,
)
from ...application.operations.public_period import PublicPeriod
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import run_registered_operation


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
    """Capture invoice evidence and aggregate inside its immutable profile worker.

    A refusal naming the invoice's retención defects is raised as the
    registered defects error, so the operator reads each defect explained in
    their language rather than a flattened argument error.
    """
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
        result_version=2,
        timeout=120,
        allow_refusal_detail=True,
    )
    projection = completed.projection
    refusal_reason: str | None = None
    refusal_defects: tuple[InvoiceRetencionProjectionDefect, ...] | None = None
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
            refusal_defects = projection.refusal_defects
            _require_invoice_capture_refusal(projection, completed, refusal_reason)
        else:
            _require_invoice_capture_success(projection, completed)
    except Exception:
        raise invalid_completion_error(completed) from None
    if refusal_defects is not None:
        raise InvoiceWithholdingDefectsError(refusal_defects)
    if refusal_reason is not None:
        raise typer.BadParameter(refusal_reason)
    return ModeloInvoiceWithholdingCaptureRead(completion=completed, projection=projection)


__all__ = ["ModeloInvoiceWithholdingCaptureRead", "aggregate_modelo_with_received_invoice_retencion"]


def _invoice_refusal_has_success_data(projection: ModeloInvoiceWithholdingCaptureProjection) -> bool:
    """Reject aggregate data in a refused invoice capture."""
    return (
        projection.provider is not None
        or projection.observation_count is not None
        or projection.source_kinds is not None
        or (projection.result_row_count is not None)
        or (projection.withholding_window is not None)
    )


def _require_invoice_capture_refusal(
    projection: ModeloInvoiceWithholdingCaptureProjection,
    completed: RegisteredOperationCompletion[ModeloInvoiceWithholdingCaptureProjection],
    refusal_reason: str | None,
) -> None:
    """Correlate invoice refusal shape and unchanged terminal effects."""
    if (
        not refusal_reason
        or _invoice_refusal_has_success_data(projection)
        or completed.terminal_condition is not OperationTerminalCondition.REFUSED
        or (completed.refusal_code is None)
        or (completed.refusal_code != projection.refusal_code)
        or (completed.effect is not OperationEffect.NONE)
    ):
        raise ValueError("invoice withholding refusal differs from its registered result")


def _invoice_capture_payload_missing(projection: ModeloInvoiceWithholdingCaptureProjection) -> bool:
    """Require all captured withholding aggregate fields."""
    return (
        projection.outcome != "captured"
        or projection.refusal_reason is not None
        or projection.refusal_defects is not None
        or (projection.provider is not PerModeloAggregationContributor.RETENCIONES)
        or (projection.observation_count is None)
        or (projection.source_kinds is None)
        or (projection.result_row_count is None)
    )


def _invoice_capture_window_invalid(projection: ModeloInvoiceWithholdingCaptureProjection) -> bool:
    """Require a nonempty pinned baseline and positive capture generation."""
    window = projection.withholding_window
    return (
        window is None
        or not window.baseline.scope_token
        or (not window.baseline.generation_id)
        or (window.generation < 1)
    )


def _require_invoice_capture_success(
    projection: ModeloInvoiceWithholdingCaptureProjection,
    completed: RegisteredOperationCompletion[ModeloInvoiceWithholdingCaptureProjection],
) -> None:
    """Correlate captured withholding data with successful mutation custody."""
    if (
        _invoice_capture_payload_missing(projection)
        or _invoice_capture_window_invalid(projection)
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect not in {OperationEffect.UPDATED, OperationEffect.NONE}
    ):
        raise ValueError("invoice withholding result differs from its exact request")
