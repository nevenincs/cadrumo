"""Canonical google consent response stages for the human terminal."""

from __future__ import annotations

from uuid import UUID, uuid4

from cadrumo.application.operations.frontend_projection import (
    OperationReviewAvailableInteractionV1,
)
from cadrumo.application.operations.frontend_requests import (
    OperationResponseApplyRequestV1,
    OperationResponseControlRefusalV1,
    OperationResponseControlRequestV1,
    OperationResponseControlSuccessV1,
    OperationResponseMutationSuccessV1,
    OperationResponseRejectRequestV1,
)
from cadrumo.core.hashing import canonical_json_bytes
from cadrumo.core.time.clock import now
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.operation_access import (
    OperationManage,
    OperationManaged,
    OperationReply,
)
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

from .google_consent_exchange import google_consent_exchange


def admit_google_response_control(
    reply: OperationReply, pending: OperationReviewAvailableInteractionV1, apply: bool
) -> str:
    """Admit google response control."""
    if not isinstance(reply, OperationManaged) or reply.operation_id != pending.operation_id:
        raise RefusalError(RefusalCode.INVALID_FRAME)
    if reply.document.get("outcome") == "refused":
        refusal = OperationResponseControlRefusalV1.model_validate_json(canonical_json_bytes(reply.document))
        raise FrontendRefusedError(refusal.code.value)
    control = OperationResponseControlSuccessV1.model_validate_json(canonical_json_bytes(reply.document))
    intent = "apply" if apply else "reject"
    if (
        control.operation_id != pending.operation_id
        or control.interaction_id != pending.interaction_id
        or control.revision != pending.revision
        or not control.available
        or intent not in control.permitted_intents
    ):
        raise RefusalError(RefusalCode.INVALID_FRAME)
    return intent


def validate_google_response_mutation(
    reply: OperationReply, pending: OperationReviewAvailableInteractionV1, intent: str
) -> None:
    """Validate google response mutation."""
    if not isinstance(reply, OperationManaged) or reply.operation_id != pending.operation_id:
        raise RefusalError(RefusalCode.INVALID_FRAME)
    if reply.document.get("outcome") == "refused":
        refusal = OperationResponseControlRefusalV1.model_validate_json(canonical_json_bytes(reply.document))
        raise FrontendRefusedError(refusal.code.value)
    accepted = OperationResponseMutationSuccessV1.model_validate_json(canonical_json_bytes(reply.document))
    if (
        accepted.operation_id != pending.operation_id
        or accepted.interaction_id != pending.interaction_id
        or accepted.revision != pending.revision
        or accepted.response_action != intent
    ):
        raise RefusalError(RefusalCode.INVALID_FRAME)


def respond_google_consent(
    client: FrontendClient,
    profile_id: UUID,
    session_id: UUID,
    pending: OperationReviewAvailableInteractionV1,
    *,
    apply: bool,
    deadline: float,
) -> None:
    """Apply or reject only the available response for this exact review revision."""
    actor_ref = f"session:{session_id}"
    reply = google_consent_exchange(
        client,
        profile_id,
        session_id,
        OperationManage(
            request_id=uuid4(),
            profile_id=profile_id,
            session_id=session_id,
            management=OperationResponseControlRequestV1(
                operation_id=pending.operation_id,
                interaction_id=pending.interaction_id,
                revision=pending.revision,
                actor_ref=actor_ref,
            ),
        ),
        deadline,
    )
    intent = admit_google_response_control(reply, pending, apply)
    if apply:
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
            reason_code="google.consent.terminal-unavailable",
        )
    reply = google_consent_exchange(
        client,
        profile_id,
        session_id,
        OperationManage(
            request_id=uuid4(),
            profile_id=profile_id,
            session_id=session_id,
            management=mutation,
        ),
        deadline,
    )
    validate_google_response_mutation(reply, pending, intent)
