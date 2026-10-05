"""Profile worker service loop and owner-controlled shutdown."""

from __future__ import annotations

import asyncio
import sys
import time
from contextlib import suppress
from dataclasses import dataclass
from typing import Literal

from pydantic import ValidationError

from ...adapters.local_runtime.runtime_frame_io import read_secret, write_document
from ...adapters.local_runtime.worker_transport import WorkerChannel
from ...adapters.persistence.storage.custody.sign_in_generation import SignInGeneration
from ...adapters.persistence.storage.master_key.profile_worker_custody import ProfileWorkerCustody
from ...application.operations.drain import OperationDrainResult
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.profile_worker import (
    ProfileWorkerContractRequest,
    ProfileWorkerControlRequest,
    ProfileWorkerDrained,
    ProfileWorkerHumanBindingRequest,
    ProfileWorkerHumanBound,
    ProfileWorkerHumanOutcome,
    ProfileWorkerHumanReceiptRequest,
    ProfileWorkerLeaseRequest,
    ProfileWorkerManageRequest,
    ProfileWorkerObserveRequest,
    ProfileWorkerOperationContract,
    ProfileWorkerOperationRequest,
    ProfileWorkerProjectRequest,
    ProfileWorkerRefusal,
    ProfileWorkerResumeRequest,
    ProfileWorkerRetireRequest,
    ProfileWorkerSecretRequest,
    ProfileWorkerSettlement,
    ProfileWorkerSettlementRequest,
    ProfileWorkerStatus,
    ProfileWorkerSubmissionAbortRequest,
    ProfileWorkerSubmissionBeginRequest,
    ProfileWorkerSubmissionChunkRequest,
    ProfileWorkerSubmissionFinishRequest,
    ProfileWorkerSubmitRequest,
)
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from ...core.async_cleanup import await_cancellation_complete, close_async_resources
from ...core.logging import get_logger
from ...core.startup_phase_log import startup_phase
from . import worker_cleanup as _worker_cleanup
from . import worker_operation_requests as _worker_requests
from .operation_host import ProfileWorkerOperationHost
from .profile_login import ProfileWorkerHumanLogin
from .worker_submission_staging import WorkerSubmissionStaging

_ControlDisposition = Literal["handled", "status", "stop"]
_log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class _WorkerControl:
    """Dependencies shared by the parent-command handlers."""

    channel: WorkerChannel
    custody: ProfileWorkerCustody
    human: ProfileWorkerHumanLogin
    operations: ProfileWorkerOperationHost
    uploads: WorkerSubmissionStaging
    failed: asyncio.Event
    operation_release: _worker_cleanup.WorkerRelease[OperationDrainResult]
    upload_release: _worker_cleanup.WorkerRelease[None]


async def _expire_custody(
    stop: asyncio.Event,
    failed: asyncio.Event,
    custody: ProfileWorkerCustody,
    uploads: WorkerSubmissionStaging,
    human: ProfileWorkerHumanLogin,
) -> None:
    while not stop.is_set():
        await asyncio.sleep(0.1)
        try:
            live_sessions = await asyncio.to_thread(custody.live_sessions)
            uploads.expire(live_sessions=live_sessions)
            await asyncio.to_thread(human.expire)
        except Exception:
            failed.set()
            return


async def _handle_custody_control(context: _WorkerControl, request: object) -> _ControlDisposition | None:
    if isinstance(request, ProfileWorkerLeaseRequest):
        if request.action == "install":
            with read_secret(context.channel, deadline=time.monotonic() + 5) as secret:
                context.custody.install(request.lease, secret)
            context.operations.prepare()
        elif request.action == "refresh":
            context.custody.refresh(request.lease)
        else:
            context.custody.share(request.lease)
        return "status"
    if isinstance(request, ProfileWorkerRetireRequest):
        context.human.discard(request.session_id)
        context.custody.retire(request.session_id)
        context.uploads.expire(live_sessions=context.custody.live_sessions())
        return "status"
    if isinstance(request, ProfileWorkerHumanBindingRequest):
        receipt, pending = context.human.bind(
            request.candidate_id, request.lease, persist_receipt=request.persist_receipt
        )
        write_document(
            context.channel,
            ProfileWorkerHumanBound(
                identity=context.custody.identity,
                request_id=request.request_id,
                session_id=request.lease.session_id,
                receipt=receipt,
                receipt_pending=pending,
            ),
            deadline=time.monotonic() + 5,
        )
        return "handled"
    if isinstance(request, ProfileWorkerHumanReceiptRequest):
        receipt = context.human.mint_receipt(
            request.session_id,
            SignInGeneration(lineage=request.sign_in_lineage, generation=request.sign_in_generation),
        )
        write_document(
            context.channel,
            ProfileWorkerHumanBound(
                identity=context.custody.identity,
                request_id=request.request_id,
                session_id=request.session_id,
                receipt=receipt,
            ),
            deadline=time.monotonic() + 5,
        )
        return "handled"
    return None


