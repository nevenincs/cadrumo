"""Profile worker service loop and owner-controlled shutdown."""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from contextlib import suppress
from dataclasses import dataclass
from typing import Literal

from pydantic import ValidationError

from cadrumo.adapters.persistence.storage.custody.sign_in_generation import SignInGeneration
from cadrumo.adapters.persistence.storage.master_key.profile_worker_custody import ProfileWorkerCustody
from cadrumo.application.operations.drain import OperationDrainResult
from cadrumo.application.user_profile.access_contracts import SessionKind
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo.core.async_cleanup import await_cancellation_complete, close_async_resources
from cadrumo.core.diagnostic_log import diagnostic_error_fields, diagnostic_event
from cadrumo.core.logging import get_logger
from cadrumo.core.startup_phase_log import startup_phase
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.extension_records import ProfileWorkerExtensionRecordRequest
from cadrumo_client.transport.frame_io import read_secret, write_document
from cadrumo_runtime.contracts.profile_worker import (
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

from ..adapters.worker_transport import WorkerChannel
from . import worker_cleanup as _worker_cleanup
from . import worker_operation_requests as _worker_requests
from .operation_host import ProfileWorkerOperationHost
from .profile_login import ProfileWorkerHumanLogin
from .worker_submission_staging import WorkerSubmissionStaging

_ControlDisposition = Literal["handled", "status", "stop"]
_CONTROL_DISPATCH_SLOW_SECONDS = 0.5
_EXPIRY_MARGIN_SECONDS = 0.05
_log = get_logger(__name__)

_CONTROL_REQUEST_TYPES = (
    ProfileWorkerControlRequest,
    ProfileWorkerLeaseRequest,
    ProfileWorkerRetireRequest,
    ProfileWorkerHumanBindingRequest,
    ProfileWorkerHumanReceiptRequest,
    ProfileWorkerSettlementRequest,
    ProfileWorkerExtensionRecordRequest,
    ProfileWorkerContractRequest,
    ProfileWorkerSubmitRequest,
    ProfileWorkerSubmissionBeginRequest,
    ProfileWorkerSubmissionChunkRequest,
    ProfileWorkerSubmissionFinishRequest,
    ProfileWorkerSubmissionAbortRequest,
    ProfileWorkerOperationRequest,
    ProfileWorkerObserveRequest,
    ProfileWorkerResumeRequest,
    ProfileWorkerProjectRequest,
    ProfileWorkerManageRequest,
    ProfileWorkerSecretRequest,
)
_CONTROL_ACTIONS = frozenset(
    {
        "install",
        "refresh",
        "share",
        "lease_transfer",
        "retire",
        "operation_settlement",
        "status",
        "stop",
        "password",
        "receipt",
        "cancel_human",
        "prepare_api",
        "bind_human",
        "mint_human_receipt",
        "operation_contract",
        "operation_submit",
        "operation_submit_begin",
        "operation_submit_chunk",
        "operation_submit_finish",
        "operation_submit_abort",
        "operation_start",
        "operation_secret_ready",
        "operation_secret",
        "operation_observe",
        "operation_resume",
        "operation_project",
        "operation_project_page",
        "operation_manage",
        "extension_record",
    }
)


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
    changed: asyncio.Event


async def _until_change(stop: asyncio.Event, changed: asyncio.Event, delay: float | None) -> None:
    """Wait for the next deadline, a handled command or service stop, whichever comes first."""
    waiters = (asyncio.ensure_future(stop.wait()), asyncio.ensure_future(changed.wait()))
    try:
        # The margin lets a coarse OS timer wake after the deadline instead of just before it.
        timeout = None if delay is None else delay + _EXPIRY_MARGIN_SECONDS
        await asyncio.wait(waiters, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for waiter in waiters:
            waiter.cancel()
        await asyncio.gather(*waiters, return_exceptions=True)


async def _expire_custody(
    stop: asyncio.Event,
    failed: asyncio.Event,
    custody: ProfileWorkerCustody,
    uploads: WorkerSubmissionStaging,
    human: ProfileWorkerHumanLogin,
    changed: asyncio.Event,
) -> None:
    """Release custody at each lease, login and upload deadline; every handled command wakes it early."""
    # A new worker holds nothing until a command arrives, so it starts by waiting.
    delay: float | None = None
    while True:
        await _until_change(stop, changed, delay)
        if stop.is_set():
            return
        changed.clear()
        try:
            live_sessions = await asyncio.to_thread(custody.live_sessions)
            uploads.expire(live_sessions=live_sessions)
            await asyncio.to_thread(human.expire)
            deadlines = [
                seconds
                for seconds in (
                    custody.seconds_until_expiry(),
                    uploads.seconds_until_expiry(),
                    human.seconds_until_expiry(),
                )
                if seconds is not None
            ]
        except Exception as error:
            failed.set()
            diagnostic_event(
                _log,
                "profile_worker_custody_observation_failed",
                fields=diagnostic_error_fields(error),
                level=40,
                primary_error=error,
            )
            raise
        delay = min(deadlines) if deadlines else None


async def _handle_custody_control(context: _WorkerControl, request: object) -> _ControlDisposition | None:
    if isinstance(request, ProfileWorkerLeaseRequest):
        if request.action == "install":
            with read_secret(context.channel, deadline=time.monotonic() + 5) as secret:
                context.custody.install(request.lease, secret)
            context.operations.prepare()
        elif request.action == "refresh":
            if request.lease.kind is SessionKind.HUMAN:
                context.human.refresh(request.lease)
            else:
                context.custody.refresh(request.lease)
        else:
            context.custody.share(request.lease)
        return "status"
    if isinstance(request, ProfileWorkerRetireRequest):
        context.human.discard(request.session_id)
        context.custody.retire(request.session_id)
        live_sessions = context.custody.live_sessions()
        context.uploads.expire(live_sessions=live_sessions)
        if not live_sessions:
            # Locking or signing out ends the last session but not this worker.
            context.operations.forget_settled_ephemeral()
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


async def _handle_human_control(context: _WorkerControl, request: object) -> _ControlDisposition | None:
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
    # A sign-in never composes the registry; the first operation does.
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
    with suppress(RefusalError):
        await asyncio.to_thread(context.channel.read_exact, 1, deadline=time.monotonic() + 5)
    return "stop"


async def _dispatch_control_request(context: _WorkerControl, request: object) -> _ControlDisposition:
    if isinstance(
        request,
        # A contract may compose the registry; it travels on the operation
        # channel so sign-in and custody control never queue behind it.
        ProfileWorkerContractRequest
        | ProfileWorkerSubmitRequest
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
        raise RefusalError(RefusalCode.INVALID_FRAME)
    if isinstance(request, ProfileWorkerExtensionRecordRequest):
        from .worker_extension_records import serve_extension_record

        await asyncio.to_thread(serve_extension_record, context.channel, context.custody, request)
        return "handled"

    disposition = await _handle_custody_control(context, request)
    if disposition is not None:
        return disposition
    disposition = await _handle_metadata_control(context, request)
    if disposition is not None:
        return disposition
    disposition = await _handle_human_control(context, request)
    if disposition is not None:
        return disposition
    disposition = await _handle_action_control(context, request)
    return disposition if disposition is not None else "status"


def _control_dispatch_metadata(request: object) -> dict[str, str | None]:
    """Project only closed worker request, handler and action labels for diagnostics."""
    request_type = type(request).__name__ if type(request) in _CONTROL_REQUEST_TYPES else "UnknownWorkerRequest"
    if type(request) in {
        ProfileWorkerLeaseRequest,
        ProfileWorkerRetireRequest,
        ProfileWorkerHumanBindingRequest,
        ProfileWorkerHumanReceiptRequest,
    }:
        handler_name = "custody_control"
    elif type(request) is ProfileWorkerSettlementRequest:
        handler_name = "metadata_control"
    elif type(request) is ProfileWorkerExtensionRecordRequest:
        handler_name = "extension_record"
    elif isinstance(request, ProfileWorkerControlRequest) and request.action in {"password", "receipt"}:
        handler_name = "human_control"
    elif type(request) is ProfileWorkerControlRequest:
        handler_name = "action_control"
    else:
        handler_name = "control_dispatch"
    candidate_action = getattr(request, "action", None) if type(request) in _CONTROL_REQUEST_TYPES else None
    action = candidate_action if isinstance(candidate_action, str) and candidate_action in _CONTROL_ACTIONS else None
    return {"handler_name": handler_name, "request_type": request_type, "request_action": action}


def _record_control_dispatch_started(request: object) -> None:
    """Mark which validated control request is active if its synchronous handler stalls."""
    try:
        diagnostic_event(
            _log,
            "profile_worker_control_dispatch_started",
            fields={**_control_dispatch_metadata(request), "outcome": "started"},
        )
    except BaseException:
        return


def _record_control_dispatch_elapsed(
    request: object,
    *,
    handler_started: float,
    outcome: str,
    primary_error: BaseException | None = None,
) -> None:
    """Log only slow dispatches and bounded request/handler labels, never frame contents."""
    elapsed = max(0.0, time.monotonic() - handler_started)
    if elapsed < _CONTROL_DISPATCH_SLOW_SECONDS:
        return
    try:
        diagnostic_event(
            _log,
            "profile_worker_control_dispatch_slow",
            fields={
                **_control_dispatch_metadata(request),
                "elapsed_seconds": round(elapsed, 3),
                "outcome": outcome,
            },
            level=logging.WARNING,
            primary_error=primary_error,
        )
    except BaseException:
        return


async def _serve_control_requests(context: _WorkerControl) -> None:
    while not context.failed.is_set():
        request = (await _worker_requests.receive(context.channel, context.failed, control=True)).root
        if context.failed.is_set():
            raise RefusalError(RefusalCode.UNAVAILABLE)
        try:
            _record_control_dispatch_started(request)
            dispatch_started = time.monotonic()
            try:
                disposition = await _dispatch_control_request(context, request)
            except BaseException as error:
                _record_control_dispatch_elapsed(
                    request,
                    handler_started=dispatch_started,
                    outcome="raised",
                    primary_error=error,
                )
                raise
            _record_control_dispatch_elapsed(request, handler_started=dispatch_started, outcome="completed")
            if disposition == "stop":
                return
            if disposition == "status":
                result = ProfileWorkerStatus(
                    identity=context.custody.identity,
                    request_id=request.request_id,
                    sessions=context.custody.live_sessions(),
                    in_flight_operations=context.operations.in_flight_operation_count(),
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
                    sign_in=refusal.sign_in if isinstance(refusal, ProfileAccessRefusedError) else None,
                ),
                deadline=time.monotonic() + 5,
            )
        finally:
            # Any handled command may have installed, refreshed or retired a lease or a login.
            context.changed.set()


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
    stop, failed, changed = asyncio.Event(), asyncio.Event(), asyncio.Event()
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
        changed=changed,
    )
    expiry = asyncio.create_task(
        _expire_custody(stop, failed, custody, uploads, human, changed), name="profile-custody-expiry"
    )
    executing = asyncio.create_task(
        _worker_requests.operate(operation_channel, operations, failed, uploads, changed),
        name="profile-operation-requests",
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
