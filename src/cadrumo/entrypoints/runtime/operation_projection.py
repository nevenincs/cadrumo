"""Prepare canonical private replies for the runtime's final disclosure guard."""

from __future__ import annotations

from uuid import UUID

from ...application.operations.models import OperationId
from ...application.runtime.operation_access import (
    RuntimeOperationAcknowledged,
    RuntimeOperationControl,
    RuntimeOperationManage,
    RuntimeOperationManaged,
    RuntimeOperationObserve,
    RuntimeOperationObserved,
    RuntimeOperationPage,
    RuntimeOperationProjected,
    RuntimeOperationReply,
    RuntimeOperationResult,
    RuntimeOperationResultPage,
    RuntimeOperationReview,
    RuntimeOperationSubmit,
    RuntimeOperationSubmitted,
    operation_management_action,
)
from ...application.runtime.worker_authorization import WorkerAuthorityRequest
from ...application.user_profile.access_contracts import AccessAction, AccessDenialCode
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from .profile_host import ProfileConnection, RuntimeProfileHost


def prepare_operation_projection(
    host: RuntimeProfileHost,
    connection: ProfileConnection,
    request: RuntimeOperationSubmit
    | RuntimeOperationControl
    | RuntimeOperationObserve
    | RuntimeOperationResult
    | RuntimeOperationResultPage
    | RuntimeOperationReview
    | RuntimeOperationManage,
) -> tuple[RuntimeOperationReply, WorkerAuthorityRequest]:
    """Use native worker policy without accepting client-supplied readiness or scopes."""
    worker = host.owner.operation_worker()
    if isinstance(request, RuntimeOperationSubmit):
        submitted = worker.submit_serialized(
            session_id=request.session_id,
            frontend=connection.frontend,
            definition_id=request.definition_id,
            subject_ref=request.subject_ref,
            payload_json=request.payload_json,
            idempotency_key=request.idempotency_key,
        )
        release, expected_action = submitted.release, AccessAction.SUBMIT
        reply = RuntimeOperationSubmitted(
            request_id=request.request_id,
            runtime_boot_id=connection.context.runtime_boot_id,
            connection_id=connection.context.connection_id,
            receipt=submitted.receipt,
        )
        expected_operation = submitted.receipt.operation_id
    elif isinstance(request, RuntimeOperationObserve):
        observed = worker.observe(request.session_id, request.observation, frontend=connection.frontend)
        release, expected_action = observed.release, AccessAction.OBSERVE
        reply = RuntimeOperationObserved(
            request_id=request.request_id,
            runtime_boot_id=connection.context.runtime_boot_id,
            connection_id=connection.context.connection_id,
            observation=observed.observation,
        )
        expected_operation = request.observation.operation_id
    elif isinstance(request, RuntimeOperationResultPage):
        paged = worker.project_page(request.session_id, request.result, request.page, frontend=connection.frontend)
        release, expected_action = paged.release, AccessAction.RESULT
        expected_operation = request.result.operation_id
        reply = RuntimeOperationPage(
            request_id=request.request_id,
            runtime_boot_id=connection.context.runtime_boot_id,
            connection_id=connection.context.connection_id,
            operation_id=expected_operation,
            page=paged.page,
        )
    elif isinstance(request, RuntimeOperationResult | RuntimeOperationReview):
        if isinstance(request, RuntimeOperationResult):
            projected = worker.project(request.session_id, request.result, frontend=connection.frontend)
            expected_operation, expected_action = request.result.operation_id, AccessAction.RESULT
        else:
            projected = worker.project(request.session_id, request.review, frontend=connection.frontend)
            expected_operation, expected_action = request.review.reference.operation_id, AccessAction.REVIEW
        release = projected.release
        reply = RuntimeOperationProjected(
            request_id=request.request_id,
            runtime_boot_id=connection.context.runtime_boot_id,
            connection_id=connection.context.connection_id,
            operation_id=expected_operation,
            projection_kind="result" if isinstance(request, RuntimeOperationResult) else "review",
            document=projected.document,
        )
    elif isinstance(request, RuntimeOperationManage):
        managed = worker.manage(request.session_id, request.management, frontend=connection.frontend)
        release, expected_action = managed.release, operation_management_action(request.management)
        expected_operation = request.management.operation_id
        reply = RuntimeOperationManaged(
            request_id=request.request_id,
            runtime_boot_id=connection.context.runtime_boot_id,
            connection_id=connection.context.connection_id,
            operation_id=expected_operation,
            document=managed.document,
        )
    else:
        if request.action == "operation_resume":
            acknowledged = worker.resume(request.session_id, request.operation_id, frontend=connection.frontend)
            expected_action = AccessAction.RESUME
        else:
            acknowledged = worker.start(request.session_id, request.operation_id, frontend=connection.frontend)
            expected_action = AccessAction.START
        release = acknowledged.release
        reply = RuntimeOperationAcknowledged(
            request_id=request.request_id,
            runtime_boot_id=connection.context.runtime_boot_id,
            connection_id=connection.context.connection_id,
            operation_id=acknowledged.operation_id,
        )
        expected_operation = request.operation_id
    validate_operation_release(
        release,
        connection=connection,
        profile_id=request.profile_id,
        session_id=request.session_id,
        action=expected_action,
        operation_id=expected_operation,
    )
    return reply, release


def validate_operation_release(
    release: WorkerAuthorityRequest,
    *,
    connection: ProfileConnection,
    profile_id: UUID,
    session_id: UUID,
    action: AccessAction,
    operation_id: OperationId,
) -> None:
    """Correlate a worker's release before its parent acquires the output guard."""
    if (
        release.connection_id != connection.context.connection_id
        or release.session_id != session_id
        or release.request.profile_id != profile_id
        or release.request.frontend != connection.frontend
        or release.request.destination_id != connection.client_id
        or release.request.action is not action
        or release.operation_id != operation_id
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
