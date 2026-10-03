"""Installed profile worker: native parent verification precedes all private custody."""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from collections.abc import Awaitable, Callable, Generator
from contextlib import AbstractContextManager, ExitStack, contextmanager, suppress
from importlib.metadata import version
from pathlib import Path
from typing import cast
from uuid import UUID

from pydantic import ValidationError

from ...adapters.local_runtime.framing import (
    RuntimeTransportCleanup,
    VerifiedRuntimeConnection,
    close_runtime_transport_after_failure,
    read_document,
    read_secret,
    write_document,
)
from ...adapters.local_runtime.posix import PosixRuntimeChannel
from ...adapters.local_runtime.profile_worker import worker_operation_namespace
from ...adapters.local_runtime.worker_authorization_client import WorkerAuthorizationClient
from ...adapters.local_runtime.worker_lease_transfer import read_worker_lease
from ...adapters.local_runtime.worker_transport import WorkerChannel, worker_endpoint
from ...adapters.persistence.storage.master_key.profile_worker_custody import ProfileWorkerCustody
from ...application.runtime.contracts import RuntimeClientHello, RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.operation_access import operation_management_action
from ...application.runtime.profile_worker import (
    ProfileWorkerContractRequest,
    ProfileWorkerDrained,
    ProfileWorkerHumanBindingRequest,
    ProfileWorkerHumanBound,
    ProfileWorkerHumanOutcome,
    ProfileWorkerIdentity,
    ProfileWorkerLeaseRequest,
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
    ProfileWorkerRetireRequest,
    ProfileWorkerSecretRequest,
    ProfileWorkerSettlement,
    ProfileWorkerSettlementRequest,
    ProfileWorkerStatus,
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
from ...core.async_cleanup import (
    AsyncCloseable,
    AsyncResourceCleanupError,
    await_cancellation_complete,
    close_async_resources,
)
from ...core.config import override_settings
from ..adapter_composition import profile_adapter_composition
from ..exchange_rate_composition import live_exchange_rate_composition
from .operation_host import ProfileWorkerOperationHost
from .profile_login import ProfileWorkerHumanLogin
from .worker_submission_staging import StagedSubmission, WorkerSubmissionStaging


class _WorkerRelease[Result]:
    """Keep one worker release retryable until its callback succeeds."""

    def __init__(self, release: Callable[[], Awaitable[Result]]) -> None:
        self._release = release
        self._results: list[Result] = []

    async def release(self) -> Result:
        if not self._results:
            self._results.append(await self._release())
        return self._results[0]

    async def close(self) -> None:
        await self.release()


def _retain_task_failures(primary: BaseException, failures: tuple[BaseException, ...]) -> None:
    """Keep known worker body diagnostics and their actual failed release owners."""
    pending = [primary, *failures]
    retained: list[BaseException] = []
    seen: set[int] = set()
    seen_cleanup: set[int] = set()
    cleanup = primary.__dict__.get("async_cleanup_error")
    combined = cleanup if isinstance(cleanup, AsyncResourceCleanupError) else None
    if combined is not None:
        seen_cleanup.add(id(combined))
    for failure in pending:
        if id(failure) in seen:
            continue
        seen.add(id(failure))
        if failure is not primary:
            retained.append(failure)
        nested = failure.__dict__.get("worker_task_errors")
        if isinstance(nested, tuple):
            pending.extend(error for error in cast(tuple[object, ...], nested) if isinstance(error, BaseException))
        for name in ("async_cleanup_error", "cleanup_error", "body_error"):
            cleanup = failure.__dict__.get(name)
            if isinstance(cleanup, AsyncResourceCleanupError):
                if id(cleanup) not in seen_cleanup:
                    seen_cleanup.add(id(cleanup))
                    combined = combined.merged_with(cleanup) if combined is not None else cleanup
            elif isinstance(cleanup, BaseException):
                pending.append(cleanup)
    if combined is not None:
        primary.__dict__["async_cleanup_error"] = combined
        if isinstance(primary, asyncio.CancelledError):
            primary.__dict__["cleanup_error"] = combined
    if retained:
        primary.__dict__["worker_task_errors"] = tuple(retained)
        primary.add_note("Worker task/body failures are retained as worker_task_errors")


def _require_native_parent(channel: WorkerChannel, parent_pid: int) -> None:
    """Check the socket's live kernel peer before admitting profile custody."""
    if channel.peer.process_id != parent_pid:
        raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
    if isinstance(channel, PosixRuntimeChannel):
        with channel.capture_peer_pidfd():
            if channel.peer.process_id != parent_pid:
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)


