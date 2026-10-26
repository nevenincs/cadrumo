"""Release validated Google results only through their matching terminal authority."""

from __future__ import annotations

from pydantic import BaseModel

from ...core.operations import OperationTerminalCondition, profile_operation_subject
from ..operations.interactions import OperationInteractionRequest
from ..operations.models import OperationTerminalReceipt
from .google_configuration_operation_contracts import (
    GOOGLE_CONFIGURATION_CONTRACTS,
    GoogleConfigurationExecutionResult,
    GoogleConsentProposal,
    GoogleConsentReviewProjection,
)
from .google_configuration_operation_refusal import GOOGLE_CONFIGURATION_REFUSAL_CODE


def _validated_execution_result(value: BaseModel) -> GoogleConfigurationExecutionResult:
    if type(value) is not GoogleConfigurationExecutionResult or not isinstance(
        value, GoogleConfigurationExecutionResult
    ):
        raise ValueError("invalid Google configuration execution result")
    return GoogleConfigurationExecutionResult.model_validate(value.model_dump(mode="python"), strict=True)


def _require_common_receipt(
    private: GoogleConfigurationExecutionResult,
    receipt: OperationTerminalReceipt,
) -> tuple[type[BaseModel], type[BaseModel]]:
    pair = GOOGLE_CONFIGURATION_CONTRACTS.get(receipt.identity.definition_id)
    projection = private.projection
    if (
        pair is None
        or private.identity != receipt.identity
        or receipt.identity.subject_ref != profile_operation_subject(str(projection.profile_id))
        or receipt.effect.value != private.effect
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
    ):
        raise ValueError("Google configuration outcome differs from its terminal receipt")
    return pair


def _require_success_receipt(
    private: GoogleConfigurationExecutionResult,
    projection_type: type[BaseModel],
    receipt: OperationTerminalReceipt,
) -> None:
    projection = private.projection
    if (
        projection.result is None
        or type(projection.result) is not projection_type
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.result_ref is None
        or receipt.refusal_ref is not None
        or receipt.refusal_detail_ref is not None
    ):
        raise ValueError("Google success differs from its terminal receipt")


def _require_refusal_receipt(private: GoogleConfigurationExecutionResult, receipt: OperationTerminalReceipt) -> None:
    projection = private.projection
    if (
        projection.refusal is None
        or receipt.condition is not OperationTerminalCondition.REFUSED
        or receipt.refusal_ref != GOOGLE_CONFIGURATION_REFUSAL_CODE
        or receipt.refusal_detail_ref is None
        or receipt.result_ref is not None
    ):
        raise ValueError("Google refusal differs from its terminal receipt")


def project_google_configuration_result(value: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release complete human facts only from the exact invocation/effect receipt."""
    private = _validated_execution_result(value)
    _request_type, projection_type = _require_common_receipt(private, receipt)
    if private.projection.outcome == "succeeded":
        _require_success_receipt(private, projection_type, receipt)
    else:
        _require_refusal_receipt(private, receipt)
    return private.projection


def project_google_consent_review(value: BaseModel, interaction: OperationInteractionRequest, /) -> BaseModel:
    """Disclose only the exact profile/revision proposal acknowledged by this terminal."""
    if type(value) is not GoogleConsentProposal or not isinstance(value, GoogleConsentProposal):
        raise ValueError("invalid Google consent proposal")
    proposal = GoogleConsentProposal.model_validate(value.model_dump(mode="python"), strict=True)
    if (
        proposal.identity != interaction.identity
        or proposal.revision != interaction.revision
        or proposal.digest != interaction.continuation_digest
    ):
        raise ValueError("Google consent proposal differs from its interaction")
    return GoogleConsentReviewProjection(
        identity=proposal.identity,
        revision=proposal.revision,
        profile_id=proposal.request.profile_id,
        reviewed_proposal_digest=proposal.digest,
    )


__all__ = ["project_google_configuration_result", "project_google_consent_review"]
