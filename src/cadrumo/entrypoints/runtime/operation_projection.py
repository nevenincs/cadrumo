"""Prepare canonical private replies for the runtime's final disclosure guard."""

from __future__ import annotations

from ...application.runtime.operation_access import (
    RuntimeOperationAcknowledged,
    RuntimeOperationControl,
    RuntimeOperationObserve,
    RuntimeOperationObserved,
    RuntimeOperationReply,
    RuntimeOperationSubmit,
    RuntimeOperationSubmitted,
)
from ...application.runtime.worker_authorization import WorkerAuthorizationRequest
from ...application.user_profile.access_contracts import AccessAction, AccessDenialCode
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from .profile_host import ProfileConnection, RuntimeProfileHost


def prepare_operation_projection(
    host: RuntimeProfileHost,
    connection: ProfileConnection,
    request: RuntimeOperationSubmit | RuntimeOperationControl | RuntimeOperationObserve,
) -> tuple[RuntimeOperationReply, WorkerAuthorizationRequest]:
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
    if (
        release.connection_id != connection.context.connection_id
        or release.session_id != request.session_id
        or release.request.profile_id != request.profile_id
        or release.request.frontend != connection.frontend
        or release.request.destination_id != connection.client_id
        or release.request.action is not expected_action
        or release.operation_id != expected_operation
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    return reply, release
