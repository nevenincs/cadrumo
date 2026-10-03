"""Censal public contracts, review documents, and terminal results."""

from __future__ import annotations

from typing import cast
from uuid import UUID, uuid4

from pydantic import BaseModel, JsonValue, ValidationError

from ....adapters.local_runtime.frontend_client import (
    RuntimeFrontendClient,
    RuntimeFrontendRefusedError,
)
from ....application.operations.frontend_projection import OperationReviewAvailableInteractionV1
from ....application.operations.frontend_requests import (
    OperationObservationSuccessV1,
    OperationResultProjectionRefusalV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
    OperationReviewProjectionRefusalV1,
    OperationReviewProjectionRequestV1,
    OperationReviewProjectionSuccessV1,
)
from ....application.operations.models import OperationId
from ....application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionContractV1,
    OperationSchemaIdentityV1,
)
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....application.runtime.deadline_budget import remaining_budget
from ....application.runtime.operation_access import (
    RuntimeOperationProjected,
    RuntimeOperationReview,
)
from ....application.user_profile.censal_operation import (
    CENSAL_OPERATION_DEFINITION_ID,
    CENSAL_REVIEW_PROJECTION_SCHEMA_BINDING,
    CENSAL_REVIEW_RESPONSE_SCHEMA_BINDING,
    CensalOperationOutcome,
    CensalOperationRequest,
    CensalOperationResult,
    CensalReviewProjectionV1,
)
from ....core.hashing import canonical_json_bytes
from ....core.operations import OperationEffect, OperationLifecycle, OperationTerminalCondition
from .runtime_censal_exchange import _exchange


def _decode_censal_terminal(
    document: dict[str, JsonValue],
) -> OperationResultProjectionSuccessV1[CensalOperationResult]:
    """Decode censal terminal."""
    encoded = canonical_json_bytes(document)
    try:
        if document.get("outcome") == "refused":
            refusal = OperationResultProjectionRefusalV1.model_validate_json(encoded)
            raise RuntimeFrontendRefusedError(refusal.code.value)
        success_type = cast(
            "type[OperationResultProjectionSuccessV1[CensalOperationResult]]",
            OperationResultProjectionSuccessV1.__class_getitem__(CensalOperationResult),
        )
        success = success_type.model_validate_json(encoded)
    except (TypeError, ValueError, ValidationError, RecursionError):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) from None
    return success


def _require_censal_terminal_result(
    success: OperationResultProjectionSuccessV1[CensalOperationResult],
    contract: OperationPublicDefinitionContractV1,
    expected_outcome: CensalOperationOutcome,
    review: CensalReviewProjectionV1,
) -> None:
    """Require censal terminal result."""
    if (
        success.result_schema != contract.result_schema
        or success.definition_contract_digest != contract.definition_contract_digest
        or success.projection.outcome is not expected_outcome
        or success.projection.reviewed_proposal_digest != review.reviewed_proposal_digest
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)


def _expected_schema(
    *,
    definition_id: str,
    suffix: str,
    model_type: type[BaseModel],
) -> OperationSchemaIdentityV1:
    return OperationSchemaIdentityV1.from_model(
        schema_id=f"{definition_id}.{suffix}",
        schema_version=1,
        model_type=model_type,
    )


def _validate_contract(
    client: RuntimeFrontendClient, request: CensalOperationRequest, deadline: float
) -> OperationPublicDefinitionContractV1:
    contract = client.contract(CENSAL_OPERATION_DEFINITION_ID, deadline=deadline)
    expected_request = _expected_schema(
        definition_id=CENSAL_OPERATION_DEFINITION_ID,
        suffix="request",
        model_type=CensalOperationRequest,
    )
    expected_result = _expected_schema(
        definition_id=CENSAL_OPERATION_DEFINITION_ID,
        suffix="result",
        model_type=CensalOperationResult,
    )
    if (
        contract.definition_id != CENSAL_OPERATION_DEFINITION_ID
        or contract.request_schema != expected_request
        or contract.result_schema != expected_result
        or contract.review_projection_schema != CENSAL_REVIEW_PROJECTION_SCHEMA_BINDING.identity
        or contract.interaction_response_schema != CENSAL_REVIEW_RESPONSE_SCHEMA_BINDING.identity
        or client.frontend not in contract.permitted_frontends
        or client.frontend is not OperationFrontendProjection.CLI
        or contract.ephemeral_secret_required
        or request.baseline.profile_id != str(client.profile_id)
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return contract


def _resolve_review(
    client: RuntimeFrontendClient,
    *,
    profile_id: UUID,
    session_id: UUID,
    operation_id: OperationId,
    pending: OperationReviewAvailableInteractionV1,
    deadline: float,
    contract: OperationPublicDefinitionContractV1,
) -> CensalReviewProjectionV1:
    request = RuntimeOperationReview(
        request_id=uuid4(),
        profile_id=profile_id,
        session_id=session_id,
        review=OperationReviewProjectionRequestV1(reference=pending.review_reference),
    )
    reply = _exchange(client, session_id, request, deadline=deadline)
    if (
        not isinstance(reply, RuntimeOperationProjected)
        or reply.operation_id != operation_id
        or reply.projection_kind != "review"
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    encoded = canonical_json_bytes(reply.document)
    try:
        if reply.document.get("outcome") == "refused":
            refusal = OperationReviewProjectionRefusalV1.model_validate_json(encoded)
            raise RuntimeFrontendRefusedError(refusal.code.value)
        success_type = cast(
            "type[OperationReviewProjectionSuccessV1[CensalReviewProjectionV1]]",
            OperationReviewProjectionSuccessV1.__class_getitem__(CensalReviewProjectionV1),
        )
        success = success_type.model_validate_json(encoded)
    except (TypeError, ValueError, ValidationError, RecursionError):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) from None
    if (
        success.projection_schema != contract.review_projection_schema
        or success.definition_contract_digest != contract.definition_contract_digest
        or not isinstance(success.projection, CensalReviewProjectionV1)
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return success.projection


def _validate_terminal(
    client: RuntimeFrontendClient,
    observed: OperationObservationSuccessV1,
    *,
    contract: OperationPublicDefinitionContractV1,
    review: CensalReviewProjectionV1,
    apply: bool,
    deadline: float,
) -> None:
    expected_outcome = CensalOperationOutcome.APPLIED if apply else CensalOperationOutcome.REJECTED
    permitted_effects = {OperationEffect.UPDATED} if apply else {OperationEffect.NONE, OperationEffect.UPDATED}
    projection = observed.projection
    if (
        projection.lifecycle is not OperationLifecycle.TERMINAL
        or projection.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or projection.effect not in permitted_effects
        or projection.result_ref is None
        or contract.result_schema is None
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    document = client.read_result_document(
        OperationResultProjectionRequestV1(
            operation_id=projection.operation_id,
            terminal_revision=projection.revision,
            definition_contract_digest=contract.definition_contract_digest,
            result_schema=contract.result_schema,
        ),
        timeout=remaining_budget(deadline),
        deadline=deadline,
    )
    success = _decode_censal_terminal(document)
    _require_censal_terminal_result(success, contract, expected_outcome, review)
