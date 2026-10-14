"""Canonical google consent review stages for the human terminal."""

from __future__ import annotations

from contextlib import suppress
from typing import cast
from uuid import UUID, uuid4

from pydantic import ValidationError

from cadrumo.adapters.outbound.google.errors import GoogleAuthNonInteractiveError
from cadrumo.adapters.outbound.google.oauth_flow import require_interactive_terminal
from cadrumo.application.operations.frontend_projection import (
    OperationPublicProjectionV1,
    OperationReviewAvailableInteractionV1,
)
from cadrumo.application.operations.frontend_requests import (
    OperationReviewProjectionRefusalV1,
    OperationReviewProjectionRequestV1,
    OperationReviewProjectionSuccessV1,
)
from cadrumo.application.operations.models import OperationIdentity
from cadrumo.application.operations.registry import (
    OperationPublicDefinitionContractV1,
)
from cadrumo.application.user_profile.google_configuration_operation_contracts import (
    GOOGLE_CONSENT_PRESENTATION_CODE,
    GOOGLE_LOGIN_OPERATION_DEFINITION_ID,
    GoogleConsentProposal,
    GoogleConsentReviewProjection,
    GoogleLoginRequest,
)
from cadrumo.core.hashing import canonical_json_bytes
from cadrumo.core.operations import (
    profile_operation_subject,
)
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.operation_access import (
    OperationProjected,
    OperationReview,
)
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

from .google_consent_exchange import google_consent_exchange
from .google_consent_response import respond_google_consent


def validate_google_consent_review(
    reply: OperationProjected,
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
        raise RefusalError(RefusalCode.INVALID_FRAME)


def review_google_consent(
    client: FrontendClient,
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
        raise RefusalError(RefusalCode.INVALID_FRAME)
    reply = google_consent_exchange(
        client,
        profile_id,
        session_id,
        OperationReview(
            request_id=uuid4(),
            profile_id=profile_id,
            session_id=session_id,
            review=OperationReviewProjectionRequestV1(reference=pending.review_reference),
        ),
        deadline,
    )
    if (
        not isinstance(reply, OperationProjected)
        or reply.operation_id != pending.operation_id
        or reply.projection_kind != "review"
    ):
        raise RefusalError(RefusalCode.INVALID_FRAME)
    if reply.document.get("outcome") == "refused":
        refusal = OperationReviewProjectionRefusalV1.model_validate_json(canonical_json_bytes(reply.document))
        raise FrontendRefusedError(refusal.code.value)
    # CAST-RATIONALE-GOOGLE-CONSENT-REVIEW: Pydantic specializes the runtime
    # envelope to the exact public review type; its generic stub is broader.
    validate_google_consent_review(reply, pending, profile_id, request, contract)
    try:
        require_interactive_terminal()
    except GoogleAuthNonInteractiveError as error:
        # Reject this exact proposal when transport still permits settlement.
        # Failure to acknowledge rejection does not replace the canonical TTY verdict.
        with suppress(FrontendRefusedError, RefusalError, ValidationError):
            respond_google_consent(client, profile_id, session_id, pending, apply=False, deadline=deadline)
        error.context = {**(error.context or {}), "operation_id": str(pending.operation_id), "effect": "none"}
        raise
    respond_google_consent(client, profile_id, session_id, pending, apply=True, deadline=deadline)


def review_google_consent_once(
    state: OperationPublicProjectionV1,
    reviewed: tuple[str, int] | None,
    client: FrontendClient,
    profile_id: UUID,
    session_id: UUID,
    request: GoogleLoginRequest,
    contract: OperationPublicDefinitionContractV1,
    deadline: float,
) -> tuple[str, int] | None:
    """Review google consent once."""
    if not isinstance(state.pending_interaction, OperationReviewAvailableInteractionV1):
        raise RefusalError(RefusalCode.INVALID_FRAME)
    pending = state.pending_interaction
    coordinates = (pending.interaction_id, pending.revision)
    if reviewed is None:
        review_google_consent(client, profile_id, session_id, pending, request, contract, deadline)
        reviewed = coordinates
    elif reviewed != coordinates:
        raise RefusalError(RefusalCode.INVALID_FRAME)
    return reviewed
