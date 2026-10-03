"""Receipt-bound public result projection for invoice withholding capture."""

from __future__ import annotations

from pydantic import BaseModel

from ...core.hashing import canonical_json_bytes
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ..operations.models import (
    OperationTerminalReceipt,
    require_succeeded_receipt_references,
    require_terminal_receipt_match,
    terminal_receipt_matches,
)
from .invoice_withholding_capture_contracts import (
    MODELO_INVOICE_WITHHOLDING_CAPTURE_MAX_RESULT_BYTES,
    MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID,
    ModeloInvoiceWithholdingCaptureProjection,
    ModeloInvoiceWithholdingCaptureReport,
)


def _validated_report(result: BaseModel) -> ModeloInvoiceWithholdingCaptureReport:
    if type(result) is not ModeloInvoiceWithholdingCaptureReport:
        raise ValueError("invalid invoice-withholding operation result")
    return ModeloInvoiceWithholdingCaptureReport.model_validate(result.model_dump(mode="python"), strict=True)


def _require_receipt_identity(
    projection: ModeloInvoiceWithholdingCaptureProjection,
    receipt: OperationTerminalReceipt,
) -> None:
    if (
        receipt.identity.definition_id != MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID
        or receipt.identity.subject_ref != profile_operation_subject(str(projection.profile_id))
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
    ):
        raise ValueError("invoice-withholding result differs from its terminal receipt")


def _require_refusal_receipt(
    report: ModeloInvoiceWithholdingCaptureReport,
    receipt: OperationTerminalReceipt,
) -> None:
    projection = report.projection
    if (
        report.local_write_performed
        or not terminal_receipt_matches(
            receipt,
            definition_id=MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(projection.profile_id)),
            condition=OperationTerminalCondition.REFUSED,
            effect=OperationEffect.NONE,
        )
        or receipt.refusal_ref != projection.refusal_code
        or receipt.refusal_detail_ref is None
    ):
        raise ValueError("invoice-withholding refusal contradicts its terminal receipt")


def _require_success_receipt(
    report: ModeloInvoiceWithholdingCaptureReport,
    receipt: OperationTerminalReceipt,
) -> None:
    message = "invoice-withholding capture contradicts its terminal receipt"
    require_terminal_receipt_match(
        receipt,
        definition_id=MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(report.projection.profile_id)),
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.UPDATED if report.local_write_performed else OperationEffect.NONE,
        message=message,
    )
    require_succeeded_receipt_references(receipt, message=message)


def _require_public_result_size(projection: ModeloInvoiceWithholdingCaptureProjection) -> None:
    if (
        len(canonical_json_bytes(projection.model_dump(mode="json")))
        > MODELO_INVOICE_WITHHOLDING_CAPTURE_MAX_RESULT_BYTES
    ):
        raise ValueError("invoice-withholding projection exceeds its public result limit")


def project_modelo_invoice_withholding_capture_result(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    /,
) -> BaseModel:
    """Release only the allowlisted summary whose terminal receipt agrees."""
    report = _validated_report(result)
    projection = report.projection
    _require_receipt_identity(projection, receipt)
    if projection.outcome == "refused":
        _require_refusal_receipt(report, receipt)
    else:
        _require_success_receipt(report, receipt)
    _require_public_result_size(projection)
    return projection


__all__ = ["project_modelo_invoice_withholding_capture_result"]
