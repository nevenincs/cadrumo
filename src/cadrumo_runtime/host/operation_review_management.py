"""Operation lifecycle and response management for profile workers."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, JsonValue, TypeAdapter

from cadrumo.application.operations.frontend_requests import (
    OperationCancellationRequestV1,
    OperationDetachRequestV1,
    OperationResponseApplyRequestV1,
    OperationResponseControlRequestV1,
    OperationResponseRejectRequestV1,
)
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.async_cleanup import await_cancellation_complete
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.operation_access import OperationManagementRequest, operation_management_action

if TYPE_CHECKING:
    from cadrumo.application.operations.composition import OperationSubmission
    from cadrumo.application.operations.projection_services import OperationResponseCapability
    from cadrumo.application.operations.registry import OperationFrontendProjection
    from cadrumo_runtime.contracts.worker_authorization import WorkerAuthorityRequest

    from .operation_host import ProfileWorkerOperationHost

_PROJECTION_DOCUMENT = TypeAdapter(dict[str, JsonValue])


def _validate_response_authority(
    host: ProfileWorkerOperationHost, request: OperationManagementRequest, session_id: UUID
) -> OperationResponseCapability | None:
    submission = host.submissions.get(request.operation_id)
    capability = None if submission is None else submission[1].response_capability
    if isinstance(request, OperationResponseControlRequestV1) and (
        request.actor_ref != f"session:{session_id}"
        or submission is None
        or submission[0] != session_id
        or capability is None
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED)
    return capability


async def _execute_control(
    host: ProfileWorkerOperationHost,
    request: OperationManagementRequest,
    submission: tuple[UUID, OperationSubmission] | None,
    capability: OperationResponseCapability | None,
) -> BaseModel:
    services = host.composed()
    if isinstance(request, OperationCancellationRequestV1):
        return await services.cancellation.request(request)
    if isinstance(request, OperationDetachRequestV1):
        return await services.detach.detach(request)
    # The exact original capability stays local. A new session,
    # idempotent receipt or reattached operation cannot obtain it.
    if submission is None:
        raise ProfileAccessRefusedError(AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED)
    if isinstance(request, OperationResponseApplyRequestV1):
        response = await services.response(request, capability)
        return await response.apply(request)
    if isinstance(request, OperationResponseRejectRequestV1):
        response = await services.response(request, capability)
        return await response.reject(request)
    response = await services.inspect_response(request, capability)
    return await response.inspect(request)


@asynccontextmanager
async def manage_operation(
    host: ProfileWorkerOperationHost,
    session_id: UUID,
    request: OperationManagementRequest,
    *,
    frontend: OperationFrontendProjection,
) -> AsyncGenerator[tuple[dict[str, JsonValue], WorkerAuthorityRequest]]:
    """Use canonical controls without recovering an earlier session's response proof."""
    submission = host.submissions.get(request.operation_id)
    capability = _validate_response_authority(host, request, session_id)
    async with host.release(session_id, request.operation_id, frontend, operation_management_action(request)) as (
        authorization
    ):
        result = await await_cancellation_complete(
            _execute_control(host, request, submission, capability), task_name="profile-operation-control"
        )
        document = _PROJECTION_DOCUMENT.validate_python(result.model_dump(mode="json", serialize_as_any=True))
        yield document, authorization
