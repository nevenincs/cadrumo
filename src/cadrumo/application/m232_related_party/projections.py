"""Receipt-checked public projections for the Modelo 232 related-party statements."""

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
    M232_RELATED_PARTY_LIST_OPERATION_DEFINITION_ID,
    M232_RELATED_PARTY_NONE_STATE_OPERATION_DEFINITION_ID,
    M232_RELATED_PARTY_NONE_WITHDRAW_OPERATION_DEFINITION_ID,
    M232_RELATED_PARTY_OPERATION_STATE_OPERATION_DEFINITION_ID,
    M232_RELATED_PARTY_OPERATION_WITHDRAW_OPERATION_DEFINITION_ID,
    M232_RELATED_PARTY_REFUSAL_CODES,
    M232_RELATED_PARTY_TURNOVER_STATE_OPERATION_DEFINITION_ID,
    M232_RELATED_PARTY_TURNOVER_WITHDRAW_OPERATION_DEFINITION_ID,
)
from .results import (
    Modelo232RelatedPartyExecutionResult,
    Modelo232RelatedPartyListProjection,
    Modelo232RelatedPartyMutationProjection,
)

__all__ = ["project_m232_related_party_list_result", "project_m232_related_party_result"]

_DEFINITIONS: Final = {
    "state_operation": M232_RELATED_PARTY_OPERATION_STATE_OPERATION_DEFINITION_ID,
    "withdraw_operation": M232_RELATED_PARTY_OPERATION_WITHDRAW_OPERATION_DEFINITION_ID,
    "state_none": M232_RELATED_PARTY_NONE_STATE_OPERATION_DEFINITION_ID,
    "withdraw_none": M232_RELATED_PARTY_NONE_WITHDRAW_OPERATION_DEFINITION_ID,
    "state_turnover": M232_RELATED_PARTY_TURNOVER_STATE_OPERATION_DEFINITION_ID,
    "withdraw_turnover": M232_RELATED_PARTY_TURNOVER_WITHDRAW_OPERATION_DEFINITION_ID,
}
_MESSAGE: Final = "Modelo 232 related-party result contradicts its terminal receipt"


def _private(result: BaseModel) -> Modelo232RelatedPartyExecutionResult:
    if type(result) is not Modelo232RelatedPartyExecutionResult:
        raise ValueError(_MESSAGE)
    return Modelo232RelatedPartyExecutionResult.model_validate(result.model_dump(mode="python"), strict=True)


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
        and code in M232_RELATED_PARTY_REFUSAL_CODES
    )


def project_m232_related_party_list_result(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    /,
) -> Modelo232RelatedPartyListProjection:
    """Release the statements of one ejercicio and their verdict only against a read-only receipt."""
    private = _private(result)
    profile_id = _profile_from_receipt(receipt)
    year = private.year
    if (
        receipt.identity.definition_id != M232_RELATED_PARTY_LIST_OPERATION_DEFINITION_ID
        or private.operation_id != "list"
        or private.outcome != "success"
        or private.profile_id != profile_id
        or year is None
        or any(
            row.ejercicio != private.ejercicio
            for row in (*year.operations, *year.none_statements, *year.turnover_statements)
        )
    ):
        raise ValueError(_MESSAGE)
    require_succeeded_terminal_receipt(
        receipt,
        definition_id=M232_RELATED_PARTY_LIST_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        effect=OperationEffect.NONE,
        message=_MESSAGE,
    )
    return Modelo232RelatedPartyListProjection(profile_id=profile_id, ejercicio=private.ejercicio, year=year)


def project_m232_related_party_result(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    /,
) -> Modelo232RelatedPartyMutationProjection:
    """Release one stated or withdrawn payload, or its typed refusal that stored nothing."""
    private = _private(result)
    definition_id = receipt.identity.definition_id
    profile_id = _profile_from_receipt(receipt)
    if _DEFINITIONS.get(private.operation_id) != definition_id or private.profile_id != profile_id:
        raise ValueError(_MESSAGE)
    if private.outcome == "refused":
        refusal = private.refusal
        if (
            refusal is None
            or refusal.ejercicio != private.ejercicio
            or not _refusal_receipt_matches(receipt, refusal.code)
        ):
            raise ValueError(_MESSAGE)
        return Modelo232RelatedPartyMutationProjection(
            outcome="refused", profile_id=profile_id, ejercicio=private.ejercicio, refusal=refusal
        )
    stated = private.operation or private.none_statement or private.turnover_statement
    if stated is None or stated.ejercicio != private.ejercicio:
        raise ValueError(_MESSAGE)
    require_succeeded_terminal_receipt(
        receipt,
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(profile_id)),
        effect=OperationEffect.UPDATED,
        message=_MESSAGE,
    )
    return Modelo232RelatedPartyMutationProjection(
        outcome="stated" if private.operation_id.startswith("state_") else "withdrawn",
        profile_id=profile_id,
        ejercicio=private.ejercicio,
        operation=private.operation,
        none_statement=private.none_statement,
        turnover_statement=private.turnover_statement,
    )
