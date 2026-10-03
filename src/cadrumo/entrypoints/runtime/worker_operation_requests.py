"""Profile worker request framing and operation-channel dispatch."""

from __future__ import annotations

import asyncio
import time
from contextlib import ExitStack
from uuid import UUID

from pydantic import ValidationError

from ...adapters.local_runtime.runtime_frame_io import read_document, read_secret, write_document
from ...adapters.local_runtime.runtime_transport_cleanup import close_runtime_transport_after_failure
from ...adapters.local_runtime.worker_lease_transfer import read_worker_lease
from ...adapters.local_runtime.worker_transport import WorkerChannel
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.operation_access import operation_management_action
from ...application.runtime.profile_worker import (
    ProfileWorkerLeaseTransferRequest,
    ProfileWorkerManageRequest,
    ProfileWorkerObservation,
    ProfileWorkerObserveRequest,
    ProfileWorkerOperationReceipt,
    ProfileWorkerOperationRequest,
    ProfileWorkerProjection,
    ProfileWorkerProjectionPage,
    ProfileWorkerProjectPageRequest,
    ProfileWorkerProjectRequest,
    ProfileWorkerRefusal,
    ProfileWorkerRequest,
    ProfileWorkerResumeRequest,
    ProfileWorkerSecretRequest,
    ProfileWorkerSubmission,
    ProfileWorkerSubmissionAbortRequest,
    ProfileWorkerSubmissionBeginRequest,
    ProfileWorkerSubmissionChunkRequest,
    ProfileWorkerSubmissionFinishRequest,
    ProfileWorkerSubmitRequest,
    ProfileWorkerUploadAccepted,
)
from ...application.runtime.projection_pages import project_document_page
from ...application.user_profile.access_contracts import AccessAction, AccessDenialCode
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from ...core.async_cleanup import await_cancellation_complete
from .operation_host import ProfileWorkerOperationHost
from .worker_submission_staging import StagedSubmission, WorkerSubmissionStaging


async def receive(channel: WorkerChannel, failed: asyncio.Event, *, control: bool = False) -> ProfileWorkerRequest:
    """Read one bounded worker request, consuming lease transfers only on control."""

    def read() -> ProfileWorkerRequest:
        deadline = time.monotonic() + 5
        request = read_document(channel, ProfileWorkerRequest, deadline=deadline)
        if isinstance(request.root, ProfileWorkerLeaseTransferRequest):
            if not control:
                error = RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                close_runtime_transport_after_failure(channel, error)
                raise error
            return read_worker_lease(channel, request.root, deadline=deadline)
        return request

    while not failed.is_set():
        if channel.read_ready():
            return await await_cancellation_complete(asyncio.to_thread(read), task_name="profile-worker-read")
        await asyncio.sleep(0.02)
    raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)


async def operate(
    channel: WorkerChannel,
    operations: ProfileWorkerOperationHost,
    failed: asyncio.Event,
    uploads: WorkerSubmissionStaging,
) -> None:
    """Dispatch operation-channel requests and serialize refusals on that channel."""
    try:
        while True:
            request = (await receive(channel, failed)).root
            try:
                await _dispatch_request(channel, operations, request, uploads)
            except (AutomationCustodyError, ProfileAccessRefusedError, ValidationError) as refusal:
                if failed.is_set():
                    raise
                write_document(
                    channel,
                    ProfileWorkerRefusal(
                        identity=operations.custody.identity,
                        request_id=request.request_id,
                        reason=AutomationCustodyCode.INVALID
                        if isinstance(refusal, ValidationError)
                        else refusal.reason,
                    ),
                    deadline=time.monotonic() + 5,
                )
    except Exception:
        failed.set()
        raise


async def _dispatch_request(
    channel: WorkerChannel,
    operations: ProfileWorkerOperationHost,
    request: object,
    uploads: WorkerSubmissionStaging,
) -> None:
    if isinstance(
        request,
        ProfileWorkerSubmitRequest
        | ProfileWorkerSubmissionBeginRequest
        | ProfileWorkerSubmissionChunkRequest
        | ProfileWorkerSubmissionFinishRequest
        | ProfileWorkerSubmissionAbortRequest,
    ):
        await _handle_submission(channel, operations, request, uploads)
        return
    if isinstance(request, ProfileWorkerSecretRequest):
        await _handle_secret(channel, operations, request)
        return
    if isinstance(request, ProfileWorkerOperationRequest | ProfileWorkerResumeRequest):
        await _handle_operation(channel, operations, request)
        return
    if isinstance(request, ProfileWorkerObserveRequest):
        await _handle_observation(channel, operations, request)
        return
    if isinstance(request, ProfileWorkerProjectRequest | ProfileWorkerProjectPageRequest):
        await _handle_projection(channel, operations, request)
        return
    if isinstance(request, ProfileWorkerManageRequest):
        await _handle_management(channel, operations, request)
        return
    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)


