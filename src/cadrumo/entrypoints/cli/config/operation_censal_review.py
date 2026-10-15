"""Transport for registered censal review over the bound profile connection."""

from __future__ import annotations

import time
from collections.abc import Callable
from uuid import UUID, uuid4

from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.commands.registered_operation_errors import submitted_operation_error
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.deadline_budget import bounded_deadline_after, remaining_budget
from cadrumo_client.contracts.operation_access import (
    OperationAcknowledged,
    OperationControl,
    OperationSubmit,
    OperationSubmitted,
)
from cadrumo_client.contracts.submission_payload import SUBMISSION_PAYLOAD_MAX_BYTES
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError, frontend_failure_code

from ....application.operations.frontend_projection import OperationReviewAvailableInteractionV1
from ....application.operations.frontend_requests import (
    OperationObservationSuccessV1,
)
from ....application.operations.models import OperationId
from ....application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionContractV1,
)
from ....application.user_profile.censal_operation import (
    CENSAL_OPERATION_DEFINITION_ID,
    CensalOperationRequest,
    CensalReviewProjectionV1,
)
from ....core.operations import OperationLifecycle, OperationTerminalCondition
from .operation_censal_contracts import CensalReviewResult, _CensalReceiptState
from .operation_censal_exchange import _exchange
from .operation_censal_observation import _observe, _review_interaction, _validate_observation
from .operation_censal_projection import _resolve_review, _validate_contract, _validate_terminal
from .operation_censal_response import _respond


def _submit_censal_operation(
    client: FrontendClient, request: CensalOperationRequest, profile_id: UUID, session_id: UUID, deadline: float
) -> tuple[OperationSubmitted, str]:
    """Submit censal operation."""
    try:
        payload_json = request.model_dump_json()
        payload_size = len(payload_json.encode("utf-8"))
    except (UnicodeError, ValueError):
        raise RefusalError(RefusalCode.INVALID_FRAME) from None
    if payload_size > SUBMISSION_PAYLOAD_MAX_BYTES:
        raise RefusalError(RefusalCode.INVALID_FRAME)
    subject_ref = str(profile_id)
    submit_request = OperationSubmit(
        request_id=uuid4(),
        profile_id=profile_id,
        session_id=session_id,
        definition_id=CENSAL_OPERATION_DEFINITION_ID,
        subject_ref=subject_ref,
        payload_json=payload_json,
    )
    submitted = _exchange(client, session_id, submit_request, deadline=deadline)
    if not isinstance(submitted, OperationSubmitted):
        raise RefusalError(RefusalCode.INVALID_FRAME)
    return submitted, subject_ref


def review_censal_operation(
    client: FrontendClient,
    request: CensalOperationRequest,
    *,
    decide: Callable[[CensalReviewProjectionV1], bool],
    timeout: float = 120,
) -> CensalReviewResult:
    """Submit, review and answer one registered censal operation on this session."""
    deadline = bounded_deadline_after(timeout, subject="censal review")
    profile_id, session_id = client.profile_id, client.session_id
    if client.frontend is not OperationFrontendProjection.CLI or request.baseline.profile_id != str(profile_id):
        raise RefusalError(RefusalCode.INVALID_FRAME)

    contract = _validate_contract(client, request, deadline)
    submitted, subject_ref = _submit_censal_operation(client, request, profile_id, session_id, deadline)
    operation_id = submitted.receipt.operation_id

    receipt = _CensalReceiptState()
    try:
        _start_censal_operation(client, submitted, profile_id, session_id, operation_id, deadline)

        waiting, pending = _review_interaction(
            client,
            profile_id=profile_id,
            session_id=session_id,
            operation_id=operation_id,
            subject_ref=subject_ref,
            contract=contract,
            deadline=deadline,
        )
        receipt.condition = waiting.projection.terminal_condition
        receipt.effect = waiting.projection.effect
        receipt.refusal_code = waiting.projection.refusal_ref
        pending = _require_censal_pending(waiting, pending, receipt)
        review = _resolve_review(
            client,
            profile_id=profile_id,
            session_id=session_id,
            operation_id=operation_id,
            pending=pending,
            deadline=deadline,
            contract=contract,
        )
        apply = _decide_censal_review(review, request, decide)
        _respond(
            client,
            profile_id=profile_id,
            session_id=session_id,
            operation_id=operation_id,
            pending=pending,
            apply=apply,
            deadline=deadline,
        )

        return _await_censal_terminal(
            client, profile_id, session_id, operation_id, subject_ref, contract, deadline, receipt, review, apply
        )
    except CliRefusedBoundaryError:
        raise
    except Exception as error:
        code = frontend_failure_code(error)
        raise submitted_operation_error(
            operation_id,
            code,
            terminal_condition=receipt.condition,
            effect=receipt.effect,
            refusal_code=receipt.refusal_code,
        ) from None