async def _receive(channel: WorkerChannel, failed: asyncio.Event, *, control: bool = False) -> ProfileWorkerRequest:
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


async def _operate(
    channel: WorkerChannel,
    operations: ProfileWorkerOperationHost,
    failed: asyncio.Event,
    uploads: WorkerSubmissionStaging,
) -> None:
    try:
        while True:
            request = (await _receive(channel, failed)).root
            try:
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
                    continue
                elif isinstance(request, ProfileWorkerSubmissionBeginRequest):
                    operations.contract(request.session_id, request.definition_id)
                    uploads.begin(request)
                    result = ProfileWorkerUploadAccepted(
                        identity=operations.custody.identity,
                        request_id=request.request_id,
                        upload_id=request.upload_id,
                    )
                elif isinstance(request, ProfileWorkerSubmissionChunkRequest):
                    operations.custody.require(request.session_id)
                    uploads.append(request)
                    result = ProfileWorkerUploadAccepted(
                        identity=operations.custody.identity,
                        request_id=request.request_id,
                        upload_id=request.upload_id,
                    )
                elif isinstance(request, ProfileWorkerSubmissionFinishRequest):
                    staged = uploads.finish(request)
                    try:
                        await _submit_payload_reply(channel, operations, request_id=request.request_id, payload=staged)
                    finally:
                        del staged
                    continue
                elif isinstance(request, ProfileWorkerSubmissionAbortRequest):
                    uploads.abort(request)
                    result = ProfileWorkerUploadAccepted(
                        identity=operations.custody.identity,
                        request_id=request.request_id,
                        upload_id=request.upload_id,
                    )
                elif isinstance(request, ProfileWorkerSecretRequest):
                    # The parent has already performed preflight. Always
                    # consume the promised bounded frame before rechecking
                    # authority, so a refusal cannot desynchronize the stream.
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
                    continue
                elif isinstance(request, ProfileWorkerOperationRequest | ProfileWorkerResumeRequest):
                    if isinstance(request, ProfileWorkerResumeRequest):
                        operation_id = await operations.resume(
                            request.operation_id, request.session_id, frontend=request.frontend
                        )
                        action = AccessAction.RESUME
                    else:
                        operation_id = await operations.start(request.operation_id, request.session_id)
                        action = AccessAction.START
                    async with operations.release(
                        request.session_id, operation_id, request.frontend, action
                    ) as release:
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
                    continue
                elif isinstance(request, ProfileWorkerObserveRequest):
                    async with operations.observe(
                        request.session_id, request.observation, frontend=request.frontend
                    ) as (observation, release):
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
                    continue
                elif isinstance(request, ProfileWorkerProjectRequest | ProfileWorkerProjectPageRequest):
                    async with operations.project(
                        request.session_id, request.projection, frontend=request.frontend
                    ) as (document, release):
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
                    continue
                elif isinstance(request, ProfileWorkerManageRequest):
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
                    continue
                else:
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            except (AutomationCustodyError, ProfileAccessRefusedError, ValidationError) as refusal:
                result = ProfileWorkerRefusal(
                    identity=operations.custody.identity,
                    request_id=request.request_id,
                    reason=AutomationCustodyCode.INVALID if isinstance(refusal, ValidationError) else refusal.reason,
                )
            write_document(channel, result, deadline=time.monotonic() + 5)
    except Exception:
        failed.set()
        raise


