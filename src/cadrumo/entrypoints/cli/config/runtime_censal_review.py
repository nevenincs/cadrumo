"""Runtime transport for the registered censal review operation."""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast
from uuid import UUID, uuid4

from pydantic import BaseModel, JsonValue, ValidationError

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient, RuntimeFrontendRefusedError
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
from ....application.operations.models import OperationId
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
from ....application.user_profile.access_contracts import AccessDenialCode
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
from ....core.time.clock import now
from ..errors import CliRefusedBoundaryError
from ..runtime_registered_operation import submitted_operation_error

_MAX_TIMEOUT_SECONDS = 120.0
_OBSERVATION_PAGE_LIMIT = 1


@dataclass(frozen=True, slots=True)
class CensalRuntimeReviewResult:
    """The exact reviewed proposal and the outcome the runtime applied."""

    projection: CensalReviewProjectionV1
    applied: bool


def _deadline(timeout: float) -> float:
    if not math.isfinite(timeout) or not 0 < timeout <= _MAX_TIMEOUT_SECONDS:
        raise ValueError("censal review timeout must be finite and at most 120 seconds")
    return time.monotonic() + timeout


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
    return remaining


def _failure_code(error: Exception) -> str:
    if isinstance(error, RuntimeFrontendRefusedError):
        return error.reason
    if isinstance(error, RuntimeRefusalError):
        return error.reason.value
    return RuntimeRefusalCode.UNAVAILABLE.value


def _require_session(client: RuntimeFrontendClient, session_id: UUID) -> None:
    if client.session_id != session_id:
        raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)


def _exchange(
    client: RuntimeFrontendClient,
    session_id: UUID,
    request: RuntimeOperationRequest,
    *,
    deadline: float,
) -> RuntimeOperationReply:
    _require_session(client, session_id)
    reply = client.operation(request, deadline=deadline)
    _require_session(client, session_id)
    if getattr(reply, "request_id", None) != getattr(request, "request_id", None):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return reply


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


def _observe(
    client: RuntimeFrontendClient,
    *,
    profile_id: UUID,
    session_id: UUID,
    operation_id: OperationId,
    deadline: float,
) -> OperationObservationSuccessV1:
    request = RuntimeOperationObserve(
        request_id=uuid4(),
        profile_id=profile_id,
        session_id=session_id,
        observation=OperationObservationRequestV1(
            operation_id=operation_id,
            after_cursor=0,
            page_limit=_OBSERVATION_PAGE_LIMIT,
        ),
    )
    reply = _exchange(client, session_id, request, deadline=deadline)
    if not isinstance(reply, RuntimeOperationObserved):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    if isinstance(reply.observation, OperationObservationRefusalV1):
        raise RuntimeFrontendRefusedError(reply.observation.code.value)
    if not isinstance(reply.observation, OperationObservationSuccessV1):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return reply.observation


def _validate_observation(
    observed: OperationObservationSuccessV1,
    *,
    operation_id: OperationId,
    subject_ref: str,
    contract: OperationPublicDefinitionContractV1,
) -> None:
    projection = observed.projection
    if (
        projection.operation_id != operation_id
        or projection.definition_id != CENSAL_OPERATION_DEFINITION_ID
        or projection.subject_ref != subject_ref
        or projection.definition_contract != contract
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)


def _review_interaction(
    client: RuntimeFrontendClient,
    *,
    profile_id: UUID,
    session_id: UUID,
    operation_id: OperationId,
    subject_ref: str,
    contract: OperationPublicDefinitionContractV1,
    deadline: float,
) -> tuple[OperationObservationSuccessV1, OperationReviewAvailableInteractionV1 | None]:
    while True:
        _remaining(deadline)
        observed = _observe(
            client,
            profile_id=profile_id,
            session_id=session_id,
            operation_id=operation_id,
            deadline=deadline,
        )
        _validate_observation(
            observed,
            operation_id=operation_id,
            subject_ref=subject_ref,
            contract=contract,
        )
        projection = observed.projection
        if projection.lifecycle is OperationLifecycle.TERMINAL:
            return observed, None
        pending = projection.pending_interaction
        if isinstance(pending, OperationReviewAvailableInteractionV1):
            reference = pending.review_reference
            if (
                pending.operation_id != operation_id
                or pending.response_schema != CENSAL_REVIEW_RESPONSE_SCHEMA_BINDING.identity
                or reference.operation_id != operation_id
                or reference.review_projection_schema != CENSAL_REVIEW_PROJECTION_SCHEMA_BINDING.identity
                or reference.definition_contract_digest != contract.definition_contract_digest
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            return observed, pending
        if projection.lifecycle is OperationLifecycle.WAITING_FOR_INTERACTION:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        time.sleep(min(0.02, _remaining(deadline)))


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
        timeout=_remaining(deadline),
        deadline=deadline,
    )
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
    if (
        success.result_schema != contract.result_schema
        or success.definition_contract_digest != contract.definition_contract_digest
        or success.projection.outcome is not expected_outcome
        or success.projection.reviewed_proposal_digest != review.reviewed_proposal_digest
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)