async def _handle_metadata_control(context: _WorkerControl, request: object) -> _ControlDisposition | None:
    if isinstance(request, ProfileWorkerContractRequest):
        description = context.operations.describe(request.session_id, request.definition_id)
        write_document(
            context.channel,
            ProfileWorkerOperationContract(
                identity=context.custody.identity,
                request_id=request.request_id,
                contract=description.contract,
                request_json_schema=description.request_json_schema,
            ),
            deadline=time.monotonic() + 5,
        )
        return "handled"
    if isinstance(request, ProfileWorkerSettlementRequest):
        settled = await context.operations.settlement(request.operation_identity, timeout=request.wait_seconds)
        write_document(
            context.channel,
            ProfileWorkerSettlement(
                identity=context.custody.identity,
                request_id=request.request_id,
                operation_identity=request.operation_identity,
                settled=settled,
            ),
            deadline=time.monotonic() + 5,
        )
        return "handled"
    return None


async def _handle_human_control(
    context: _WorkerControl, request: object, failed: asyncio.Event
) -> _ControlDisposition | None:
    if not isinstance(request, ProfileWorkerControlRequest) or request.action not in {"password", "receipt"}:
        return None
    with (
        startup_phase(_log, "worker_human_proof"),
        read_secret(context.channel, deadline=time.monotonic() + 5) as secret,
    ):
        if request.action == "password":
            candidate, login = context.human.authenticate(secret)
        else:
            candidate, login = context.human.resume(secret, login_id=request.originating_login_id)
    try:
        context.operations.prepare()
    except BaseException as primary:
        try:
            context.human.cancel()
        except BaseException as cleanup:
            _worker_cleanup.retain_task_failures(primary, (cleanup,))
            failed.set()
        raise
    write_document(
        context.channel,
        ProfileWorkerHumanOutcome(
            identity=context.custody.identity,
            request_id=request.request_id,
            candidate_id=candidate,
            login=login,
        ),
        deadline=time.monotonic() + 5,
    )
    return "handled"


async def _handle_action_control(context: _WorkerControl, request: object) -> _ControlDisposition | None:
    if not isinstance(request, ProfileWorkerControlRequest):
        return None
    if request.action == "prepare_api":
        context.operations.prepare()
        return "status"
    if request.action == "cancel_human":
        context.human.cancel()
        return "status"
    if request.action != "stop":
        return None
    await context.upload_release.close()
    drained = await context.operation_release.release()
    write_document(
        context.channel,
        ProfileWorkerDrained(
            identity=context.custody.identity,
            request_id=request.request_id,
            unresolved=drained.unresolved,
            recovery_required=drained.recovery_required,
        ),
        deadline=time.monotonic() + 5,
    )
    # Keep the pipe open until the parent consumes the reply and contains this scope.
    with suppress(RuntimeRefusalError):
        await asyncio.to_thread(context.channel.read_exact, 1, deadline=time.monotonic() + 5)
    return "stop"


