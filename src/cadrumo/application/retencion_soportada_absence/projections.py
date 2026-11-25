"""Receipt-checked public projection for the suffered-withholding absence attestations."""

from __future__ import annotations

from typing import Final
from uuid import UUID

from pydantic import BaseModel

from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ..operations.models import (
    OperationTerminalReceipt,
    refused_receipt_references_hold,
    require_succeeded_terminal_receipt,
)
from .contracts import (
    RETENCION_SOPORTADA_ABSENCE_ATTEST_OPERATION_DEFINITION_ID,
    RETENCION_SOPORTADA_ABSENCE_LIST_OPERATION_DEFINITION_ID,
    RETENCION_SOPORTADA_ABSENCE_REFUSAL_CODES,
    RETENCION_SOPORTADA_ABSENCE_WITHDRAW_OPERATION_DEFINITION_ID,
)
from .results import (
    RetencionSoportadaAbsenceExecutionResult,
    RetencionSoportadaAbsenceListProjection,
    RetencionSoportadaAbsenceMutationProjection,
)

__all__ = ["project_retencion_soportada_absence_list_result", "project_retencion_soportada_absence_result"]

_DEFINITIONS: Final = {
    "attest": RETENCION_SOPORTADA_ABSENCE_ATTEST_OPERATION_DEFINITION_ID,
    "withdraw": RETENCION_SOPORTADA_ABSENCE_WITHDRAW_OPERATION_DEFINITION_ID,
}
_MESSAGE: Final = "suffered-withholding absence result contradicts its terminal receipt"


def _profile_from_receipt(receipt: OperationTerminalReceipt) -> UUID:
    subject = receipt.identity.subject_ref
    try:
        profile_id = UUID(subject.removeprefix("profile:"))
    except ValueError:
        raise ValueError(_MESSAGE) from None
    if subject != profile_operation_subject(str(profile_id)):
        raise ValueError(_MESSAGE)
    return profile_id


def _refusal_receipt_matches(receipt: OperationTerminalReceipt, code: str) -> bool:
    return (
        receipt.condition is OperationTerminalCondition.REFUSED
        and receipt.effect is OperationEffect.NONE
        and receipt.refusal_ref == code
        and receipt.refusal_detail_ref is not None
        and refused_receipt_references_hold(receipt)
        and receipt.diagnostic_ref is None
        and code in RETENCION_SOPORTADA_ABSENCE_REFUSAL_CODES
    )


def project_retencion_soportada_absence_list_result(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    /,
) -> RetencionSoportadaAbsenceListProjection:
    """Release the stored attestations of one ejercicio only against a read-only receipt."""
    if type(result) is not RetencionSoportadaAbsenceExecutionResult:
        raise ValueError(_MESSAGE)
    private = RetencionSoportadaAbsenceExecutionResult.model_validate(result.model_dump(mode="python"), strict=True)
    profile_id = _profile_from_receipt(receipt)
    if (
        receipt.identity.definition_id != RETENCION_SOPORTADA_ABSENCE_LIST_OPERATION_DEFINITION_ID
        or private.operation_id != "list"
        or private.outcome != "success"
        or private.profile_id != profile_id
        or private.attestations is None
        or any(row.ejercicio != private.ejercicio for row in private.attestations)
    ):
        raise ValueError(_MESSAGE)
    require_succeeded_terminal_receipt(
        receipt,
        definition_id=RETENCION_SOPORTADA_ABSENCE_LIST_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        effect=OperationEffect.NONE,
        message=_MESSAGE,
    )
    return RetencionSoportadaAbsenceListProjection(
        profile_id=profile_id, ejercicio=private.ejercicio, attestations=private.attestations
    )


def project_retencion_soportada_absence_result(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    /,
) -> RetencionSoportadaAbsenceMutationProjection:
    """Release one attested or withdrawn outcome, or its typed refusal that stored nothing."""
    if type(result) is not RetencionSoportadaAbsenceExecutionResult:
        raise ValueError(_MESSAGE)
    private = RetencionSoportadaAbsenceExecutionResult.model_validate(result.model_dump(mode="python"), strict=True)
    definition_id = receipt.identity.definition_id
    profile_id = _profile_from_receipt(receipt)
    if _DEFINITIONS.get(private.operation_id) != definition_id or private.profile_id != profile_id:
        raise ValueError(_MESSAGE)
    if private.outcome == "refused":
        refusal = private.refusal
        if refusal is None or not _refusal_receipt_matches(receipt, refusal.code):
            raise ValueError(_MESSAGE)
        return RetencionSoportadaAbsenceMutationProjection(
            outcome="refused", profile_id=profile_id, ejercicio=private.ejercicio, refusal=refusal
        )
    attestation = private.attestation
    if attestation is None or attestation.ejercicio != private.ejercicio:
        raise ValueError(_MESSAGE)
    require_succeeded_terminal_receipt(
        receipt,
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(profile_id)),
        effect=OperationEffect.UPDATED,
        message=_MESSAGE,
    )
    return RetencionSoportadaAbsenceMutationProjection(
        outcome="attested" if private.operation_id == "attest" else "withdrawn",
        profile_id=profile_id,
        ejercicio=private.ejercicio,
        attestation=attestation,
    )
