"""Canonical google consent review stages for the human terminal."""

from __future__ import annotations

from contextlib import suppress
from typing import cast
from uuid import UUID, uuid4

from pydantic import ValidationError

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from ....adapters.outbound.google.errors import GoogleAuthNonInteractiveError
from ....adapters.outbound.google.oauth_flow import require_interactive_terminal
from ....application.operations.frontend_projection import (
    OperationPublicProjectionV1,
    OperationReviewAvailableInteractionV1,
)
from ....application.operations.frontend_requests import (
    OperationReviewProjectionRefusalV1,
    OperationReviewProjectionRequestV1,
    OperationReviewProjectionSuccessV1,
)
from ....application.operations.models import OperationIdentity
from ....application.operations.registry import (
    OperationPublicDefinitionContractV1,
)
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....application.runtime.operation_access import (
    RuntimeOperationProjected,
    RuntimeOperationReview,
)
from ....application.user_profile.google_configuration_operation_contracts import (
    GOOGLE_CONSENT_PRESENTATION_CODE,
    GOOGLE_LOGIN_OPERATION_DEFINITION_ID,
    GoogleConsentProposal,
    GoogleConsentReviewProjection,
    GoogleLoginRequest,
)
from ....core.hashing import canonical_json_bytes
from ....core.operations import (
    profile_operation_subject,
)
from .google_consent_exchange import google_consent_exchange
from .google_consent_response import respond_google_consent


def validate_google_consent_review(
    reply: RuntimeOperationProjected,
    pending: OperationReviewAvailableInteractionV1,
    profile_id: UUID,
    request: GoogleLoginRequest,
    contract: OperationPublicDefinitionContractV1,
) -> None:
    """Validate google consent review."""
    # CAST-RATIONALE-GOOGLE-CONSENT-REVIEW: bind the exact public review type.
    success_type = cast(
        "type[OperationReviewProjectionSuccessV1[GoogleConsentReviewProjection]]",
        OperationReviewProjectionSuccessV1.__class_getitem__(GoogleConsentReviewProjection),
    )
    success = success_type.model_validate_json(canonical_json_bytes(reply.document))
    proposal = GoogleConsentProposal(
        identity=OperationIdentity(
            operation_id=pending.operation_id,
            definition_id=GOOGLE_LOGIN_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(profile_id)),
        ),
        revision=pending.revision,
        request=request,
    )
    if (
        success.projection_schema != contract.review_projection_schema
        or success.definition_contract_digest != contract.definition_contract_digest
        or success.projection.identity != proposal.identity
        or success.projection.revision != pending.revision
        or success.projection.profile_id != profile_id
        or success.projection.reviewed_proposal_digest != proposal.digest
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)


def review_google_consent(
    client: RuntimeFrontendClient,
    profile_id: UUID,
    session_id: UUID,
    pending: OperationReviewAvailableInteractionV1,
    request: GoogleLoginRequest,
    contract: OperationPublicDefinitionContractV1,
    deadline: float,
) -> None:
    """Verify the proposal before requiring and acknowledging the human terminal."""
    if (
        pending.presentation_code != GOOGLE_CONSENT_PRESENTATION_CODE
        or pending.response_schema != contract.interaction_response_schema
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    reply = google_consent_exchange(
        client,
        profile_id,
        session_id,
        RuntimeOperationReview(
            request_id=uuid4(),
            profile_id=profile_id,
            session_id=session_id,
            review=OperationReviewProjectionRequestV1(reference=pending.review_reference),
        ),
        deadline,
    )
    if (
        not isinstance(reply, RuntimeOperationProjected)
        or reply.operation_id != pending.operation_id
        or reply.projection_kind != "review"
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    if reply.document.get("outcome") == "refused":
        refusal = OperationReviewProjectionRefusalV1.model_validate_json(canonical_json_bytes(reply.document))
        raise RuntimeFrontendRefusedError(refusal.code.value)
    # CAST-RATIONALE-GOOGLE-CONSENT-REVIEW: Pydantic specializes the runtime
    # envelope to the exact public review type; its generic stub is broader.
    validate_google_consent_review(reply, pending, profile_id, request, contract)
    try:
        require_interactive_terminal()
    except GoogleAuthNonInteractiveError as error:
        # Reject this exact proposal when transport still permits settlement.
        # Failure to acknowledge rejection does not replace the canonical TTY verdict.
        with suppress(RuntimeFrontendRefusedError, RuntimeRefusalError, ValidationError):
            respond_google_consent(client, profile_id, session_id, pending, apply=False, deadline=deadline)
        error.context = {**(error.context or {}), "operation_id": str(pending.operation_id), "effect": "none"}
        raise
    respond_google_consent(client, profile_id, session_id, pending, apply=True, deadline=deadline)


def review_google_consent_once(
    state: OperationPublicProjectionV1,
    reviewed: tuple[str, int] | None,
    client: RuntimeFrontendClient,
    profile_id: UUID,
    session_id: UUID,
    request: GoogleLoginRequest,
    contract: OperationPublicDefinitionContractV1,
    deadline: float,
) -> tuple[str, int] | None:
    """Review google consent once."""
    if not isinstance(state.pending_interaction, OperationReviewAvailableInteractionV1):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    pending = state.pending_interaction
    coordinates = (pending.interaction_id, pending.revision)
    if reviewed is None:
        review_google_consent(client, profile_id, session_id, pending, request, contract, deadline)
        reviewed = coordinates
    elif reviewed != coordinates:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return reviewed