def review_censal_with_runtime(
    client: RuntimeFrontendClient,
    request: CensalOperationRequest,
    *,
    decide: Callable[[CensalReviewProjectionV1], bool],
    timeout: float = 120,
) -> CensalRuntimeReviewResult:
    """Submit, review and answer one registered censal operation on this session."""
    deadline = _deadline(timeout)
    profile_id, session_id = client.profile_id, client.session_id
    if client.frontend is not OperationFrontendProjection.CLI or request.baseline.profile_id != str(profile_id):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)

    contract = _validate_contract(client, request, deadline)
    try:
        payload_json = request.model_dump_json()
        payload_size = len(payload_json.encode("utf-8"))
    except (UnicodeError, ValueError):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) from None
    if payload_size > SUBMISSION_PAYLOAD_MAX_BYTES:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    subject_ref = str(profile_id)
    submit_request = RuntimeOperationSubmit(
        request_id=uuid4(),
        profile_id=profile_id,
        session_id=session_id,
        definition_id=CENSAL_OPERATION_DEFINITION_ID,
        subject_ref=subject_ref,
        payload_json=payload_json,
    )
    submitted = _exchange(client, session_id, submit_request, deadline=deadline)
    if not isinstance(submitted, RuntimeOperationSubmitted):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    operation_id = submitted.receipt.operation_id

    condition: OperationTerminalCondition | None = None
    effect: OperationEffect | None = None
    refusal_code: str | None = None
    try:
        if submitted.receipt.secret_requirement is not None:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        start_request = RuntimeOperationControl(
            action="operation_start",
            request_id=uuid4(),
            profile_id=profile_id,
            session_id=session_id,
            operation_id=operation_id,
        )
        started = _exchange(client, session_id, start_request, deadline=deadline)
        if not isinstance(started, RuntimeOperationAcknowledged) or started.operation_id != operation_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)

        waiting, pending = _review_interaction(
            client,
            profile_id=profile_id,
            session_id=session_id,
            operation_id=operation_id,
            subject_ref=subject_ref,
            contract=contract,
            deadline=deadline,
        )
        condition = waiting.projection.terminal_condition
        effect = waiting.projection.effect
        refusal_code = waiting.projection.refusal_ref
        if pending is None:
            raise RuntimeFrontendRefusedError(
                waiting.projection.refusal_ref
                or waiting.projection.failure_error_code
                or (condition.value if condition is not None else "unknown")
            )
        review = _resolve_review(
            client,
            profile_id=profile_id,
            session_id=session_id,
            operation_id=operation_id,
            pending=pending,
            deadline=deadline,
            contract=contract,
        )
        if tuple((item.path, item.intent) for item in review.fields) != tuple(
            (item.path, item.intent) for item in request.field_intents
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        apply = decide(review)
        if type(apply) is not bool:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        _respond(
            client,
            profile_id=profile_id,
            session_id=session_id,
            operation_id=operation_id,
            pending=pending,
            apply=apply,
            deadline=deadline,
        )

        while True:
            _remaining(deadline)
            terminal = _observe(
                client,
                profile_id=profile_id,
                session_id=session_id,
                operation_id=operation_id,
                deadline=deadline,
            )
            _validate_observation(
                terminal,
                operation_id=operation_id,
                subject_ref=subject_ref,
                contract=contract,
            )
            state = terminal.projection
            condition, effect, refusal_code = state.terminal_condition, state.effect, state.refusal_ref
            if state.lifecycle is OperationLifecycle.TERMINAL:
                if condition is not OperationTerminalCondition.SUCCEEDED:
                    raise RuntimeFrontendRefusedError(
                        state.refusal_ref
                        or state.failure_error_code
                        or (condition.value if condition is not None else "unknown")
                    )
                _validate_terminal(client, terminal, contract=contract, review=review, apply=apply, deadline=deadline)
                if client.profile_id != profile_id or client.session_id != session_id:
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                return CensalRuntimeReviewResult(projection=review, applied=apply)
            if state.lifecycle is OperationLifecycle.WAITING_FOR_INTERACTION:
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            time.sleep(min(0.02, _remaining(deadline)))
    except CliRefusedBoundaryError:
        raise
    except Exception as error:
        code = RuntimeRefusalCode.INVALID_FRAME.value if isinstance(error, ValidationError) else _failure_code(error)
        raise submitted_operation_error(
            operation_id,
            code,
            terminal_condition=condition,
            effect=effect,
            refusal_code=refusal_code,
        ) from None


__all__ = ["CensalRuntimeReviewResult", "review_censal_with_runtime"]
