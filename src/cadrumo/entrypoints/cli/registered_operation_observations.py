"""Poll exact registered CLI operation projections while retaining effect uncertainty."""

from __future__ import annotations

import time
from collections.abc import Callable
from uuid import UUID, uuid4

from pydantic import BaseModel

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...application.operations.frontend_projection import (
    OperationPublicProjectionV1,
)
from ...application.operations.frontend_requests import (
    OperationObservationRequestV1,
)
from ...application.operations.models import OperationId
from ...application.operations.registry import (
    OperationPublicDefinitionContractV1,
)
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.operation_access import (
    RuntimeOperationObserve,
    RuntimeOperationReply,
    RuntimeOperationRequest,
)
from ...core.operations import OperationEffect, OperationLifecycle
from .registered_operation_contracts import (
    RegisteredOperationProgress,
    RegisteredOperationReviewCompletion,
    RegisteredOperationReviewHandler,
)
from .registered_operation_deadlines import OPERATION_POLL_INITIAL_SECONDS, OPERATION_POLL_MAX_SECONDS
from .registered_operation_errors import registered_operation_still_running
from .registered_operation_projections import decode_registered_observation
from .registered_operation_reviews import respond_registered_pending_review


def observe_registered_operation(
    client: RuntimeFrontendClient,
    operation_id: OperationId,
    profile_id: UUID,
    session_id: UUID,
    definition_id: str,
    subject_ref: str,
    contract: OperationPublicDefinitionContractV1,
    deadline: float,
    pending_check_command: str | None,
    progress: RegisteredOperationProgress,
    exchange: Callable[[RuntimeOperationRequest], RuntimeOperationReply],
) -> OperationPublicProjectionV1:
    """Read the next exact operation projection and preserve timeout-as-still-running semantics."""
    if time.monotonic() >= deadline:
        raise registered_operation_still_running(operation_id, progress.effect, pending_check_command)
    if client.session_id != session_id:
        raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
    try:
        observed = exchange(
            RuntimeOperationObserve(
                request_id=uuid4(),
                profile_id=profile_id,
                session_id=session_id,
                observation=OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=1),
            ),
        )
    except RuntimeRefusalError as error:
        if error.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED and time.monotonic() >= deadline:
            raise registered_operation_still_running(operation_id, progress.effect, pending_check_command) from None
        raise
    return decode_registered_observation(observed, operation_id, definition_id, subject_ref, contract)


def wait_registered_settlement[ReviewT: BaseModel](
    client: RuntimeFrontendClient,
    operation_id: OperationId,
    profile_id: UUID,
    session_id: UUID,
    definition_id: str,
    subject_ref: str,
    contract: OperationPublicDefinitionContractV1,
    deadline: float,
    pending_check_command: str | None,
    progress: RegisteredOperationProgress,
    review: RegisteredOperationReviewHandler[ReviewT] | None,
    exchange: Callable[[RuntimeOperationRequest], RuntimeOperationReply],
) -> tuple[OperationPublicProjectionV1, RegisteredOperationReviewCompletion[ReviewT] | None]:
    """Observe settlement with bounded polling and sticky uncertainty after response submission."""
    responded_interactions: set[tuple[str, int]] = set()
    poll = OPERATION_POLL_INITIAL_SECONDS
    while True:
        state = observe_registered_operation(
            client,
            operation_id,
            profile_id,
            session_id,
            definition_id,
            subject_ref,
            contract,
            deadline,
            pending_check_command,
            progress,
            exchange,
        )
        if state.lifecycle is OperationLifecycle.TERMINAL:
            progress.condition, progress.effect = state.terminal_condition, state.effect
            progress.refusal_code = state.refusal_ref
            break
        if progress.effect is not OperationEffect.UNKNOWN:
            progress.effect = state.effect
        if state.lifecycle is OperationLifecycle.WAITING_FOR_INTERACTION:
            detached_review = respond_registered_pending_review(
                state, operation_id, review, contract, profile_id, session_id, responded_interactions, exchange
            )
            if detached_review is not None:
                return state, detached_review
        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(min(poll, remaining))
        poll = min(poll * 1.5, OPERATION_POLL_MAX_SECONDS)
    return state, None