async def _handle_submission(
    channel: WorkerChannel,
    operations: ProfileWorkerOperationHost,
    request: (
        ProfileWorkerSubmitRequest
        | ProfileWorkerSubmissionBeginRequest
        | ProfileWorkerSubmissionChunkRequest
        | ProfileWorkerSubmissionFinishRequest
        | ProfileWorkerSubmissionAbortRequest
    ),
    uploads: WorkerSubmissionStaging,
) -> None:
    if isinstance(request, ProfileWorkerSubmitRequest):
        await _submit_payload_reply(
            channel,
            operations,
            request_id=request.request_id,
            payload=StagedSubmission(
                session_id=request.session_id,
                frontend=request.frontend,
                definition_id=request.definition_id,
                subject_ref=request.subject_ref,
                payload_json=request.payload_json,
                idempotency_key=request.idempotency_key,
            ),
        )
        return
    if isinstance(request, ProfileWorkerSubmissionBeginRequest):
        operations.contract(request.session_id, request.definition_id)
        uploads.begin(request)
        _write_upload_accepted(channel, operations, request.request_id, request.upload_id)
        return
    if isinstance(request, ProfileWorkerSubmissionChunkRequest):
        operations.custody.require(request.session_id)
        uploads.append(request)
        _write_upload_accepted(channel, operations, request.request_id, request.upload_id)
        return
    if isinstance(request, ProfileWorkerSubmissionFinishRequest):
        staged = uploads.finish(request)
        try:
            await _submit_payload_reply(channel, operations, request_id=request.request_id, payload=staged)
        finally:
            del staged
        return
    uploads.abort(request)
    _write_upload_accepted(channel, operations, request.request_id, request.upload_id)


def _write_upload_accepted(
    channel: WorkerChannel, operations: ProfileWorkerOperationHost, request_id: UUID, upload_id: UUID
) -> None:
    write_document(
        channel,
        ProfileWorkerUploadAccepted(
            identity=operations.custody.identity,
            request_id=request_id,
            upload_id=upload_id,
        ),
        deadline=time.monotonic() + 5,
    )


async def _submit_payload_reply(
    channel: WorkerChannel,
    operations: ProfileWorkerOperationHost,
    *,
    request_id: UUID,
    payload: StagedSubmission,
) -> None:
    """Admit both small and staged payloads through the one canonical owner."""
    submitted = await operations.submit_payload(
        session_id=payload.session_id,
        frontend=payload.frontend,
        definition_id=payload.definition_id,
        subject_ref=payload.subject_ref,
        payload_json=payload.payload_json,
        idempotency_key=payload.idempotency_key,
    )
    async with operations.release(
        payload.session_id, submitted.receipt.operation_id, payload.frontend, AccessAction.SUBMIT
    ) as release:
        write_document(
            channel,
            ProfileWorkerSubmission(
                identity=operations.custody.identity,
                request_id=request_id,
                receipt=submitted.receipt,
                release=release,
            ),
            deadline=time.monotonic() + 5,
        )


async def _handle_secret(
    channel: WorkerChannel, operations: ProfileWorkerOperationHost, request: ProfileWorkerSecretRequest
) -> None:
    # The parent has already performed preflight. Consume the promised bounded
    # frame before rechecking authority so refusal cannot desynchronize the stream.
    with ExitStack() as secrets:
        secret = (
            secrets.enter_context(read_secret(channel, deadline=time.monotonic() + 5))
            if request.action == "operation_secret"
            else None
        )
        async with operations.operation_secret(
            request.session_id, request.requirement, frontend=request.frontend, secret=secret
        ) as release:
            write_document(
                channel,
                ProfileWorkerOperationReceipt(
                    identity=operations.custody.identity,
                    request_id=request.request_id,
                    operation_id=request.requirement.identity.operation_id,
                    release=release,
                ),
                deadline=time.monotonic() + 5,
            )


async def _handle_operation(
    channel: WorkerChannel,
    operations: ProfileWorkerOperationHost,
    request: ProfileWorkerOperationRequest | ProfileWorkerResumeRequest,
) -> None:
    if isinstance(request, ProfileWorkerResumeRequest):
        operation_id = await operations.resume(request.operation_id, request.session_id, frontend=request.frontend)
        action = AccessAction.RESUME
    else:
        operation_id = await operations.start(request.operation_id, request.session_id)
        action = AccessAction.START
    async with operations.release(request.session_id, operation_id, request.frontend, action) as release:
        write_document(
            channel,
            ProfileWorkerOperationReceipt(
                identity=operations.custody.identity,
                request_id=request.request_id,
                operation_id=operation_id,
                release=release,
            ),
            deadline=time.monotonic() + 5,
        )


async def _handle_observation(
    channel: WorkerChannel, operations: ProfileWorkerOperationHost, request: ProfileWorkerObserveRequest
) -> None:
    async with operations.observe(request.session_id, request.observation, frontend=request.frontend) as (
        observation,
        release,
    ):
        write_document(
            channel,
            ProfileWorkerObservation(
                identity=operations.custody.identity,
                request_id=request.request_id,
                observation=observation,
                release=release,
            ),
            deadline=time.monotonic() + 5,
        )


async def _handle_projection(
    channel: WorkerChannel,
    operations: ProfileWorkerOperationHost,
    request: ProfileWorkerProjectRequest | ProfileWorkerProjectPageRequest,
) -> None:
    async with operations.project(request.session_id, request.projection, frontend=request.frontend) as (
        document,
        release,
    ):
        projected = (
            ProfileWorkerProjectionPage(
                identity=operations.custody.identity,
                request_id=request.request_id,
                page=project_document_page(document, request.page),
                release=release,
            )
            if isinstance(request, ProfileWorkerProjectPageRequest)
            else ProfileWorkerProjection(
                identity=operations.custody.identity,
                request_id=request.request_id,
                document=document,
                release=release,
            )
        )
        write_document(channel, projected, deadline=time.monotonic() + 5)


async def _handle_management(
    channel: WorkerChannel, operations: ProfileWorkerOperationHost, request: ProfileWorkerManageRequest
) -> None:
    async with operations.manage(request.session_id, request.management, frontend=request.frontend) as (
        document,
        release,
    ):
        if (
            release.operation_id != request.management.operation_id
            or release.request.action is not operation_management_action(request.management)
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        write_document(
            channel,
            ProfileWorkerProjection(
                identity=operations.custody.identity,
                request_id=request.request_id,
                document=document,
                release=release,
            ),
            deadline=time.monotonic() + 5,
        )
