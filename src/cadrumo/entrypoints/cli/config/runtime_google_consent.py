"""Exact human terminal acknowledgement for the registered Google consent flow."""

from __future__ import annotations

import math
import time
from contextlib import suppress
from typing import cast
from uuid import UUID, uuid4

from pydantic import ValidationError

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient, RuntimeFrontendRefusedError
from ....adapters.outbound.google.errors import GoogleAuthNonInteractiveError
from ....adapters.outbound.google.oauth_flow import require_interactive_terminal
from ....application.operations.frontend_projection import OperationReviewAvailableInteractionV1
from ....application.operations.frontend_requests import (
    OperationObservationRefusalV1,
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResponseApplyRequestV1,
    OperationResponseControlRefusalV1,
    OperationResponseControlRequestV1,
    OperationResponseControlSuccessV1,
    OperationResponseMutationSuccessV1,
    OperationResponseRejectRequestV1,
    OperationResultProjectionRefusalV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
    OperationReviewProjectionRefusalV1,
    OperationReviewProjectionRequestV1,
    OperationReviewProjectionSuccessV1,
)
from ....application.operations.models import OperationIdentity
from ....application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionContractV1,
    OperationSchemaIdentityV1,
)
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....application.runtime.operation_access import (
    RuntimeOperationAcknowledged,
    RuntimeOperationControl,
    RuntimeOperationManage,
    RuntimeOperationManaged,
    RuntimeOperationObserve,
    RuntimeOperationObserved,
    RuntimeOperationProjected,
    RuntimeOperationReply,
    RuntimeOperationRequest,
    RuntimeOperationReview,
    RuntimeOperationSubmit,
    RuntimeOperationSubmitted,
)
from ....application.runtime.submission_payload import SUBMISSION_PAYLOAD_MAX_BYTES
from ....application.user_profile.google_configuration_operation import (
    GOOGLE_CONSENT_RESPONSE_SCHEMA_BINDING,
    GOOGLE_CONSENT_REVIEW_SCHEMA_BINDING,
)
from ....application.user_profile.google_configuration_operation_contracts import (
    GOOGLE_CONSENT_PRESENTATION_CODE,
    GOOGLE_LOGIN_OPERATION_DEFINITION_ID,
    GoogleConfigurationOutcome,
    GoogleConsentProposal,
    GoogleConsentReviewProjection,
    GoogleLoginRequest,
)
from ....core.hashing import canonical_json_bytes
from ....core.operations import OperationLifecycle, OperationTerminalCondition, profile_operation_subject
from ....core.time.clock import now
from ..errors import CliRefusedBoundaryError
from ..runtime_registered_operation import RegisteredOperationCompletion, submitted_operation_error


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
    return remaining


