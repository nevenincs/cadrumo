"""Profile worker request framing and operation-channel dispatch."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncGenerator
from contextlib import ExitStack, asynccontextmanager
from typing import TypeGuard
from uuid import UUID

from pydantic import BaseModel, ValidationError

from cadrumo.application.operations.frontend_requests import (
    OperationResponseControlRequestV1,
    OperationResultProjectionRequestV1,
)
from cadrumo.application.operations.models import OperationId
from cadrumo.application.user_profile.access_contracts import AccessAction, AccessDenialCode
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo.core.async_cleanup import await_cancellation_complete
from cadrumo.core.errors.hierarchy import CadrumoError
from cadrumo.core.logging import get_logger
from cadrumo.core.request_faults import registered_error_fault
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.operation_access import operation_management_action
from cadrumo_client.contracts.projection_pages import PROJECTION_PAGE_BYTES, project_document_page
from cadrumo_client.contracts.submission_payload import FinancialOperandInputDescriptor
from cadrumo_client.transport.frame_io import read_document, read_secret, write_document
from cadrumo_client.transport.transport_cleanup import close_transport_after_failure
from cadrumo_runtime.contracts.profile_worker import (
    ProfileWorkerContractRequest,
    ProfileWorkerLeaseTransferRequest,
    ProfileWorkerManageRequest,
    ProfileWorkerObservation,
    ProfileWorkerObserveRequest,
    ProfileWorkerOperationContract,
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

from ..adapters.worker_lease_transfer import read_worker_lease
from ..adapters.worker_transport import WorkerChannel
from .operation_host import ProfileWorkerOperationHost
from .worker_submission_staging import StagedSubmission, WorkerSubmissionStaging

_LOGGER = get_logger(__name__)


async def receive(channel: WorkerChannel, failed: asyncio.Event, *, control: bool = False) -> ProfileWorkerRequest:
    """Read one bounded worker request, consuming lease transfers only on control."""

    def read() -> ProfileWorkerRequest:
        deadline = time.monotonic() + 5
        request = read_document(channel, ProfileWorkerRequest, deadline=deadline)
        if isinstance(request.root, ProfileWorkerLeaseTransferRequest):
            if not control:
                error = RefusalError(RefusalCode.INVALID_FRAME)
                close_transport_after_failure(channel, error)
                raise error
            return read_worker_lease(channel, request.root, deadline=deadline)
        return request

    while not failed.is_set():
        if channel.read_ready():
            return await await_cancellation_complete(asyncio.to_thread(read), task_name="profile-worker-read")
        await asyncio.sleep(0.02)
    raise RefusalError(RefusalCode.UNAVAILABLE)


async def operate(
    channel: WorkerChannel,
    operations: ProfileWorkerOperationHost,
    failed: asyncio.Event,
    uploads: WorkerSubmissionStaging,
    changed: asyncio.Event,
) -> None:
    """Dispatch operation-channel requests and serialize refusals on that channel.

    ``changed`` wakes custody expiry after each request, which may have staged an upload.
    """
    try:
        while True:
            request = (await receive(channel, failed)).root
            try:
                await _dispatch_request(channel, operations, request, uploads)
            except (AutomationCustodyError, ProfileAccessRefusedError, ValidationError) as refusal:
                if failed.is_set():
                    raise
                if isinstance(refusal, ProfileAccessRefusedError):
                    _LOGGER.warning("worker operation access refused code=%s", refusal.reason, exc_info=refusal)
                write_document(
                    channel,
                    ProfileWorkerRefusal(
                        identity=operations.custody.identity,
                        request_id=request.request_id,
                        reason=AutomationCustodyCode.INVALID
                        if isinstance(refusal, ValidationError)
                        else refusal.reason,
                        request_faults=refusal.request_faults if isinstance(refusal, AutomationCustodyError) else (),
                        holder_operation_id=refusal.holder_operation_id
                        if isinstance(refusal, ProfileAccessRefusedError)
                        else None,
                    ),
                    deadline=time.monotonic() + 5,
                )
            finally:
                del request
                changed.set()
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
    if _is_read(request):
        await _serve_read(channel, operations, request)
        return
    if isinstance(request, ProfileWorkerManageRequest):
        async with _management_reply(operations, request) as reply:
            write_document(channel, reply, deadline=time.monotonic() + 5)
        return
    if isinstance(request, ProfileWorkerContractRequest):
        await describe_contract(channel, operations, request)
        return
    raise RefusalError(RefusalCode.INVALID_FRAME)


async def describe_contract(
    channel: WorkerChannel, operations: ProfileWorkerOperationHost, request: ProfileWorkerContractRequest
) -> None:
    """Answer one contract on the operation channel, composing the registry if this is its first use.

    The composition and schema projection run off the service loop, and the
    handler retains its ownership if shutdown cancels it while the thread
    still uses the host.
    """
    description = await await_cancellation_complete(
        asyncio.to_thread(operations.describe, request.session_id, request.definition_id),
        task_name="profile-worker-description",
    )
    write_document(
        channel,
        ProfileWorkerOperationContract(
            identity=operations.custody.identity,
            request_id=request.request_id,
            contract=description.contract,
            request_json_schema=description.request_json_schema,
        ),
        deadline=time.monotonic() + 5,
    )


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
        contract = operations.contract(request.session_id, request.definition_id)
        if isinstance(request.descriptor, FinancialOperandInputDescriptor) != (
            contract.transient_financial_operand is not None
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        if isinstance(request.descriptor, FinancialOperandInputDescriptor) and request.idempotency_key is not None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
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
    if payload.financial_input:
        submitted = await operations.submit_financial_input(
            session_id=payload.session_id,
            frontend=payload.frontend,
            definition_id=payload.definition_id,
            subject_ref=payload.subject_ref,
            input_json=payload.payload_json,
        )
    else:
        submitted = await operations.submit_payload(
            session_id=payload.session_id,
            frontend=payload.frontend,
            definition_id=payload.definition_id,
            subject_ref=payload.subject_ref,
            payload_json=payload.payload_json,
            idempotency_key=payload.idempotency_key,
        )
    async with operations.release_submission(
        payload.session_id, submitted.receipt.operation_id, payload.frontend
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


type _ReadRequest = (
    ProfileWorkerObserveRequest
    | ProfileWorkerProjectRequest
    | ProfileWorkerProjectPageRequest
    | ProfileWorkerManageRequest
)


def _is_read(request: object) -> TypeGuard[_ReadRequest]:
    """Tell whether a request only reads: an observation, a projection, a page, or the inspection of a review."""
    if isinstance(request, ProfileWorkerManageRequest):
        # Applying and rejecting a review extend this request type; only the type itself inspects.
        return type(request.management) is OperationResponseControlRequestV1
    return isinstance(
        request, ProfileWorkerObserveRequest | ProfileWorkerProjectRequest | ProfileWorkerProjectPageRequest
    )


def read_refusal(fault: Exception) -> AutomationCustodyError | ProfileAccessRefusedError | None:
    """Return the refusal that answers what stopped a read, or ``None`` for what must still end the channel.

    A registered error is answered with its own code and the message the
    command line prints for it. An unregistered lookup, value or type fault is
    answered with the generic refusal of a read and no text, because its
    message is wording nobody chose and may hold anything; its type is logged.
    A typed refusal already answers, and a transport refusal says the channel
    this worker asks the runtime for authority on can no longer be trusted, so
    neither is replaced.
    """
    if isinstance(fault, AutomationCustodyError | ProfileAccessRefusedError | ValidationError | RefusalError):
        return None
    if isinstance(fault, CadrumoError):
        return AutomationCustodyError(AutomationCustodyCode.INVALID, request_faults=(registered_error_fault(fault),))
    if isinstance(fault, ValueError | LookupError | TypeError):
        _LOGGER.error("worker read stopped by an unexpected fault exception_type=%s", type(fault).__name__)
        return ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return None


async def _serve_read(channel: WorkerChannel, operations: ProfileWorkerOperationHost, request: _ReadRequest) -> None:
    """Answer one read, turning whatever stops it before its reply into a refusal.

    A read changes nothing, so whatever stops it leaves no outcome to
    misreport and a refusal is always a true answer: the worker that every
    session of the profile shares serves on. An act that starts, resumes,
    answers or stops an operation can fail after it took effect, where a
    refusal would deny an effect that exists, so those are not answered here.
    Once the reply is being written the fault belongs to the channel and is
    not answered a second time.
    """
    prepared = False
    try:
        async with _read_reply(operations, request) as reply:
            prepared = True
            write_document(channel, reply, deadline=time.monotonic() + 5)
    except Exception as fault:
        refusal = None if prepared else read_refusal(fault)
        if refusal is None:
            raise
        raise refusal from None
    delivered = _delivered_result(request, reply)
    if delivered is not None:
        operations.release_delivered_result(delivered)


def _delivered_result(request: _ReadRequest, reply: BaseModel) -> OperationId | None:
    """Name the operation whose whole settled result this written reply completed, if any."""
    if not isinstance(request, ProfileWorkerProjectRequest | ProfileWorkerProjectPageRequest):
        return None
    if not isinstance(request.projection, OperationResultProjectionRequestV1):
        return None
    if isinstance(reply, ProfileWorkerProjectionPage) and (
        reply.page.offset + PROJECTION_PAGE_BYTES < reply.page.total_bytes
    ):
        return None
    return request.projection.operation_id


@asynccontextmanager
async def _read_reply(operations: ProfileWorkerOperationHost, request: _ReadRequest) -> AsyncGenerator[BaseModel]:
    """Lend the reply of one read while its disclosure guard is held."""
    if isinstance(request, ProfileWorkerManageRequest):
        async with _management_reply(operations, request) as managed:
            yield managed
        return
    if isinstance(request, ProfileWorkerObserveRequest):
        async with operations.observe(request.session_id, request.observation, frontend=request.frontend) as (
            observation,
            release,
        ):
            yield ProfileWorkerObservation(
                identity=operations.custody.identity,
                request_id=request.request_id,
                observation=observation,
                release=release,
            )
        return
    async with operations.project(request.session_id, request.projection, frontend=request.frontend) as (
        document,
        release,
    ):
        if isinstance(request, ProfileWorkerProjectPageRequest):
            yield ProfileWorkerProjectionPage(
                identity=operations.custody.identity,
                request_id=request.request_id,
                page=project_document_page(document, request.page),
                release=release,
            )
        else:
            yield ProfileWorkerProjection(
                identity=operations.custody.identity,
                request_id=request.request_id,
                document=document,
                release=release,
            )


@asynccontextmanager
async def _management_reply(
    operations: ProfileWorkerOperationHost, request: ProfileWorkerManageRequest
) -> AsyncGenerator[ProfileWorkerProjection]:
    """Lend the reply of one control or response request while its guard is held."""
    async with operations.manage(request.session_id, request.management, frontend=request.frontend) as (
        document,
        release,
    ):
        if (
            release.operation_id != request.management.operation_id
            or release.request.action is not operation_management_action(request.management)
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        yield ProfileWorkerProjection(
            identity=operations.custody.identity,
            request_id=request.request_id,
            document=document,
            release=release,
        )
