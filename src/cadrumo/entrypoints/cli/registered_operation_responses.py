"""Detach, authorize and correlate exact registered operator review responses."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel

from ...adapters.local_runtime.frontend_client import RuntimeFrontendRefusedError
from ...application.operations.frontend_projection import (
    OperationReviewAvailableInteractionV1,
)
from ...application.operations.frontend_requests import (
    OperationDetachRefusalV1,
    OperationDetachRequestV1,
    OperationDetachSuccessV1,
    OperationResponseApplyRequestV1,
    OperationResponseControlRefusalV1,
    OperationResponseControlRequestV1,
    OperationResponseControlSuccessV1,
    OperationResponseMutationSuccessV1,
    OperationResponseRejectRequestV1,
)
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.operation_access import (
    RuntimeOperationManage,
    RuntimeOperationManaged,
    RuntimeOperationReply,
    RuntimeOperationRequest,
)
from ...application.user_profile.access_contracts import AccessDenialCode
from ...core.hashing import canonical_json_bytes


def detach_registered_review[ReviewT: BaseModel](
    review: ReviewT,
    pending: OperationReviewAvailableInteractionV1,
    profile_id: UUID,
    session_id: UUID,
    exchange: Callable[[RuntimeOperationRequest], RuntimeOperationReply],
) -> ReviewT:
    """Detach the exact pending review when the operator leaves it undecided."""
    request = RuntimeOperationManage(
        request_id=uuid4(),
        profile_id=profile_id,
        session_id=session_id,
        management=OperationDetachRequestV1(operation_id=pending.operation_id, expected_revision=pending.revision),
    )
    reply = exchange(request)
    if not isinstance(reply, RuntimeOperationManaged) or reply.operation_id != pending.operation_id:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    encoded = canonical_json_bytes(reply.document)
    if reply.document.get("outcome") == "refused":
        refusal = OperationDetachRefusalV1.model_validate_json(encoded)
        raise RuntimeFrontendRefusedError(refusal.code.value)
    detached = OperationDetachSuccessV1.model_validate_json(encoded)
    if detached.operation_id != pending.operation_id or detached.revision < pending.revision:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return review


def require_registered_response_control(
    pending: OperationReviewAvailableInteractionV1,
    profile_id: UUID,
    session_id: UUID,
    decision: Literal["apply", "reject"],
    exchange: Callable[[RuntimeOperationRequest], RuntimeOperationReply],
) -> str:
    """Require correlated response authority before mutating a pending review."""
    actor_ref = f"session:{session_id}"
    request = RuntimeOperationManage(
        request_id=uuid4(),
        profile_id=profile_id,
        session_id=session_id,
        management=OperationResponseControlRequestV1(
            operation_id=pending.operation_id,
            interaction_id=pending.interaction_id,
            revision=pending.revision,
            actor_ref=actor_ref,
        ),
    )
    reply = exchange(request)
    if not isinstance(reply, RuntimeOperationManaged) or reply.operation_id != pending.operation_id:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    encoded = canonical_json_bytes(reply.document)
    if reply.document.get("outcome") == "refused":
        refusal = OperationResponseControlRefusalV1.model_validate_json(encoded)
        raise RuntimeFrontendRefusedError(refusal.code.value)
    control = OperationResponseControlSuccessV1.model_validate_json(encoded)
    if (
        control.operation_id != pending.operation_id
        or control.interaction_id != pending.interaction_id
        or control.revision != pending.revision
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    if not control.available or decision not in control.permitted_intents:
        raise RuntimeFrontendRefusedError(AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED.value)
    return actor_ref


def submit_registered_review_response(
    pending: OperationReviewAvailableInteractionV1,
    profile_id: UUID,
    session_id: UUID,
    decision: Literal["apply", "reject"],
    mutation: OperationResponseApplyRequestV1 | OperationResponseRejectRequestV1,
    exchange: Callable[[RuntimeOperationRequest], RuntimeOperationReply],
) -> None:
    """Submit and correlate the exact accepted operator response."""
    request = RuntimeOperationManage(
        request_id=uuid4(), profile_id=profile_id, session_id=session_id, management=mutation
    )
    reply = exchange(request)
    if not isinstance(reply, RuntimeOperationManaged) or reply.operation_id != pending.operation_id:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    encoded = canonical_json_bytes(reply.document)
    if reply.document.get("outcome") == "refused":
        refusal = OperationResponseControlRefusalV1.model_validate_json(encoded)
        raise RuntimeFrontendRefusedError(refusal.code.value)
    accepted = OperationResponseMutationSuccessV1.model_validate_json(encoded)
    if (
        accepted.operation_id != pending.operation_id
        or accepted.interaction_id != pending.interaction_id
        or accepted.revision != pending.revision
        or accepted.response_action != decision
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
