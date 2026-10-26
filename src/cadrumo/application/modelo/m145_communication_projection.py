"""Receipt-bound public result projection for Modelo 145 operations."""

from __future__ import annotations

from pydantic import BaseModel

from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ..operations.models import OperationTerminalReceipt
from .m145_communication_contracts import (
    M145CommunicationExecutionResult,
    M145CommunicationOperationResult,
    require_m145_communication_projection_kind,
)


def _require_receipt_identity(
    projected: M145CommunicationOperationResult,
    receipt: OperationTerminalReceipt,
) -> None:
    if (
        receipt.identity.definition_id != projected.operation_id
        or receipt.identity.subject_ref != profile_operation_subject(str(projected.profile_id))
        or receipt.effect is not projected.effect
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
    ):
        raise ValueError("M145 result differs from its terminal receipt")


def _require_success_receipt(
    projected: M145CommunicationOperationResult,
    receipt: OperationTerminalReceipt,
) -> None:
    if projected.result is None:
        raise ValueError("M145 success has no typed result")
    require_m145_communication_projection_kind(projected.operation_id, projected.result)
    if receipt.condition is not OperationTerminalCondition.SUCCEEDED:
        raise ValueError("M145 success has an incompatible terminal receipt")


def _require_refusal_receipt(
    projected: M145CommunicationOperationResult,
    receipt: OperationTerminalReceipt,
) -> None:
    if (
        projected.refusal is None
        or receipt.condition is not OperationTerminalCondition.REFUSED
        or receipt.refusal_detail_ref is None
        or receipt.refusal_ref != projected.refusal.code
        or receipt.effect is not OperationEffect.NONE
    ):
        raise ValueError("M145 refusal has an incompatible terminal receipt")


def project_m145_communication_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release the encrypted terminal detail only with its exact settled receipt."""
    if type(result) is not M145CommunicationExecutionResult:
        raise ValueError("invalid M145 private result type")
    projected = result.result
    _require_receipt_identity(projected, receipt)
    if projected.outcome == "completed":
        _require_success_receipt(projected, receipt)
    else:
        _require_refusal_receipt(projected, receipt)
    return projected


__all__ = ["project_m145_communication_result"]
