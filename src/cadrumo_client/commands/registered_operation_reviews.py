"""Decode and decide typed registered CLI reviews with exact pending-reference guards."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import cast
from uuid import UUID, uuid4

from pydantic import BaseModel

from cadrumo.application.operations.frontend_projection import (
    OperationPublicProjectionV1,
    OperationReviewAvailableInteractionV1,
)
from cadrumo.application.operations.frontend_requests import (
    OperationResponseApplyRequestV1,
    OperationResponseRejectRequestV1,
    OperationReviewProjectionRefusalV1,
    OperationReviewProjectionRequestV1,
    OperationReviewProjectionSuccessV1,
)
from cadrumo.application.operations.models import OperationId
from cadrumo.application.operations.registry import (
    OperationPublicDefinitionContractV1,
)
from cadrumo.core.hashing import canonical_json_bytes
from cadrumo.core.time.clock import now
from cadrumo_client.commands.registered_operation_contracts import (
    RegisteredOperationReviewCompletion,
    RegisteredOperationReviewHandler,
)
from cadrumo_client.commands.registered_operation_responses import (
    detach_registered_review,
    require_registered_response_control,
    submit_registered_review_response,
)
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.operation_access import (
    OperationProjected,
    OperationReply,
    OperationRequest,
    OperationReview,
)
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError


def require_registered_pending_review[ReviewT: BaseModel](
    pending: OperationReviewAvailableInteractionV1,
    state: OperationPublicProjectionV1,
    operation_id: OperationId,
    review: RegisteredOperationReviewHandler[ReviewT],
    contract: OperationPublicDefinitionContractV1,
) -> None:
    """Require every pending review reference and schema coordinate before any operator decision."""
    reference = pending.review_reference
    if (
        pending.operation_id != operation_id
        or pending.revision != state.revision
        or pending.response_schema != review.response_schema
        or reference.operation_id != operation_id
        or reference.interaction_id != pending.interaction_id
        or reference.revision != pending.revision
        or reference.review_projection_schema != review.review_schema
        or reference.definition_contract_digest != contract.definition_contract_digest
    ):
        raise RefusalError(RefusalCode.INVALID_FRAME)


def respond_registered_pending_review[ReviewT: BaseModel](
    state: OperationPublicProjectionV1,
    operation_id: OperationId,
    review: RegisteredOperationReviewHandler[ReviewT] | None,
    contract: OperationPublicDefinitionContractV1,
    profile_id: UUID,
    session_id: UUID,
    responded_interactions: set[tuple[str, int]],
    exchange: Callable[[OperationRequest], OperationReply],
) -> RegisteredOperationReviewCompletion[ReviewT] | None:
    """Respond once to the exact pending review, retaining an undecided detached review."""
    pending = state.pending_interaction
    if review is None or not isinstance(pending, OperationReviewAvailableInteractionV1):
        raise RefusalError(RefusalCode.INVALID_FRAME)
    require_registered_pending_review(pending, state, operation_id, review, contract)
    interaction = (pending.interaction_id, pending.revision)
    if interaction not in responded_interactions:
        detached_review = handle_registered_review(
            review,
            pending,
            contract=contract,
            profile_id=profile_id,
            session_id=session_id,
            exchange=exchange,
        )
        if detached_review is not None:
            return RegisteredOperationReviewCompletion(
                operation_id=operation_id,
                review=detached_review,
                effect=state.effect,
            )
        responded_interactions.add(interaction)
    return None


def registered_review_projection[ReviewT: BaseModel](
    document: Mapping[str, object],
    handler: RegisteredOperationReviewHandler[ReviewT],
    contract: OperationPublicDefinitionContractV1,
) -> ReviewT:
    """Decode the exact typed review and correlate its schema and defining contract."""
    encoded = canonical_json_bytes(document)
    if document.get("outcome") == "refused":
        refusal = OperationReviewProjectionRefusalV1.model_validate_json(encoded)
        raise FrontendRefusedError(refusal.code.value)
    success_type = cast(
        "type[OperationReviewProjectionSuccessV1[ReviewT]]",
        OperationReviewProjectionSuccessV1.__class_getitem__(handler.review_type),
    )
    success = success_type.model_validate_json(encoded)
    if (
        success.projection_schema != handler.review_schema
        or success.definition_contract_digest != contract.definition_contract_digest
    ):
        raise RefusalError(RefusalCode.INVALID_FRAME)
    return success.projection


def handle_registered_review[ReviewT: BaseModel](
    handler: RegisteredOperationReviewHandler[ReviewT],
    pending: OperationReviewAvailableInteractionV1,
    *,
    contract: OperationPublicDefinitionContractV1,
    profile_id: UUID,
    session_id: UUID,
    exchange: Callable[[OperationRequest], OperationReply],
) -> ReviewT | None:
    """Read the review and execute its explicit apply, reject or detach decision."""
    request: OperationRequest = OperationReview(
        request_id=uuid4(),
        profile_id=profile_id,
        session_id=session_id,
        review=OperationReviewProjectionRequestV1(reference=pending.review_reference),
    )
    reply = exchange(request)
    if (
        not isinstance(reply, OperationProjected)
        or reply.operation_id != pending.operation_id
        or reply.projection_kind != "review"
    ):
        raise RefusalError(RefusalCode.INVALID_FRAME)
    review = registered_review_projection(reply.document, handler, contract)
    if handler.validate_reference is not None:
        handler.validate_reference(review, pending.review_reference)
    decision = handler.decide(review)
    if decision is None:
        return detach_registered_review(review, pending, profile_id, session_id, exchange)
    if decision not in ("apply", "reject"):
        raise RefusalError(RefusalCode.INVALID_FRAME)
    actor_ref = require_registered_response_control(pending, profile_id, session_id, decision, exchange)
    if decision == "apply":
        mutation = OperationResponseApplyRequestV1(
            operation_id=pending.operation_id,
            interaction_id=pending.interaction_id,
            revision=pending.revision,
            actor_ref=actor_ref,
            responded_at=now(),
        )
    else:
        mutation = OperationResponseRejectRequestV1(
            operation_id=pending.operation_id,
            interaction_id=pending.interaction_id,
            revision=pending.revision,
            actor_ref=actor_ref,
            responded_at=now(),
            reason_code=handler.reject_reason_code,
        )
    submit_registered_review_response(pending, profile_id, session_id, decision, mutation, exchange)
    return None
