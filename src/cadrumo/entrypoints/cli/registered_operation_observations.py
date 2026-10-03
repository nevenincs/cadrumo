"""Poll exact registered CLI operation projections while retaining effect uncertainty."""

from __future__ import annotations

import time
from collections.abc import Callable
from uuid import UUID, uuid4

from pydantic import BaseModel

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...application.operations.event_replay import OperationEventCursor
from ...application.operations.frontend_projection import (
    OperationPublicProjectionV1,
)
from ...application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationPublicEventPageV1,
    OperationPublicNoticeEventV1,
)
from ...application.operations.models import OperationId
from ...application.operations.persistence.replay import OperationReplayStatus
from ...application.operations.registry import (
    OperationPublicDefinitionContractV1,
)
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.operation_access import (
    RuntimeOperationObserve,
    RuntimeOperationReply,
    RuntimeOperationRequest,
)
from ...core.i18n.render import tr
from ...core.operations import OperationEffect, OperationLifecycle
from .errors import write_stderr
from .registered_operation_contracts import (
    RegisteredOperationProgress,
    RegisteredOperationReviewCompletion,
    RegisteredOperationReviewHandler,
)
from .registered_operation_deadlines import OPERATION_POLL_INITIAL_SECONDS, OPERATION_POLL_MAX_SECONDS
from .registered_operation_errors import registered_operation_still_running
from .registered_operation_projections import decode_registered_observation
from .registered_operation_reviews import respond_registered_pending_review

_OBSERVATION_EVENT_PAGE_LIMIT = 100

# Operation notices this command line prompts the operator for, by the
# executor's stable notice code. A code absent here (``operation.started``, or
# one a newer runtime adds) prints nothing.
_OPERATION_NOTICE_LOCALE_KEYS: dict[str, str] = {
    "auth.clave-movil.approval-pending": "cli.common.operation_notices.clave_movil_approval_pending",
    "auth.clave-movil.qr-scan-pending": "cli.common.operation_notices.clave_movil_qr_scan_pending",
}
_OPERATION_NOTICE_DISPLAY_CODE_LOCALE_KEYS: dict[str, str] = {
    "auth.clave-movil.approval-pending": "cli.common.operation_notices.clave_movil_approval_pending_with_code",
    "auth.clave-movil.qr-scan-pending": "cli.common.operation_notices.clave_movil_qr_scan_pending_with_code",
}


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
    after_cursor: OperationEventCursor = 0,
) -> OperationObservationSuccessV1:
    """Read the next exact operation projection and the events after ``after_cursor``.

    A timeout still reads as still-running, never as a refusal.
    """
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
                observation=OperationObservationRequestV1(
                    operation_id=operation_id,
                    after_cursor=after_cursor,
                    page_limit=_OBSERVATION_EVENT_PAGE_LIMIT,
                ),
            ),
        )
    except RuntimeRefusalError as error:
        if error.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED and time.monotonic() >= deadline:
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
    if event.display_code is not None:
        code_message_key = _OPERATION_NOTICE_DISPLAY_CODE_LOCALE_KEYS.get(event.notice_code)
        if code_message_key is not None:
            write_stderr(tr(code_message_key, code=event.display_code) + "\n")
            return
    message_key = _OPERATION_NOTICE_LOCALE_KEYS.get(event.notice_code)
    if message_key is not None:
        write_stderr(tr(message_key) + "\n")


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