async def _dispatch_control_request(context: _WorkerControl, request: object) -> _ControlDisposition:
    if isinstance(
        request,
        ProfileWorkerSubmitRequest
        | ProfileWorkerSubmissionBeginRequest
        | ProfileWorkerSubmissionChunkRequest
        | ProfileWorkerSubmissionFinishRequest
        | ProfileWorkerSubmissionAbortRequest
        | ProfileWorkerOperationRequest
        | ProfileWorkerObserveRequest
        | ProfileWorkerResumeRequest
        | ProfileWorkerProjectRequest
        | ProfileWorkerManageRequest
        | ProfileWorkerSecretRequest,
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    disposition = await _handle_custody_control(context, request)
    if disposition is not None:
        return disposition
    disposition = await _handle_metadata_control(context, request)
    if disposition is not None:
        return disposition
    disposition = await _handle_human_control(context, request, context.failed)
    if disposition is not None:
        return disposition
    disposition = await _handle_action_control(context, request)
    return disposition if disposition is not None else "status"


async def _serve_control_requests(context: _WorkerControl) -> None:
    while not context.failed.is_set():
        request = (await _worker_requests.receive(context.channel, context.failed, control=True)).root
        if context.failed.is_set():
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        try:
            disposition = await _dispatch_control_request(context, request)
            if disposition == "stop":
                return
            if disposition == "status":
                result = ProfileWorkerStatus(
                    identity=context.custody.identity,
                    request_id=request.request_id,
                    sessions=context.custody.live_sessions(),
                )
                write_document(context.channel, result, deadline=time.monotonic() + 5)
        except (AutomationCustodyError, ProfileAccessRefusedError, ValidationError) as refusal:
            if context.failed.is_set():
                raise
            write_document(
                context.channel,
                ProfileWorkerRefusal(
                    identity=context.custody.identity,
                    request_id=request.request_id,
                    reason=AutomationCustodyCode.INVALID if isinstance(refusal, ValidationError) else refusal.reason,
                ),
                deadline=time.monotonic() + 5,
            )


async def _collect_task_failures(
    expiry: asyncio.Task[None], executing: asyncio.Task[None], primary_error: BaseException | None
) -> tuple[BaseException | None, tuple[BaseException, ...]]:
    task_failures: list[BaseException] = []

    async def settle() -> None:
        for task in (expiry, executing):
            try:
                await task
            except asyncio.CancelledError as cancellation:
                if any(
                    isinstance(cancellation.__dict__.get(name), BaseException)
                    for name in ("async_cleanup_error", "cleanup_error", "body_error")
                ):
                    task_failures.append(cancellation)
            except BaseException as failure:
                task_failures.append(failure)

    try:
        await await_cancellation_complete(
            settle(),
            task_name="profile-worker-tasks-stop",
            cancellation=primary_error if isinstance(primary_error, asyncio.CancelledError) else None,
        )
    except asyncio.CancelledError as cancellation:
        if primary_error is not None and not isinstance(primary_error, asyncio.CancelledError):
            cancellation.__dict__["body_error"] = primary_error
        primary_error = cancellation
    return primary_error, tuple(task_failures)


async def _finish_service(
    stop: asyncio.Event,
    expiry: asyncio.Task[None],
    executing: asyncio.Task[None],
    operation_release: _worker_cleanup.WorkerRelease[OperationDrainResult],
    human_release: _worker_cleanup.WorkerRelease[None],
    upload_release: _worker_cleanup.WorkerRelease[None],
    primary_error: BaseException | None,
) -> None:
    stop.set()
    executing.cancel()
    primary_error, task_failures = await _collect_task_failures(expiry, executing, primary_error)
    raise_task_failure = primary_error is None and bool(task_failures)
    if raise_task_failure:
        primary_error = task_failures[0]
    if primary_error is not None and task_failures:
        _worker_cleanup.retain_task_failures(primary_error, task_failures)
    await close_async_resources(
        operation_release,
        human_release,
        upload_release,
        task_name="profile-worker-serve-close",
        primary_error=primary_error,
    )
    if raise_task_failure and primary_error is not None:
        raise primary_error


async def _serve(
    channel: WorkerChannel,
    operation_channel: WorkerChannel,
    custody: ProfileWorkerCustody,
    human: ProfileWorkerHumanLogin,
    operations: ProfileWorkerOperationHost,
) -> None:
    stop, failed = asyncio.Event(), asyncio.Event()
    uploads = WorkerSubmissionStaging()
    operation_release = _worker_cleanup.WorkerRelease(operations.close)
    human_release = _worker_cleanup.WorkerRelease(lambda: asyncio.to_thread(human.close))
    upload_release = _worker_cleanup.WorkerRelease(lambda: asyncio.to_thread(uploads.close))
    context = _WorkerControl(
        channel=channel,
        custody=custody,
        human=human,
        operations=operations,
        uploads=uploads,
        failed=failed,
        operation_release=operation_release,
        upload_release=upload_release,
    )
    expiry = asyncio.create_task(_expire_custody(stop, failed, custody, uploads, human), name="profile-custody-expiry")
    executing = asyncio.create_task(
        _worker_requests.operate(operation_channel, operations, failed, uploads), name="profile-operation-requests"
    )
    try:
        await _serve_control_requests(context)
    finally:
        await _finish_service(
            stop,
            expiry,
            executing,
            operation_release,
            human_release,
            upload_release,
            sys.exception(),
        )
