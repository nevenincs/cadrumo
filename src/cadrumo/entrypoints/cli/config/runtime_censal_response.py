"""Censal response authority, explicit decisions, and mutation receipts."""

from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import JsonValue, ValidationError

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from ....application.operations.frontend_projection import OperationReviewAvailableInteractionV1
from ....application.operations.frontend_requests import (
    OperationResponseApplyRequestV1,
    OperationResponseControlRefusalV1,
    OperationResponseControlRequestV1,
    OperationResponseControlSuccessV1,
    OperationResponseMutationSuccessV1,
    OperationResponseRejectRequestV1,
)
from ....application.operations.models import OperationId
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....application.runtime.operation_access import (
    RuntimeOperationManage,
    RuntimeOperationManaged,
)
from ....application.user_profile.access_contracts import AccessDenialCode
from ....core.hashing import canonical_json_bytes
from ....core.time.clock import now
from .runtime_censal_exchange import _exchange


def _require_response_authority(
    client: RuntimeFrontendClient,
    profile_id: UUID,
    session_id: UUID,
    operation_id: OperationId,
    pending: OperationReviewAvailableInteractionV1,
    actor_ref: str,
    apply: bool,
    deadline: float,
) -> str:
    """Require response authority."""
    control_request = OperationResponseControlRequestV1(
        operation_id=operation_id,
        interaction_id=pending.interaction_id,
        revision=pending.revision,
        actor_ref=actor_ref,
    )
    control_wire_request = RuntimeOperationManage(
        request_id=uuid4(),
        profile_id=profile_id,
        session_id=session_id,
        management=control_request,
    )
    control_reply = _exchange(client, session_id, control_wire_request, deadline=deadline)
    if not isinstance(control_reply, RuntimeOperationManaged) or control_reply.operation_id != operation_id:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    control = _decode_response_control(control_reply.document)
    expected_intent = "apply" if apply else "reject"
    if (
        control.operation_id != operation_id
        or control.interaction_id != pending.interaction_id
        or control.revision != pending.revision
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    if not control.available or expected_intent not in control.permitted_intents:
        raise RuntimeFrontendRefusedError(AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED.value)
    return expected_intent


def _decode_response_control(document: dict[str, JsonValue]) -> OperationResponseControlSuccessV1:
    encoded = canonical_json_bytes(document)
    try:
        if document.get("outcome") == "refused":
            refusal = OperationResponseControlRefusalV1.model_validate_json(encoded)
            raise RuntimeFrontendRefusedError(refusal.code.value)
        return OperationResponseControlSuccessV1.model_validate_json(encoded)
    except (TypeError, ValueError, ValidationError, RecursionError):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) from None


def _decode_response_mutation(document: dict[str, JsonValue]) -> OperationResponseMutationSuccessV1:
    encoded = canonical_json_bytes(document)
    try:
        if document.get("outcome") == "refused":
            refusal = OperationResponseControlRefusalV1.model_validate_json(encoded)
            raise RuntimeFrontendRefusedError(refusal.code.value)
        return OperationResponseMutationSuccessV1.model_validate_json(encoded)
    except (TypeError, ValueError, ValidationError, RecursionError):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) from None


def _respond(
    client: RuntimeFrontendClient,
    *,
    profile_id: UUID,
    session_id: UUID,
    operation_id: OperationId,
    pending: OperationReviewAvailableInteractionV1,
    apply: bool,
    deadline: float,
) -> None:
    actor_ref = f"session:{session_id}"
    expected_intent = _require_response_authority(
        client, profile_id, session_id, operation_id, pending, actor_ref, apply, deadline
    )

    responded_at = now()
    if apply:
        mutation = OperationResponseApplyRequestV1(
            operation_id=operation_id,
            interaction_id=pending.interaction_id,
            revision=pending.revision,
            actor_ref=actor_ref,
            responded_at=responded_at,
        )
    else:
        mutation = OperationResponseRejectRequestV1(
            operation_id=operation_id,
            interaction_id=pending.interaction_id,
            revision=pending.revision,
            actor_ref=actor_ref,
            responded_at=responded_at,
            reason_code="censo.review.operator-rejected",
        )
    mutation_wire_request = RuntimeOperationManage(
        request_id=uuid4(),
        profile_id=profile_id,
        session_id=session_id,
        management=mutation,
    )
    mutation_reply = _exchange(client, session_id, mutation_wire_request, deadline=deadline)
    if not isinstance(mutation_reply, RuntimeOperationManaged) or mutation_reply.operation_id != operation_id:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    accepted = _decode_response_mutation(mutation_reply.document)
    if (
        accepted.operation_id != operation_id
        or accepted.interaction_id != pending.interaction_id
        or accepted.revision != pending.revision
        or accepted.response_action != expected_intent
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