def _start_censal_operation(
    client: FrontendClient,
    submitted: OperationSubmitted,
    profile_id: UUID,
    session_id: UUID,
    operation_id: OperationId,
    deadline: float,
) -> None:
    """Start the acknowledged operation only after confirming its secret contract."""
    if submitted.receipt.secret_requirement is not None:
        raise RefusalError(RefusalCode.INVALID_FRAME)
    start_request = OperationControl(
        action="operation_start",
        request_id=uuid4(),
        profile_id=profile_id,
        session_id=session_id,
        operation_id=operation_id,
    )
    started = _exchange(client, session_id, start_request, deadline=deadline)
    if not isinstance(started, OperationAcknowledged) or started.operation_id != operation_id:
        raise RefusalError(RefusalCode.INVALID_FRAME)


def _require_censal_pending(
    waiting: OperationObservationSuccessV1,
    pending: OperationReviewAvailableInteractionV1 | None,
    receipt: _CensalReceiptState,
) -> OperationReviewAvailableInteractionV1:
    """Require a pending review or present the admitted terminal refusal."""
    if pending is None:
        raise FrontendRefusedError(
            waiting.projection.refusal_ref
            or waiting.projection.failure_error_code
            or (receipt.condition.value if receipt.condition is not None else "unknown")
        )
    return pending


def _decide_censal_review(
    review: CensalReviewProjectionV1,
    request: CensalOperationRequest,
    decide: Callable[[CensalReviewProjectionV1], bool],
) -> bool:
    """Check the exact reviewed intents before accepting an explicit boolean decision."""
    if tuple((item.path, item.intent) for item in review.fields) != tuple(
        (item.path, item.intent) for item in request.field_intents
    ):
        raise RefusalError(RefusalCode.INVALID_FRAME)
    apply = decide(review)
    if type(apply) is not bool:
        raise RefusalError(RefusalCode.INVALID_FRAME)
    return apply


def _await_censal_terminal(
    client: FrontendClient,
    profile_id: UUID,
    session_id: UUID,
    operation_id: OperationId,
    subject_ref: str,
    contract: OperationPublicDefinitionContractV1,
    deadline: float,
    receipt: _CensalReceiptState,
    review: CensalReviewProjectionV1,
    apply: bool,
) -> CensalReviewResult:
    """Observe to settlement while preserving the latest receipt for failure presentation."""
    while True:
        remaining_budget(deadline)
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
        receipt.condition, receipt.effect, receipt.refusal_code = (
            state.terminal_condition,
            state.effect,
            state.refusal_ref,
        )
        if state.lifecycle is OperationLifecycle.TERMINAL:
            if receipt.condition is not OperationTerminalCondition.SUCCEEDED:
                raise FrontendRefusedError(
                    state.refusal_ref
                    or state.failure_error_code
                    or (receipt.condition.value if receipt.condition is not None else "unknown")
                )
            _validate_terminal(client, terminal, contract=contract, review=review, apply=apply, deadline=deadline)
            if client.profile_id != profile_id or client.session_id != session_id:
                raise RefusalError(RefusalCode.INVALID_FRAME)
            return CensalReviewResult(projection=review, applied=apply)
        if state.lifecycle is OperationLifecycle.WAITING_FOR_INTERACTION:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        time.sleep(min(0.02, remaining_budget(deadline)))
