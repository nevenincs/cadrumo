"""Correlate invoice intake results with exact terminal receipt effects."""

from __future__ import annotations

from pydantic import BaseModel

from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ..operations.models import OperationTerminalReceipt
from .catalogue_intake_contracts import (
    INVOICE_INTAKE_PROJECTION_TYPES,
    InvoiceImportProjection,
    InvoiceIntakeExecutionResult,
    InvoiceWizardOutcome,
)
from .catalogue_intake_refusal import INVOICE_WIZARD_VALIDATION_REFUSAL_CODE


def project_invoice_intake_result(
    value: BaseModel, receipt: OperationTerminalReceipt, /
) -> InvoiceImportProjection | InvoiceWizardOutcome:
    """Release complete facts only with matching terminal effect and authority."""
    if type(value) is not InvoiceIntakeExecutionResult or not isinstance(value, InvoiceIntakeExecutionResult):
        raise ValueError("invalid invoice intake result")
    private = InvoiceIntakeExecutionResult.model_validate(value.model_dump(mode="python"), strict=True)
    projection = private.projection
    _require_invoice_intake_projection_scope(receipt, private, projection)
    if isinstance(projection, InvoiceWizardOutcome) and projection.outcome == "refused":
        _require_invoice_wizard_refusal_receipt(receipt)
        return projection
    _require_invoice_intake_success_receipt(receipt)
    _require_invoice_intake_effect(receipt, projection)
    return projection


def _require_invoice_intake_projection_scope(
    receipt: OperationTerminalReceipt,
    private: InvoiceIntakeExecutionResult,
    projection: InvoiceImportProjection | InvoiceWizardOutcome,
) -> None:
    if (
        type(projection) is not INVOICE_INTAKE_PROJECTION_TYPES.get(receipt.identity.definition_id)
        or receipt.identity.subject_ref != profile_operation_subject(str(projection.profile_id))
        or receipt.effect.value != private.effect
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
    ):
        raise ValueError("invoice intake outcome differs from its terminal receipt")


def _require_invoice_wizard_refusal_receipt(receipt: OperationTerminalReceipt) -> None:
    if (
        receipt.condition is not OperationTerminalCondition.REFUSED
        or receipt.effect is not OperationEffect.NONE
        or receipt.refusal_ref != INVOICE_WIZARD_VALIDATION_REFUSAL_CODE
        or receipt.refusal_detail_ref is None
        or receipt.result_ref is not None
    ):
        raise ValueError("invoice intake refusal differs from its terminal receipt")


def _require_invoice_intake_success_receipt(receipt: OperationTerminalReceipt) -> None:
    if (
        receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.result_ref is None
        or receipt.refusal_ref is not None
        or receipt.refusal_detail_ref is not None
    ):
        raise ValueError("invoice intake outcome differs from its terminal receipt")


def _require_invoice_intake_effect(
    receipt: OperationTerminalReceipt,
    projection: InvoiceImportProjection | InvoiceWizardOutcome,
) -> None:
    if isinstance(projection, InvoiceWizardOutcome):
        if projection.result is None:
            raise ValueError("invoice intake success has no wizard result")
        expected = OperationEffect.NONE if projection.result.already_existed else OperationEffect.UPDATED
    else:
        expected = (
            OperationEffect.NONE
            if projection.created == 0
            else OperationEffect.PARTIAL
            if projection.refused
            else OperationEffect.UPDATED
        )
    if receipt.effect is not expected:
        raise ValueError("invoice intake row facts differ from its mutation effect")


__all__ = ["project_invoice_intake_result"]