async def _serve(
    channel: WorkerChannel,
    operation_channel: WorkerChannel,
    custody: ProfileWorkerCustody,
    human: ProfileWorkerHumanLogin,
    operations: ProfileWorkerOperationHost,
) -> None:
    stop, failed = asyncio.Event(), asyncio.Event()
    uploads = WorkerSubmissionStaging()
    operation_release = _WorkerRelease(operations.close)
    human_release = _WorkerRelease(lambda: asyncio.to_thread(human.close))
    upload_release = _WorkerRelease(lambda: asyncio.to_thread(uploads.close))

    async def expire() -> None:
        while not stop.is_set():
            await asyncio.sleep(0.1)
            try:
                await asyncio.to_thread(custody.expire)
                uploads.expire(live_sessions=custody.live_sessions())
                await asyncio.to_thread(human.expire)
            except Exception:
                failed.set()
                return

    expiry = asyncio.create_task(expire(), name="profile-custody-expiry")
    executing = asyncio.create_task(
        _operate(operation_channel, operations, failed, uploads), name="profile-operation-requests"
    )
    try:
        while not failed.is_set():
            request = (await _receive(channel, failed, control=True)).root
            if failed.is_set():
                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
            try:
                if isinstance(request, ProfileWorkerLeaseRequest):
                    if request.action == "install":
                        with read_secret(channel, deadline=time.monotonic() + 5) as secret:
                            custody.install(request.lease, secret)
                        operations.prepare()
                    elif request.action == "refresh":
                        custody.refresh(request.lease)
                    else:
                        custody.share(request.lease)
                elif isinstance(request, ProfileWorkerRetireRequest):
                    custody.retire(request.session_id)
                    uploads.expire(live_sessions=custody.live_sessions())
                elif isinstance(request, ProfileWorkerHumanBindingRequest):
                    receipt = human.bind(request.candidate_id, request.lease, persist_receipt=request.persist_receipt)
                    write_document(
                        channel,
                        ProfileWorkerHumanBound(
                            identity=custody.identity,
                            request_id=request.request_id,
                            session_id=request.lease.session_id,
                            receipt=receipt,
                        ),
                        deadline=time.monotonic() + 5,
                    )
                    continue
                elif isinstance(
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
                elif isinstance(request, ProfileWorkerContractRequest):
                    description = operations.describe(request.session_id, request.definition_id)
                    write_document(
                        channel,
                        ProfileWorkerOperationContract(
                            identity=custody.identity,
                            request_id=request.request_id,
                            contract=description.contract,
                            request_json_schema=description.request_json_schema,
                        ),
                        deadline=time.monotonic() + 5,
                    )
                    continue
                elif isinstance(request, ProfileWorkerSettlementRequest):
                    settled = await operations.settlement(request.operation_identity, timeout=request.wait_seconds)
                    write_document(
                        channel,
                        ProfileWorkerSettlement(
                            identity=custody.identity,
                            request_id=request.request_id,
                            operation_identity=request.operation_identity,
                            settled=settled,
                        ),
                        deadline=time.monotonic() + 5,
                    )
                    continue
                elif request.action in {"password", "receipt"}:
                    with read_secret(channel, deadline=time.monotonic() + 5) as secret:
                        candidate, login = (
                            human.authenticate(secret) if request.action == "password" else human.resume(secret)
                        )
                    try:
                        operations.prepare()
                    except BaseException as primary:
                        try:
                            human.close()
                        except BaseException as cleanup:
                            _retain_task_failures(primary, (cleanup,))
                            failed.set()
                        raise
                    write_document(
                        channel,
                        ProfileWorkerHumanOutcome(
                            identity=custody.identity,
                            request_id=request.request_id,
                            candidate_id=candidate,
                            login=login,
                        ),
                        deadline=time.monotonic() + 5,
                    )
                    continue
                elif request.action == "prepare_api":
                    operations.prepare()
                elif request.action == "cancel_human":
                    human.close()
                elif request.action == "stop":
                    await upload_release.close()
                    drained = await operation_release.release()
                    write_document(
                        channel,
                        ProfileWorkerDrained(
                            identity=custody.identity,
                            request_id=request.request_id,
                            unresolved=drained.unresolved,
                            recovery_required=drained.recovery_required,
                        ),
                        deadline=time.monotonic() + 5,
                    )
                    # Keep the pipe open until the parent consumes the reply and
                    # contains this scope. Closing immediately can discard an
                    # unread named-pipe frame on Windows.
                    with suppress(RuntimeRefusalError):
                        await asyncio.to_thread(channel.read_exact, 1, deadline=time.monotonic() + 5)
                    return
                result = ProfileWorkerStatus(
                    identity=custody.identity, request_id=request.request_id, sessions=custody.live_sessions()
                )
                write_document(channel, result, deadline=time.monotonic() + 5)
            except (AutomationCustodyError, ProfileAccessRefusedError, ValidationError) as refusal:
                if failed.is_set():
                    raise
                write_document(
                    channel,
                    ProfileWorkerRefusal(
                        identity=custody.identity,
                        request_id=request.request_id,
                        reason=AutomationCustodyCode.INVALID
                        if isinstance(refusal, ValidationError)
                        else refusal.reason,
                    ),
                    deadline=time.monotonic() + 5,
                )
    finally:
        primary_error = sys.exception()
        stop.set()
        executing.cancel()
        task_failures: list[BaseException] = []

        async def settle() -> None:
            for task in (expiry, executing):
                try:
                    await task
                except asyncio.CancelledError as cancellation:
                    # executing was deliberately cancelled by this owner. A
                    # completed task is settled, never a retryable resource.
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
        raise_task_failure = primary_error is None and bool(task_failures)
        if raise_task_failure:
            primary_error = task_failures[0]
        if primary_error is not None and task_failures:
            _retain_task_failures(primary_error, tuple(task_failures))

        await close_async_resources(
            operation_release,
            human_release,
            upload_release,
            task_name="profile-worker-serve-close",
            primary_error=primary_error,
        )
        if raise_task_failure and primary_error is not None:
            raise primary_error


@contextmanager
def installed_profile_worker_composition() -> Generator[None]:
    """Bind the installed worker's persistence and live reference-rate dependencies."""
    with profile_adapter_composition(), live_exchange_rate_composition():
        yield


def run(
    arguments: list[str] | None = None,
    *,
    composition_factory: Callable[[], AbstractContextManager[None]] | None = None,
) -> int:
    """Admit only an exact native runtime parent and a contained current-cohort worker."""
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--storage-root", required=True, type=Path)
    parser.add_argument("--worker-id", required=True, type=UUID)
    parser.add_argument("--parent-pid", required=True, type=int)
    parser.add_argument("--expected-version", required=True)
    options = parser.parse_args(arguments)
    if sys.platform not in {"win32", "linux"} or not sys.flags.isolated:
        return 2
    channel = None
    operation_channel = None
    custody = None
    channel_release: RuntimeTransportCleanup | None = None
    operation_channel_release: RuntimeTransportCleanup | None = None
    handshake_release: RuntimeTransportCleanup | None = None
    endpoint_releases: list[AsyncCloseable] = []
    refusal: RuntimeRefusalError | AutomationCustodyError | None = None
    try:
        if options.expected_version != version("cadrumo"):
            raise RuntimeRefusalError(RuntimeRefusalCode.VERSION_MISMATCH)
        endpoint = worker_endpoint(storage_root=options.storage_root, worker_namespace=options.worker_id)
        endpoint_releases.append(_WorkerRelease(lambda: asyncio.to_thread(endpoint.close)))
        channel = endpoint.connect()
        channel_release = RuntimeTransportCleanup(channel)
        _require_native_parent(channel, options.parent_pid)
        deadline = time.monotonic() + 10
        handshake_release = channel_release
        connection = VerifiedRuntimeConnection(
            channel,
            expected=RuntimeClientHello(
                product_version=options.expected_version, storage_identity=endpoint.storage_identity
            ),
            deadline=deadline,
        )
        handshake_release = None
        identity = read_document(channel, ProfileWorkerIdentity, deadline=deadline)
        if (
            identity.worker_id != options.worker_id
            or identity.runtime_boot_id != connection.hello.boot_id
            or identity.binding.os_owner_id != channel.peer.os_owner_id
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        custody = ProfileWorkerCustody(identity, storage_root=options.storage_root)
        write_document(channel, identity, deadline=deadline)
        operation_endpoint = worker_endpoint(
            storage_root=options.storage_root, worker_namespace=worker_operation_namespace(identity.worker_id)
        )
        endpoint_releases.append(_WorkerRelease(lambda: asyncio.to_thread(operation_endpoint.close)))
        operation_channel = operation_endpoint.connect()
        operation_channel_release = RuntimeTransportCleanup(operation_channel)
        if operation_channel.peer != channel.peer:
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        _require_native_parent(operation_channel, options.parent_pid)
        deadline = time.monotonic() + 10
        handshake_release = operation_channel_release
        verified = VerifiedRuntimeConnection(
            operation_channel,
            expected=RuntimeClientHello(
                product_version=options.expected_version, storage_identity=operation_endpoint.storage_identity
            ),
            deadline=deadline,
        )
        handshake_release = None
        if (
            verified.hello.boot_id != identity.runtime_boot_id
            or read_document(operation_channel, ProfileWorkerIdentity, deadline=deadline) != identity
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        write_document(operation_channel, identity, deadline=deadline)
        with ExitStack() as composition:
            composition.enter_context(
                override_settings(
                    cadrumo_local_storage_root=options.storage_root,
                    cadrumo_active_profile=str(identity.binding.profile_id),
                )
            )
            composition.enter_context((composition_factory or installed_profile_worker_composition)())
            operations = ProfileWorkerOperationHost(
                custody,
                authorization=WorkerAuthorizationClient(
                    identity=identity, root=options.storage_root, parent_pid=options.parent_pid
                ),
            )
            human = ProfileWorkerHumanLogin(custody, decode=operations.profile_decode_context)
            asyncio.run(_serve(channel, operation_channel, custody, human, operations))
    except (RuntimeRefusalError, AutomationCustodyError) as error:
        refusal = error
    finally:
        primary_error = sys.exception() or refusal
        if primary_error is not None:
            _retain_task_failures(primary_error, ())
        failures: tuple[BaseException, ...] = (primary_error,) if primary_error is not None else ()
        if primary_error is not None:
            task_failures = primary_error.__dict__.get("worker_task_errors")
            if isinstance(task_failures, tuple):
                failures += tuple(
                    failure for failure in cast(tuple[object, ...], task_failures) if isinstance(failure, BaseException)
                )
        # Framing already owns an attempted failure-close. Its canonical error
        # retains unsuccessful release; do not make a second initial attempt.
        for failure in failures:
            displaced = failure.__dict__.get("_runtime_transport_cleanup")
            if not isinstance(displaced, RuntimeTransportCleanup):
                continue
            if channel_release is handshake_release or displaced.resource is channel:
                channel_release = None
            if operation_channel_release is handshake_release or displaced.resource is operation_channel:
                operation_channel_release = None
        custody_release = _WorkerRelease(lambda: asyncio.to_thread(custody.close)) if custody is not None else None
        try:
            asyncio.run(
                close_async_resources(
                    custody_release,
                    channel_release,
                    operation_channel_release,
                    *endpoint_releases,
                    task_name="profile-worker-exit-close",
                    primary_error=primary_error,
                )
            )
        finally:
            if primary_error is not None:
                _retain_task_failures(primary_error, ())
    if refusal is not None:
        if isinstance(refusal.__dict__.get("async_cleanup_error"), AsyncResourceCleanupError):
            raise refusal
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