def _exchange(
    client: RuntimeFrontendClient,
    profile_id: UUID,
    session_id: UUID,
    request: RuntimeOperationRequest,
    deadline: float,
) -> RuntimeOperationReply:
    if (
        client.profile_id != profile_id
        or client.session_id != session_id
        or client.frontend is not OperationFrontendProjection.CLI
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
    _remaining(deadline)
    reply = client.operation(request, deadline=deadline)
    if (
        client.profile_id != profile_id
        or client.session_id != session_id
        or client.frontend is not OperationFrontendProjection.CLI
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
    if reply.request_id != request.request_id:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return reply


def _respond(
    client: RuntimeFrontendClient,
    profile_id: UUID,
    session_id: UUID,
    pending: OperationReviewAvailableInteractionV1,
    *,
    apply: bool,
    deadline: float,
) -> None:
    actor_ref = f"session:{session_id}"
    reply = _exchange(
        client,
        profile_id,
        session_id,
        RuntimeOperationManage(
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
    if not isinstance(reply, RuntimeOperationManaged) or reply.operation_id != pending.operation_id:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    if reply.document.get("outcome") == "refused":
        refusal = OperationResponseControlRefusalV1.model_validate_json(canonical_json_bytes(reply.document))
        raise RuntimeFrontendRefusedError(refusal.code.value)
    control = OperationResponseControlSuccessV1.model_validate_json(canonical_json_bytes(reply.document))
    intent = "apply" if apply else "reject"
    if (
        control.operation_id != pending.operation_id
        or control.interaction_id != pending.interaction_id
        or control.revision != pending.revision
        or not control.available
        or intent not in control.permitted_intents
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
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
    reply = _exchange(
        client,
        profile_id,
        session_id,
        RuntimeOperationManage(
            request_id=uuid4(),
            profile_id=profile_id,
            session_id=session_id,
            management=mutation,
        ),
        deadline,
    )
    if not isinstance(reply, RuntimeOperationManaged) or reply.operation_id != pending.operation_id:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    if reply.document.get("outcome") == "refused":
        refusal = OperationResponseControlRefusalV1.model_validate_json(canonical_json_bytes(reply.document))
        raise RuntimeFrontendRefusedError(refusal.code.value)
    accepted = OperationResponseMutationSuccessV1.model_validate_json(canonical_json_bytes(reply.document))
    if (
        accepted.operation_id != pending.operation_id
        or accepted.interaction_id != pending.interaction_id
        or accepted.revision != pending.revision
        or accepted.response_action != intent
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)


def _review(
    client: RuntimeFrontendClient,
    profile_id: UUID,
    session_id: UUID,
    pending: OperationReviewAvailableInteractionV1,
    request: GoogleLoginRequest,
    contract: OperationPublicDefinitionContractV1,
    deadline: float,
) -> None:
    if (
        pending.presentation_code != GOOGLE_CONSENT_PRESENTATION_CODE
        or pending.response_schema != contract.interaction_response_schema
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    reply = _exchange(
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
    try:
        require_interactive_terminal()
    except GoogleAuthNonInteractiveError as error:
        # Reject this exact proposal when transport still permits settlement.
        # Failure to acknowledge rejection does not replace the canonical TTY verdict.
        with suppress(RuntimeFrontendRefusedError, RuntimeRefusalError, ValidationError):
            _respond(client, profile_id, session_id, pending, apply=False, deadline=deadline)
        error.context = {**(error.context or {}), "operation_id": str(pending.operation_id), "effect": "none"}
        raise
    _respond(client, profile_id, session_id, pending, apply=True, deadline=deadline)


def login_google_with_runtime(
    client: RuntimeFrontendClient,
    request: GoogleLoginRequest,
    *,
    timeout: float = 420,
) -> RegisteredOperationCompletion[GoogleConfigurationOutcome]:
    """Review this human terminal and wait for canonical browser consent settlement."""
    if request.refresh_only or not math.isfinite(timeout) or not 0 < timeout <= 420:
        raise ValueError("Google browser consent requires a finite timeout of at most 420 seconds")
    deadline = time.monotonic() + timeout
    profile_id, session_id = client.profile_id, client.session_id
    if request.profile_id != profile_id or client.frontend is not OperationFrontendProjection.CLI:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    contract = client.contract(GOOGLE_LOGIN_OPERATION_DEFINITION_ID, deadline=deadline)
    expected_request = OperationSchemaIdentityV1.from_model(
        schema_id=GOOGLE_LOGIN_OPERATION_DEFINITION_ID + ".request",
        schema_version=1,
        model_type=GoogleLoginRequest,
    )
    expected_result = OperationSchemaIdentityV1.from_model(
        schema_id=GOOGLE_LOGIN_OPERATION_DEFINITION_ID + ".result",
        schema_version=1,
        model_type=GoogleConfigurationOutcome,
    )
    if (
        contract.definition_id != GOOGLE_LOGIN_OPERATION_DEFINITION_ID
        or contract.request_schema != expected_request
        or contract.result_schema != expected_result
        or contract.review_projection_schema != GOOGLE_CONSENT_REVIEW_SCHEMA_BINDING.identity
        or contract.interaction_response_schema != GOOGLE_CONSENT_RESPONSE_SCHEMA_BINDING.identity
        or client.frontend not in contract.permitted_frontends
        or contract.ephemeral_secret_required
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    payload_json = request.model_dump_json()
    if len(payload_json.encode("utf-8")) > SUBMISSION_PAYLOAD_MAX_BYTES:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    subject_ref = profile_operation_subject(str(profile_id))
    submitted = _exchange(
        client,
        profile_id,
        session_id,
        RuntimeOperationSubmit(
            request_id=uuid4(),
            profile_id=profile_id,
            session_id=session_id,
            definition_id=GOOGLE_LOGIN_OPERATION_DEFINITION_ID,
            subject_ref=subject_ref,
            payload_json=payload_json,
        ),
        deadline,
    )
    if not isinstance(submitted, RuntimeOperationSubmitted):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    operation_id = submitted.receipt.operation_id
    condition = None
    effect = None
    refusal_code = None
    reviewed: tuple[str, int] | None = None
    try:
        if submitted.receipt.secret_requirement is not None:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        started = _exchange(
            client,
            profile_id,
            session_id,
            RuntimeOperationControl(
                action="operation_start",
                request_id=uuid4(),
                profile_id=profile_id,
                session_id=session_id,
                operation_id=operation_id,
            ),
            deadline,
        )
        if not isinstance(started, RuntimeOperationAcknowledged) or started.operation_id != operation_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        while True:
            observed = _exchange(
                client,
                profile_id,
                session_id,
                RuntimeOperationObserve(
                    request_id=uuid4(),
                    profile_id=profile_id,
                    session_id=session_id,
                    observation=OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=1),
                ),
                deadline,
            )
            if not isinstance(observed, RuntimeOperationObserved):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            if isinstance(observed.observation, OperationObservationRefusalV1):
                raise RuntimeFrontendRefusedError(observed.observation.code.value)
            if not isinstance(observed.observation, OperationObservationSuccessV1):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            state = observed.observation.projection
            if (
                state.operation_id != operation_id
                or state.definition_id != GOOGLE_LOGIN_OPERATION_DEFINITION_ID
                or state.subject_ref != subject_ref
                or state.definition_contract != contract
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            condition, effect, refusal_code = state.terminal_condition, state.effect, state.refusal_ref
            if state.lifecycle is OperationLifecycle.TERMINAL:
                break
            if state.lifecycle is OperationLifecycle.WAITING_FOR_INTERACTION:
                if not isinstance(state.pending_interaction, OperationReviewAvailableInteractionV1):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                pending = state.pending_interaction
                coordinates = (pending.interaction_id, pending.revision)
                if reviewed is None:
                    _review(client, profile_id, session_id, pending, request, contract, deadline)
                    reviewed = coordinates
                elif reviewed != coordinates:
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            time.sleep(min(0.02, _remaining(deadline)))
        if condition is not OperationTerminalCondition.SUCCEEDED and not (
            condition is OperationTerminalCondition.REFUSED and refusal_code in contract.refusal_detail_codes
        ):
            raise submitted_operation_error(
                operation_id,
                state.refusal_ref or state.failure_error_code or "unknown",
                terminal_condition=condition,
                effect=effect,
                refusal_code=refusal_code,
            )
        document = client.read_result_document(
            OperationResultProjectionRequestV1(
                operation_id=operation_id,
                terminal_revision=state.revision,
                definition_contract_digest=contract.definition_contract_digest,
                result_schema=expected_result,
            ),
            timeout=_remaining(deadline),
        )
        if document.get("outcome") == "refused":
            refusal = OperationResultProjectionRefusalV1.model_validate_json(canonical_json_bytes(document))
            raise RuntimeFrontendRefusedError(refusal.code.value)
        # CAST-RATIONALE-GOOGLE-CONSENT-RESULT: runtime Pydantic specialization
        # binds the exact closed outcome despite the broader generic stub.
        success_type = cast(
            "type[OperationResultProjectionSuccessV1[GoogleConfigurationOutcome]]",
            OperationResultProjectionSuccessV1.__class_getitem__(GoogleConfigurationOutcome),
        )
        success = success_type.model_validate_json(canonical_json_bytes(document))
        if (
            success.result_schema != expected_result
            or success.definition_contract_digest != contract.definition_contract_digest
            or success.projection.profile_id != profile_id
            or client.profile_id != profile_id
            or client.session_id != session_id
            or client.frontend is not OperationFrontendProjection.CLI
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return RegisteredOperationCompletion(
            operation_id=operation_id,
            projection=success.projection,
            effect=effect,
            terminal_condition=condition,
            refusal_code=refusal_code,
        )
    except (CliRefusedBoundaryError, GoogleAuthNonInteractiveError):
        raise
    except Exception as error:
        code = (
            error.reason
            if isinstance(error, RuntimeFrontendRefusedError)
            else error.reason.value
            if isinstance(error, RuntimeRefusalError)
            else RuntimeRefusalCode.INVALID_FRAME.value
            if isinstance(error, ValidationError)
            else RuntimeRefusalCode.UNAVAILABLE.value
        )
        raise submitted_operation_error(
            operation_id, code, terminal_condition=condition, effect=effect, refusal_code=refusal_code
        ) from None


__all__ = ["login_google_with_runtime"]
