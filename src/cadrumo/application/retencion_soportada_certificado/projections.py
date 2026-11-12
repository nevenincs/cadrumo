"""Receipt-checked public projections for the suffered-withholding certificate operations."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ..operations.models import (
    OperationTerminalReceipt,
    refused_receipt_references_hold,
    require_succeeded_terminal_receipt,
)
from .contracts import (
    RETENCION_SOPORTADA_LIST_OPERATION_DEFINITION_ID,
    RETENCION_SOPORTADA_RECORD_OPERATION_DEFINITION_ID,
    RETENCION_SOPORTADA_REMOVE_OPERATION_DEFINITION_ID,
    RETENCION_SOPORTADA_REVISION_REFUSAL_CODE,
    RETENCION_SOPORTADA_WRITE_REFUSAL_CODE,
)
from .results import (
    RetencionSoportadaListProjection,
    RetencionSoportadaMutationProjection,
    RetencionSoportadaOperationExecutionResult,
)

_MUTATION_DEFINITIONS = {
    "record": RETENCION_SOPORTADA_RECORD_OPERATION_DEFINITION_ID,
    "remove": RETENCION_SOPORTADA_REMOVE_OPERATION_DEFINITION_ID,
}


def _profile_from_receipt(receipt: OperationTerminalReceipt, *, definition_id: str) -> UUID:
    if receipt.identity.definition_id != definition_id:
        raise ValueError("suffered-withholding result definition differs from its terminal receipt")
    subject = receipt.identity.subject_ref
    try:
        profile_id = UUID(subject.removeprefix("profile:"))
    except ValueError:
        raise ValueError("suffered-withholding result has an invalid profile subject") from None
    if subject != profile_operation_subject(str(profile_id)):
        raise ValueError("suffered-withholding result has an invalid profile subject")
    return profile_id


def _execution_result(result: BaseModel) -> RetencionSoportadaOperationExecutionResult:
    if type(result) is not RetencionSoportadaOperationExecutionResult:
        raise ValueError("suffered-withholding execution result has an incompatible type")
    return RetencionSoportadaOperationExecutionResult.model_validate(result.model_dump(mode="python"), strict=True)


def project_retencion_soportada_list_result(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    /,
) -> RetencionSoportadaListProjection:
    """Release the stored records of one ejercicio only against a read-only receipt."""
    message = "suffered-withholding list result contradicts its terminal receipt"
    private = _execution_result(result)
    profile_id = _profile_from_receipt(receipt, definition_id=RETENCION_SOPORTADA_LIST_OPERATION_DEFINITION_ID)
    if (
        private.operation_id != "list"
        or private.outcome != "success"
        or private.profile_id != profile_id
        or private.rows is None
        or private.amount_columns is None
        or private.ejercicios is None
    ):
        raise ValueError(message)
    require_succeeded_terminal_receipt(
        receipt,
        definition_id=RETENCION_SOPORTADA_LIST_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        effect=OperationEffect.NONE,
        message=message,
    )
    return RetencionSoportadaListProjection(
        profile_id=profile_id,
        ejercicio=private.ejercicio,
        rows=private.rows,
        amount_columns=private.amount_columns,
        ejercicios=private.ejercicios,
    )


def _refusal_receipt_matches(receipt: OperationTerminalReceipt, code: str, definition_id: str) -> bool:
    return (
        receipt.condition is OperationTerminalCondition.REFUSED
        and receipt.effect is OperationEffect.NONE
        and receipt.refusal_ref == code
        and receipt.refusal_detail_ref is not None
        and refused_receipt_references_hold(receipt)
        and receipt.diagnostic_ref is None
        and receipt.identity.definition_id == definition_id
        and code in {RETENCION_SOPORTADA_WRITE_REFUSAL_CODE, RETENCION_SOPORTADA_REVISION_REFUSAL_CODE}
    )


def project_retencion_soportada_mutation_result(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    /,
) -> RetencionSoportadaMutationProjection:
    """Release one recorded or removed outcome, or its typed refusal that stored nothing."""
    message = "suffered-withholding mutation result contradicts its terminal receipt"
    private = _execution_result(result)
    definition_id = receipt.identity.definition_id
    profile_id = _profile_from_receipt(receipt, definition_id=definition_id)
    if _MUTATION_DEFINITIONS.get(private.operation_id) != definition_id or private.profile_id != profile_id:
        raise ValueError(message)
    if private.outcome == "refused":
        refusal = private.refusal
        if refusal is None or not _refusal_receipt_matches(receipt, refusal.code, definition_id):
            raise ValueError(message)
        return RetencionSoportadaMutationProjection(
            outcome="refused",
            profile_id=profile_id,
            ejercicio=private.ejercicio,
            refusal=refusal,
        )
    if private.count is None or (private.operation_id == "record") != (private.row is not None):
        raise ValueError(message)
    require_succeeded_terminal_receipt(
        receipt,
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(profile_id)),
        effect=OperationEffect.UPDATED,
        message=message,
    )
    return RetencionSoportadaMutationProjection(
        outcome="recorded" if private.operation_id == "record" else "removed",
        profile_id=profile_id,
        ejercicio=private.ejercicio,
        row=private.row,
        count=private.count,
    )
