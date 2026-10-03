"""Compile closed spreadsheet projections against their terminal receipts."""

from __future__ import annotations

from pydantic import BaseModel

from ...core.hashing import canonical_json_bytes
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ..operations.models import OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..runtime.projection_pages import PROJECTION_DOCUMENT_MAX_BYTES
from .modelo_spreadsheet_access import resolve_modelo_spreadsheet_access
from .modelo_spreadsheet_operation_contracts import (
    MODELO_SPREADSHEET_CALCULATE_OPERATION_DEFINITION_ID,
    MODELO_SPREADSHEET_OPERATION_CONTRACTS,
    MODELO_SPREADSHEET_PULL_OPERATION_DEFINITION_ID,
    ModeloSpreadsheetExecutionResult,
    ModeloSpreadsheetOutcome,
    SpreadsheetOutputPathRefusal,
    SpreadsheetRefusal,
    spreadsheet_refusal_code,
)


def _expected_effect(definition_id: str) -> OperationEffect:
    if definition_id in {
        MODELO_SPREADSHEET_PULL_OPERATION_DEFINITION_ID,
        MODELO_SPREADSHEET_CALCULATE_OPERATION_DEFINITION_ID,
    }:
        return OperationEffect.NONE
    return OperationEffect.UPDATED


def _receipt_identity_matches(
    definition_id: str, result: ModeloSpreadsheetExecutionResult, receipt: OperationTerminalReceipt
) -> bool:
    return (
        receipt.identity.definition_id == definition_id
        and receipt.identity.subject_ref == profile_operation_subject(str(result.projection.profile_id))
        and result.effect == receipt.effect.value
        and receipt.failure_error_code is None
        and receipt.diagnostic_ref is None
    )


def _success_receipt_matches(receipt: OperationTerminalReceipt, expected_effect: OperationEffect) -> bool:
    return (
        receipt.condition is OperationTerminalCondition.SUCCEEDED
        and receipt.effect is expected_effect
        and receipt.result_ref is not None
        and receipt.refusal_ref is None
        and receipt.refusal_detail_ref is None
    )


def _refusal_receipt_matches(
    refusal: SpreadsheetRefusal | None,
    receipt: OperationTerminalReceipt,
    declared_codes: frozenset[str],
) -> bool:
    if refusal is None:
        return False
    return (
        receipt.condition is OperationTerminalCondition.REFUSED
        and receipt.refusal_ref in declared_codes
        and receipt.refusal_ref == spreadsheet_refusal_code(refusal)
        and receipt.refusal_detail_ref is not None
        and receipt.result_ref is None
        and receipt.effect in {OperationEffect.NONE, OperationEffect.UNKNOWN}
        and (receipt.effect is not OperationEffect.UNKNOWN or isinstance(refusal, SpreadsheetOutputPathRefusal))
    )


def _project_spreadsheet_result(
    definition_id: str,
    outcome_type: type[ModeloSpreadsheetOutcome],
    declared_codes: frozenset[str],
    result: BaseModel,
    receipt: OperationTerminalReceipt,
) -> BaseModel:
    if type(result) is not ModeloSpreadsheetExecutionResult or not isinstance(result, ModeloSpreadsheetExecutionResult):
        raise ValueError("invalid spreadsheet operation result")
    projection = result.projection
    if type(projection) is not outcome_type:
        raise ValueError("spreadsheet result has the wrong public projection")
    if not _receipt_identity_matches(definition_id, result, receipt):
        raise ValueError("spreadsheet result contradicts its terminal receipt")
    if projection.outcome == "succeeded":
        if not _success_receipt_matches(receipt, _expected_effect(definition_id)):
            raise ValueError("spreadsheet success has an incompatible receipt")
    elif not _refusal_receipt_matches(projection.refusal, receipt, declared_codes):
        raise ValueError("spreadsheet refusal has an incompatible receipt")
    validated = outcome_type.model_validate(projection.model_dump(mode="python"), strict=True)
    if len(canonical_json_bytes(validated.model_dump(mode="json"))) > PROJECTION_DOCUMENT_MAX_BYTES:
        raise ValueError("spreadsheet result exceeds its projection limit")
    return validated


def build_modelo_spreadsheet_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind exact request and result schemas to a terminal-receipt projector."""
    pair = MODELO_SPREADSHEET_OPERATION_CONTRACTS.get(definition.definition_id)
    if (
        pair is None
        or definition.request_type is not pair[0]
        or definition.result_type is not ModeloSpreadsheetExecutionResult
    ):
        raise ValueError("invalid spreadsheet definition contract")

    def project(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
        return _project_spreadsheet_result(
            definition.definition_id,
            pair[2],
            definition.refusal_detail_codes,
            result,
            receipt,
        )

    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=pair[2],
        result_projector=project,
        access_resolver=resolve_modelo_spreadsheet_access,
    )


__all__ = ["build_modelo_spreadsheet_registration"]
