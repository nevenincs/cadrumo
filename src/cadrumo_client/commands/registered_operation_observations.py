"""Poll exact registered CLI operation projections while retaining effect uncertainty."""

from __future__ import annotations

import time
from collections.abc import Callable
from uuid import UUID, uuid4

from pydantic import BaseModel

from cadrumo.application.operations.event_replay import OperationEventCursor
from cadrumo.application.operations.frontend_projection import (
    OperationPublicProjectionV1,
)
from cadrumo.application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationPublicEventPageV1,
    OperationPublicNoticeEventV1,
)
from cadrumo.application.operations.models import OperationId
from cadrumo.application.operations.persistence.replay import OperationReplayStatus
from cadrumo.application.operations.registry import (
    OperationPublicDefinitionContractV1,
)
from cadrumo.core.operations import OperationEffect, OperationLifecycle
from cadrumo.core.operator_notice_messages import operation_notice_message
from cadrumo_client.commands.output import write_stderr
from cadrumo_client.commands.registered_operation_contracts import (
    RegisteredOperationProgress,
    RegisteredOperationReviewCompletion,
    RegisteredOperationReviewHandler,
)
from cadrumo_client.commands.registered_operation_deadlines import (
    OPERATION_POLL_INITIAL_SECONDS,
    OPERATION_POLL_MAX_SECONDS,
)
from cadrumo_client.commands.registered_operation_errors import registered_operation_still_running
from cadrumo_client.commands.registered_operation_projections import decode_registered_observation
from cadrumo_client.commands.registered_operation_reviews import respond_registered_pending_review
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.operation_access import (
    OperationObserve,
    OperationReply,
    OperationRequest,
)
from cadrumo_client.transport.frontend_client import FrontendClient

_OBSERVATION_EVENT_PAGE_LIMIT = 100


def observe_registered_operation(
    client: FrontendClient,
    operation_id: OperationId,
    profile_id: UUID,
    session_id: UUID,
    definition_id: str,
    subject_ref: str,
    contract: OperationPublicDefinitionContractV1,
    deadline: float,
    pending_check_command: str | None,
    progress: RegisteredOperationProgress,
    exchange: Callable[[OperationRequest], OperationReply],
    after_cursor: OperationEventCursor = 0,
) -> OperationObservationSuccessV1:
    """Read the next exact operation projection and the events after ``after_cursor``.

    A timeout still reads as still-running, never as a refusal.
    """
    if time.monotonic() >= deadline:
        raise registered_operation_still_running(operation_id, progress.effect, pending_check_command)
    if client.session_id != session_id:
        raise RefusalError(RefusalCode.CONNECTION_CLOSED)
    try:
        observed = exchange(
            OperationObserve(
                request_id=uuid4(),
                profile_id=profile_id,
                session_id=session_id,
                observation=OperationObservationRequestV1(
                    operation_id=operation_id,
                    after_cursor=after_cursor,
                    page_limit=_OBSERVATION_EVENT_PAGE_LIMIT,
                ),
            ),
        )
    except RefusalError as error:
        if error.reason is RefusalCode.DEADLINE_EXCEEDED and time.monotonic() >= deadline:
            raise registered_operation_still_running(operation_id, progress.effect, pending_check_command) from None
        raise
    return decode_registered_observation(observed, operation_id, definition_id, subject_ref, contract)


def render_registered_operation_notices(page: OperationPublicEventPageV1) -> OperationEventCursor:
    """Prompt the operator on stderr for each new notice this CLI knows, and return the next cursor.

    Each event is read once because the caller resumes after the returned
    cursor; an expired or compacted page resumes at its restart cursor, so
    notices the journal no longer retains are skipped rather than replayed.
    """
    if page.status is OperationReplayStatus.PAGE:
        for event in page.events:
            if isinstance(event, OperationPublicNoticeEventV1):
                _render_operation_notice(event)
        return page.next_cursor
    if page.restart_cursor is not None:
        return page.restart_cursor
    return page.next_cursor


def _render_operation_notice(event: OperationPublicNoticeEventV1) -> None:
    """Write one localized notice to stderr, keeping the structured result channel pure."""
    message = operation_notice_message(event.notice_code, event.display_code)
    if message is not None:
        write_stderr(message)


def wait_registered_settlement[ReviewT: BaseModel](
    client: FrontendClient,
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
    exchange: Callable[[OperationRequest], OperationReply],
) -> tuple[OperationPublicProjectionV1, RegisteredOperationReviewCompletion[ReviewT] | None]:
    """Observe settlement with bounded polling and sticky uncertainty after response submission."""
    responded_interactions: set[tuple[str, int]] = set()
    poll = OPERATION_POLL_INITIAL_SECONDS
    event_cursor: OperationEventCursor = 0
    while True:
        observation = observe_registered_operation(
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
            event_cursor,
        )
        event_cursor = render_registered_operation_notices(observation.event_page)
        state = observation.projection
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
