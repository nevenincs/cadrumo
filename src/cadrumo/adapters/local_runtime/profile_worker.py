"""Runtime-owned profile worker with containment before secret delivery."""

from __future__ import annotations

import asyncio
import os
import sys
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from datetime import datetime
from importlib.metadata import version
from pathlib import Path
from threading import Event, RLock
from uuid import UUID, uuid4, uuid5

from pydantic import BaseModel

from ...application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationResultProjectionRequestV1,
    OperationReviewProjectionRequestV1,
)
from ...application.operations.models import OperationId, OperationIdentity, OperationRequest
from ...application.operations.registry import OperationFrontendProjection, OperationPublicDefinitionDescriptionV1
from ...application.operations.secret_submission import OperationSecretRequirement
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError, RuntimeServerHello
from ...application.runtime.operation_access import OperationManagementRequest
from ...application.runtime.profile_access import RuntimeHumanProofMethod
from ...application.runtime.profile_worker import (
    ProfileWorkerContractRequest,
    ProfileWorkerControlRequest,
    ProfileWorkerDrained,
    ProfileWorkerHumanBindingRequest,
    ProfileWorkerHumanBound,
    ProfileWorkerHumanOutcome,
    ProfileWorkerIdentity,
    ProfileWorkerLeaseRequest,
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
    ProfileWorkerReply,
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
from ...application.runtime.projection_pages import ProjectionPageRequest
from ...application.runtime.submission_payload import SubmissionPayloadChunk, SubmissionPayloadDescriptor
from ...application.runtime.worker_authorization import WorkerAuthorizationOwner
from ...application.user_profile.access_contracts import AccessDenialCode, AccessSession
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from ...application.user_profile.login_session import ProfileHumanLoginReceipt, ProfileLoginOutcome
from ...core.async_cleanup import AsyncResourceCleanupError
from ...core.time.clock import now
from .framing import RuntimeTransportCleanup, accept_runtime_handshake, read_document, write_document, write_secret
from .linux_worker_process import LinuxOwnedProcess, LinuxProcessScope
from .posix import PosixRuntimeChannel
from .windows_process import WindowsOwnedProcess, WindowsProcessScope, unreturned_windows_process_scope
from .worker_authorization import WorkerAuthorizationServer
from .worker_lease_transfer import write_worker_lease
from .worker_transport import WorkerChannel, WorkerEndpoint, worker_endpoint

_WORKER_STARTUP_ACCEPT_TIMEOUT_SECONDS = 45.0
_WORKER_STARTUP_ACCEPT_POLL_SECONDS = 0.1
_WORKER_ADMISSION_PREPARE_TIMEOUT_SECONDS = 30.0
_WORKER_NATIVE_HEALTH_WAIT_SECONDS = 2.0


class _WorkerCleanup:
    """Retain native release until it succeeds, including asynchronous retries."""

    def __init__(self, release: Callable[[], None], *, retry_release: Callable[[], None] | None = None) -> None:
        self._release = release
        self._retry_release = retry_release or release
        self._released = False

    def close_now(self) -> None:
        if not self._released:
            release, self._release = self._release, self._retry_release
            release()
            self._released = True

    async def close(self) -> None:
        await asyncio.to_thread(self.close_now)


def _release_worker_resources(*owners: _WorkerCleanup, primary_error: BaseException | None = None) -> None:
    failed: list[_WorkerCleanup] = []
    failures: list[BaseException] = []
    for owner in owners:
        try:
            owner.close_now()
        except BaseException as error:
            failed.append(owner)
            failures.append(error)
    if not failures:
        return
    cleanup = AsyncResourceCleanupError(
        tuple(failed), tuple(failures), retry_task_name="profile-worker-cleanup", close_attempts=1
    )
    if primary_error is None:
        raise cleanup from failures[0]
    previous = primary_error.__dict__.get("async_cleanup_error")
    if isinstance(previous, AsyncResourceCleanupError):
        cleanup = previous.merged_with(cleanup)
    primary_error.__dict__["async_cleanup_error"] = cleanup
    primary_error.add_note("Worker cleanup also failed; retry through the attached async_cleanup_error")


def unreturned_profile_worker(error: BaseException) -> ProfileWorkerProcess | None:
    """Find the native owner a failed constructor could not return to its caller."""
    candidate = error.__dict__.get("_profile_worker_candidate")
    return candidate if isinstance(candidate, ProfileWorkerProcess) else None


def worker_operation_namespace(worker_id: UUID) -> UUID:
    """Separate private execution I/O from authority-held custody control calls."""
    return uuid5(worker_id, "cadrumo-profile-operations")


def _verified_worker_pid(
    channel: WorkerChannel, scope: WindowsProcessScope | LinuxProcessScope, os_owner_id: str
) -> int:
    if isinstance(scope, LinuxProcessScope):
        if not isinstance(channel, PosixRuntimeChannel):
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        return scope.verify_worker(channel, owner_id=os_owner_id)
    peer = channel.peer
    process_id = peer.process_id
    if process_id is None or process_id not in scope.active_process_ids() or peer.os_owner_id != os_owner_id:
        raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
    return process_id


class ProfileWorkerProcess:
    """One immutable profile process and its parent-owned containment scope.

    This is a custody transport, not an admission service. Only the runtime's
    session authority may supply a lease or key. Construction sends no secrets.
    """

    identity: ProfileWorkerIdentity
    _lock: RLock
    _operation_lock: RLock
    _scope: WindowsProcessScope | LinuxProcessScope
    _process: WindowsOwnedProcess | LinuxOwnedProcess
    _authorization: WorkerAuthorizationServer | None

    def __init__(
        self,
        identity: ProfileWorkerIdentity,
        *,
        storage_root: Path,
        authorization: WorkerAuthorizationOwner | None = None,
        worker_script: Path | None = None,
        wall_clock: Callable[[], datetime] = now,
    ) -> None:
        """Launch and authenticate a contained installed worker before key access."""
        if sys.platform not in {"win32", "linux"}:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        if worker_script is not None:
            worker_script = worker_script.resolve(strict=True)
        self.identity = identity
        self._lock = RLock()
        self._operation_lock = RLock()
        self._human_lock = RLock()
        self._native_guard = RLock()
        self._stopping = Event()
        self._channel: WorkerChannel | None = None
        self._operation_channel: WorkerChannel | None = None
        self._human_candidate: UUID | None = None
        self._human_deadline: float | None = None
        self._authorization = None
        endpoint = worker_endpoint(storage_root=storage_root, worker_namespace=identity.worker_id)
        operation_endpoint = worker_endpoint(
            storage_root=storage_root, worker_namespace=worker_operation_namespace(identity.worker_id)
        )
        endpoint_owner = _WorkerCleanup(endpoint.close)
        operation_endpoint_owner = _WorkerCleanup(operation_endpoint.close)
        self._listener_cleanup = (endpoint_owner, operation_endpoint_owner)
        self._pending_channel_cleanup: list[_WorkerCleanup] = []
        try:
            self._scope = (
                WindowsProcessScope()
                if sys.platform == "win32"
                else LinuxProcessScope(worker_id=identity.worker_id, worker_script=worker_script)
            )
        except BaseException as error:
            retained_scope = unreturned_windows_process_scope(error)
            if retained_scope is not None:
                # Native construction already attempted release. Transfer its
                # actual remaining owner before a public refusal drops errors.
                self._scope = retained_scope
                self._stopping.set()
                error.__dict__["_profile_worker_candidate"] = self
            raise
        retiring_listeners = False
        try:
            endpoint.listen()
            operation_endpoint.listen()
            environment = (
                {
                    key: value
                    for key, value in os.environ.items()
                    if not key.upper().startswith(("PYTHON", "LD_", "DYLD_"))
                }
                if sys.platform == "win32"
                else {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"}
            )
            environment["PYDANTIC_DISABLE_PLUGINS"] = "__all__"
            product_version = version("cadrumo")
            worker_entrypoint = (
                ("-m", "cadrumo.entrypoints.runtime.worker")
                if worker_script is None
                else (str(worker_script.resolve(strict=True)),)
            )
            self._process = self._scope.launch(
                executable=Path(sys.executable),
                arguments=(
                    "-I",
                    *worker_entrypoint,
                    "--storage-root",
                    str(storage_root),
                    "--worker-id",
                    str(identity.worker_id),
                    "--parent-pid",
                    str(os.getpid()),
                    "--expected-version",
                    product_version,
                ),
                directory=storage_root,
                environment=environment,
            )
            # A cold isolated worker imports the registered operation catalogue
            # before opening its first pipe. Keep that bounded startup budget
            # separate from the short handshakes after the pipe is connected.
            channel = self._accept_startup_channel(endpoint, timeout=_WORKER_STARTUP_ACCEPT_TIMEOUT_SECONDS)
            self._channel = channel
            worker_process_id = self._verify_native_peer(channel)
            deadline = time.monotonic() + 10
            accept_runtime_handshake(
                channel,
                identity=RuntimeServerHello(
                    product_version=product_version,
                    storage_identity=endpoint.storage_identity,
                    boot_id=identity.runtime_boot_id,
                ),
                deadline=deadline,
            )
            write_document(channel, identity, deadline=deadline)
            accepted = read_document(channel, ProfileWorkerIdentity, deadline=deadline)
            if accepted != identity:
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            self._authorization = WorkerAuthorizationServer(
                identity=identity,
                root=storage_root,
                process_id=worker_process_id,
                owns_process=self._owns_native_process,
                contain=self._contain_native_process,
                owner=authorization,
                wall_clock=wall_clock,
            )
            operation_channel = self._accept_startup_channel(operation_endpoint, timeout=10)
            self._operation_channel = operation_channel
            if operation_channel.peer != channel.peer:
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            if isinstance(self._scope, LinuxProcessScope):
                self._verify_native_peer(operation_channel)
            deadline = time.monotonic() + 10
            accept_runtime_handshake(
                operation_channel,
                identity=RuntimeServerHello(
                    product_version=product_version,
                    storage_identity=operation_endpoint.storage_identity,
                    boot_id=identity.runtime_boot_id,
                ),
                deadline=deadline,
            )
            write_document(operation_channel, identity, deadline=deadline)
            if read_document(operation_channel, ProfileWorkerIdentity, deadline=deadline) != identity:
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            # Construction transfers the child only after both native listeners
            # have retired. A release failure must not lose the unreturned owner.
            retiring_listeners = True
            try:
                _release_worker_resources(endpoint_owner, operation_endpoint_owner)
            except AsyncResourceCleanupError as cleanup:
                error = RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
                error.__dict__["async_cleanup_error"] = cleanup
                raise error from cleanup
        except BaseException as error:
            # Callback settlement needs the caller's profile guard released.
            # Retain this candidate for adoption before a refusal is projected.
            error.__dict__["_profile_worker_candidate"] = self
            owners = (_WorkerCleanup(lambda: self._close_resources(deadline=None, retire_listeners=False)),)
            if not retiring_listeners:
                owners += (endpoint_owner, operation_endpoint_owner)
            _release_worker_resources(*owners, primary_error=error)
            raise

    def _require_process_alive(self) -> None:
        with self._native_guard:
            if self._stopping.is_set():
                raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
            try:
                self._process.wait(timeout=0)
            except RuntimeRefusalError as error:
                if error.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED:
                    return
                raise
        raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)

    def _verify_native_peer(self, channel: WorkerChannel) -> int:
        with self._native_guard:
            if self._stopping.is_set():
                raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
            return _verified_worker_pid(channel, self._scope, self.identity.binding.os_owner_id)

    def _owns_native_process(self, process_id: int) -> bool:
        with self._native_guard:
            return not self._stopping.is_set() and process_id in self._scope.active_process_ids()

    def _contain_native_process(self, *, timeout: float = 2.0) -> None:
        self._stopping.set()
        acquired = self._native_guard.acquire(blocking=False)
        if not acquired:
            deadline = time.monotonic() + timeout
            acquired = self._native_guard.acquire(timeout=max(0.0, timeout))
            timeout = max(0.0, deadline - time.monotonic())
        if not acquired:
            raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
        try:
            self._scope.terminate(timeout=timeout)
        finally:
            self._native_guard.release()

    def _accept_startup_channel(
        self,
        endpoint: WorkerEndpoint,
        *,
        timeout: float,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> WorkerChannel:
        deadline = monotonic() + timeout
        while True:
            self._require_process_alive()
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
            try:
                channel = endpoint.accept(timeout=min(_WORKER_STARTUP_ACCEPT_POLL_SECONDS, remaining))
            except RuntimeRefusalError as error:
                if error.reason is not RuntimeRefusalCode.DEADLINE_EXCEEDED:
                    raise
                self._require_process_alive()
                continue
            try:
                self._require_process_alive()
            except BaseException as error:
                owner = _WorkerCleanup(channel.close)
                self._pending_channel_cleanup.append(owner)
                _release_worker_resources(owner, primary_error=error)
                raise
            return channel

    def _exchange[Result: BaseModel](
        self,
        request: ProfileWorkerRequest,
        response: type[Result],
        secret: bytearray | None = None,
        *,
        operation: bool = False,
        deadline: float | None = None,
    ) -> Result:
        lock = self._operation_lock if operation else self._lock
        acquired = False
        try:
            if deadline is None:
                lock.acquire()
                acquired = True
            else:
                acquired = lock.acquire(timeout=max(0.0, deadline - time.monotonic()))
                if not acquired:
                    raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
            try:
                channel = self._operation_channel if operation else self._channel
                if channel is None or self._stopping.is_set():
                    raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
                if isinstance(self._scope, LinuxProcessScope):
                    with self._native_guard:
                        if self._stopping.is_set() or not self._scope.owns_process(self._scope.worker_pid):
                            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
                wire_deadline = time.monotonic() + 10 if deadline is None else deadline
                if isinstance(request.root, ProfileWorkerLeaseRequest | ProfileWorkerHumanBindingRequest):
                    write_worker_lease(channel, request, deadline=wire_deadline)
                else:
                    write_document(channel, request, deadline=wire_deadline)
                if secret is not None:
                    write_secret(channel, secret, deadline=wire_deadline)
                result = read_document(channel, ProfileWorkerReply, deadline=wire_deadline).root
                if result.identity != self.identity or result.request_id != request.root.request_id:
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                if isinstance(result, ProfileWorkerRefusal):
                    if isinstance(result.reason, AccessDenialCode):
                        raise ProfileAccessRefusedError(result.reason)
                    raise AutomationCustodyError(result.reason)
                if not isinstance(result, response):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                return result
            finally:
                lock.release()
        except (AutomationCustodyError, ProfileAccessRefusedError):
            raise
        except BaseException as error:
            # No frame was sent when a caller merely timed out waiting for
            # this shared channel. Keep other sessions' worker alive.
            if acquired:
                self._stopping.set()
                released = error.__dict__.get("_runtime_transport_cleanup")
                if isinstance(released, RuntimeTransportCleanup) and released.released:
                    # Framing has already released this exact native channel.
                    # Physical worker containment must not close it a second time.
                    if released.resource is self._channel:
                        self._channel = None
                    if released.resource is self._operation_channel:
                        self._operation_channel = None
                _release_worker_resources(
                    _WorkerCleanup(lambda: self.close(deadline=deadline), retry_release=self.close), primary_error=error
                )
            raise
        finally:
            if secret is not None:
                secret[:] = bytes(len(secret))

    @property
    def stopping(self) -> bool:
        """Whether containment or a dispatched control failure fenced this worker."""
        return self._stopping.is_set()

    def require_alive(self) -> None:
        """Bound native contention, then observe the retained worker's current health.

        Native membership checks do not await host callbacks or worker wire
        replies. Waiting briefly for their guard avoids refusing a healthy
        concurrent call; expiry never closes the other guard owner.
        """
        if self._stopping.is_set():
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
        if not self._native_guard.acquire(timeout=_WORKER_NATIVE_HEALTH_WAIT_SECONDS):
            raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
        try:
            if self._stopping.is_set() or self._channel is None:
                raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
            if self._authorization is not None:
                self._authorization.require_healthy()
            self._require_process_alive()
        finally:
            self._native_guard.release()

    def prepare_api_admission(self, *, deadline: float) -> None:
        """Compose the pinned graph without receiving any secret or installing a lease."""
        self._exchange(
            ProfileWorkerRequest(ProfileWorkerControlRequest(action="prepare_api", request_id=uuid4())),
            ProfileWorkerStatus,
            deadline=deadline,
        )

    def install(self, lease: AccessSession, dek: bytearray, *, deadline: float | None = None) -> None:
        """Consume verified material and finish first-use graph preparation before admission."""
        self._exchange(
            ProfileWorkerRequest(ProfileWorkerLeaseRequest(action="install", request_id=uuid4(), lease=lease)),
            ProfileWorkerStatus,
            dek,
            deadline=(time.monotonic() + _WORKER_ADMISSION_PREPARE_TIMEOUT_SECONDS if deadline is None else deadline),
        )

    def refresh(self, lease: AccessSession) -> None:
        """Refresh an existing root lease after the authority revalidates its grant."""
        self._exchange(
            ProfileWorkerRequest(ProfileWorkerLeaseRequest(action="refresh", request_id=uuid4(), lease=lease)),
            ProfileWorkerStatus,
        )

    def share(self, lease: AccessSession) -> None:
        """Attach a narrowed child to existing worker custody."""
        self._exchange(
            ProfileWorkerRequest(ProfileWorkerLeaseRequest(action="share", request_id=uuid4(), lease=lease)),
            ProfileWorkerStatus,
        )

    def retire(self, session_id: UUID) -> None:
        """Release one lease lineage, retaining other independently authorized leases."""
        self._exchange(
            ProfileWorkerRequest(ProfileWorkerRetireRequest(request_id=uuid4(), session_id=session_id)),
            ProfileWorkerStatus,
        )

    def status(self) -> ProfileWorkerStatus:
        """Read internal worker custody identifiers without exposing material."""
        return self._exchange(
            ProfileWorkerRequest(ProfileWorkerControlRequest(action="status", request_id=uuid4())), ProfileWorkerStatus
        )

    def settlement(self, identity: OperationIdentity, *, timeout: float) -> ProfileWorkerSettlement:
        """Await one original rotation terminal state without acquiring old custody."""
        bounded_wait = float(timeout)
        reply = self._exchange(
            ProfileWorkerRequest(
                ProfileWorkerSettlementRequest(
                    request_id=uuid4(), operation_identity=identity, wait_seconds=bounded_wait
                )
            ),
            ProfileWorkerSettlement,
            deadline=time.monotonic() + bounded_wait + 5,
        )
        if reply.operation_identity != identity:
            self.close()
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return reply

    def drain(self, *, deadline: float | None = None) -> ProfileWorkerDrained:
        """Request bounded shutdown, then contain this entire native process scope.

        The caller must hold no profile authority guard while waiting: worker
        callbacks may need that same guard to finish their current operation.
        """
        try:
            return self._exchange(
                ProfileWorkerRequest(ProfileWorkerControlRequest(action="stop", request_id=uuid4())),
                ProfileWorkerDrained,
                deadline=deadline,
            )
        finally:
            self.close(deadline=deadline)

    def describe(self, session_id: UUID, definition_id: str) -> OperationPublicDefinitionDescriptionV1:
        """Read one exact canonical contract and request schema through live custody."""
        result = self._exchange(
            ProfileWorkerRequest(
                ProfileWorkerContractRequest(
                    request_id=uuid4(),
                    session_id=session_id,
                    definition_id=definition_id,
                )
            ),
            ProfileWorkerOperationContract,
        )
        return OperationPublicDefinitionDescriptionV1(
            contract=result.contract, request_json_schema=result.request_json_schema
        )

    def submit[Payload: BaseModel](
        self, session_id: UUID, request: OperationRequest[Payload], *, frontend: OperationFrontendProjection
    ) -> ProfileWorkerSubmission:
        """Submit private operands only to this profile's owned canonical supervisor."""
        return self.submit_serialized(
            session_id=session_id,
            frontend=frontend,
            definition_id=request.definition_id,
            subject_ref=request.subject_ref,
            payload_json=request.payload.model_dump_json(),
            idempotency_key=request.idempotency_key,
        )

    def submit_serialized(
        self,
        *,
        session_id: UUID,
        frontend: OperationFrontendProjection,
        definition_id: str,
        subject_ref: str,
        payload_json: str,
        idempotency_key: str | None,
    ) -> ProfileWorkerSubmission:
        """Keep domain decoding at the registered owner within immutable profile custody."""
        result = self._exchange(
            ProfileWorkerRequest(
                ProfileWorkerSubmitRequest(
                    request_id=uuid4(),
                    session_id=session_id,
                    frontend=frontend,
                    definition_id=definition_id,
                    subject_ref=subject_ref,
                    payload_json=payload_json,
                    idempotency_key=idempotency_key,
                )
            ),
            ProfileWorkerSubmission,
            operation=True,
        )
        return result

    def _acknowledge_upload(self, request: ProfileWorkerRequest, upload_id: UUID, *, deadline: float) -> None:
        acknowledgement = self._exchange(
            request,
            ProfileWorkerUploadAccepted,
            operation=True,
            deadline=deadline,
        )
        if acknowledgement.upload_id != upload_id:
            self.close(deadline=deadline)
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)

    def begin_submission_payload(
        self,
        *,
        upload_id: UUID,
        connection_id: UUID,
        session_id: UUID,
        frontend: OperationFrontendProjection,
        definition_id: str,
        subject_ref: str,
        idempotency_key: str | None,
        descriptor: SubmissionPayloadDescriptor,
        deadline: float,
    ) -> None:
        """Reserve a worker-local upload; canonical admission waits for finish."""
        self._acknowledge_upload(
            ProfileWorkerRequest(
                ProfileWorkerSubmissionBeginRequest(
                    request_id=uuid4(),
                    upload_id=upload_id,
                    connection_id=connection_id,
                    session_id=session_id,
                    frontend=frontend,
                    definition_id=definition_id,
                    subject_ref=subject_ref,
                    idempotency_key=idempotency_key,
                    descriptor=descriptor,
                )
            ),
            upload_id,
            deadline=deadline,
        )

    def append_submission_payload(
        self,
        *,
        upload_id: UUID,
        connection_id: UUID,
        session_id: UUID,
        chunk: SubmissionPayloadChunk,
        deadline: float,
    ) -> None:
        """Send one bounded frame without retaining the worker wire lock."""
        self._acknowledge_upload(
            ProfileWorkerRequest(
                ProfileWorkerSubmissionChunkRequest(
                    request_id=uuid4(),
                    upload_id=upload_id,
                    connection_id=connection_id,
                    session_id=session_id,
                    chunk=chunk,
                )
            ),
            upload_id,
            deadline=deadline,
        )

    def finish_submission_payload(
        self, *, upload_id: UUID, connection_id: UUID, session_id: UUID, deadline: float
    ) -> ProfileWorkerSubmission:
        """Receive the ordinary canonical submission receipt after verified bytes."""
        return self._exchange(
            ProfileWorkerRequest(
                ProfileWorkerSubmissionFinishRequest(
                    request_id=uuid4(), upload_id=upload_id, connection_id=connection_id, session_id=session_id
                )
            ),
            ProfileWorkerSubmission,
            operation=True,
            deadline=deadline,
        )

    def abort_submission_payload(
        self, *, upload_id: UUID, connection_id: UUID, session_id: UUID, deadline: float
    ) -> None:
        """Wipe one matching upload even when the original lease has expired."""
        self._acknowledge_upload(
            ProfileWorkerRequest(
                ProfileWorkerSubmissionAbortRequest(
                    request_id=uuid4(), upload_id=upload_id, connection_id=connection_id, session_id=session_id
                )
            ),
            upload_id,
            deadline=deadline,
        )

    def start(
        self,
        session_id: UUID,
        operation_id: OperationId,
        *,
        frontend: OperationFrontendProjection = OperationFrontendProjection.MCP,
    ) -> ProfileWorkerOperationReceipt:
        """Start an already admitted invocation with its original session binding."""
        return self._exchange(
            ProfileWorkerRequest(
                ProfileWorkerOperationRequest(
                    action="operation_start",
                    request_id=uuid4(),
                    session_id=session_id,
                    frontend=frontend,
                    operation_id=operation_id,
                )
            ),
            ProfileWorkerOperationReceipt,
            operation=True,
        )

    def observe(
        self,
        session_id: UUID,
        request: OperationObservationRequestV1,
        *,
        frontend: OperationFrontendProjection = OperationFrontendProjection.MCP,
    ) -> ProfileWorkerObservation:
        """Read a bounded canonical projection through fresh disclosure authority."""
        result = self._exchange(
            ProfileWorkerRequest(
                ProfileWorkerObserveRequest(
                    request_id=uuid4(),
                    session_id=session_id,
                    frontend=frontend,
                    observation=request,
                )
            ),
            ProfileWorkerObservation,
            operation=True,
        )
        return result

    def resume(
        self, session_id: UUID, operation_id: OperationId, *, frontend: OperationFrontendProjection
    ) -> ProfileWorkerOperationReceipt:
        """Request fresh authority and canonical recovery without a response credential."""
        return self._exchange(
            ProfileWorkerRequest(
                ProfileWorkerResumeRequest(
                    request_id=uuid4(), session_id=session_id, frontend=frontend, operation_id=operation_id
                )
            ),
            ProfileWorkerOperationReceipt,
            operation=True,
        )

    def project(
        self,
        session_id: UUID,
        request: OperationResultProjectionRequestV1 | OperationReviewProjectionRequestV1,
        *,
        frontend: OperationFrontendProjection,
    ) -> ProfileWorkerProjection:
        """Resolve a canonical result/review projection with separate output consent."""
        return self._exchange(
            ProfileWorkerRequest(
                ProfileWorkerProjectRequest(
                    request_id=uuid4(),
                    session_id=session_id,
                    frontend=frontend,
                    projection=request,
                )
            ),
            ProfileWorkerProjection,
            operation=True,
        )

    def project_page(
        self,
        session_id: UUID,
        request: OperationResultProjectionRequestV1,
        page: ProjectionPageRequest,
        *,
        frontend: OperationFrontendProjection,
    ) -> ProfileWorkerProjectionPage:
        """Reauthorize each bounded slice of the same canonical settled result."""
        return self._exchange(
            ProfileWorkerRequest(
                ProfileWorkerProjectPageRequest(
                    request_id=uuid4(), session_id=session_id, frontend=frontend, projection=request, page=page
                )
            ),
            ProfileWorkerProjectionPage,
            operation=True,
        )

    def manage(
        self,
        session_id: UUID,
        request: OperationManagementRequest,
        *,
        frontend: OperationFrontendProjection,
    ) -> ProfileWorkerProjection:
        """Send one canonical control through the worker's guarded operation channel."""
        return self._exchange(
            ProfileWorkerRequest(
                ProfileWorkerManageRequest(
                    request_id=uuid4(),
                    session_id=session_id,
                    frontend=frontend,
                    management=request,
                )
            ),
            ProfileWorkerProjection,
            operation=True,
        )

    def operation_secret(
        self,
        session_id: UUID,
        requirement: OperationSecretRequirement,
        *,
        frontend: OperationFrontendProjection,
        secret: bytearray | None = None,
    ) -> ProfileWorkerOperationReceipt:
        """Preflight or consume a secret on the contained worker's original submission."""
        return self._exchange(
            ProfileWorkerRequest(
                ProfileWorkerSecretRequest(
                    action="operation_secret_ready" if secret is None else "operation_secret",
                    request_id=uuid4(),
                    session_id=session_id,
                    frontend=frontend,
                    requirement=requirement,
                )
            ),
            ProfileWorkerOperationReceipt,
            secret,
            operation=True,
        )

    @contextmanager
    def authenticate_human(
        self, secret: bytearray, *, method: RuntimeHumanProofMethod = "password"
    ) -> Generator[ProfileLoginOutcome]:
        """Borrow a proven human outcome while the runtime admits its human lease."""
        with self._human_lock:
            started = time.monotonic()
            transaction_deadline = started + _WORKER_ADMISSION_PREPARE_TIMEOUT_SECONDS + 10
            primary: BaseException | None = None
            try:
                self._human_deadline = transaction_deadline
                result = self._exchange(
                    ProfileWorkerRequest(ProfileWorkerControlRequest(action=method, request_id=uuid4())),
                    ProfileWorkerHumanOutcome,
                    secret,
                    deadline=started + _WORKER_ADMISSION_PREPARE_TIMEOUT_SECONDS,
                )
                self._human_candidate = result.candidate_id
                yield result.login
            except BaseException as error:
                primary = error
                raise
            finally:
                self._human_candidate = None
                self._human_deadline = None
                secret[:] = bytes(len(secret))
                if self._channel is not None and not self._stopping.is_set():
                    try:
                        self._exchange(
                            ProfileWorkerRequest(
                                ProfileWorkerControlRequest(action="cancel_human", request_id=uuid4())
                            ),
                            ProfileWorkerStatus,
                            deadline=time.monotonic() + 10,
                        )
                    except BaseException as failure:
                        # Protocol failures already retain their original native
                        # close owner. A typed refusal also fences this worker;
                        # never retry a bare cancel against a later candidate.
                        if not self._stopping.is_set():
                            _release_worker_resources(_WorkerCleanup(self.close), primary_error=failure)
                        if primary is None:
                            raise
                        cleanup = AsyncResourceCleanupError(
                            (), (failure,), retry_task_name="human-candidate-cleanup", close_attempts=1
                        )
                        seen: set[int] = set()
                        for error in (failure, primary):
                            for field in ("async_cleanup_error", "cleanup_error"):
                                retained = error.__dict__.get(field)
                                if isinstance(retained, AsyncResourceCleanupError) and id(retained) not in seen:
                                    seen.add(id(retained))
                                    cleanup = retained.merged_with(cleanup)
                        primary.__dict__["async_cleanup_error"] = cleanup
                        primary.__dict__["cleanup_error"] = cleanup
                        primary.add_note("Human candidate cleanup failed; original native owner retained")
            if time.monotonic() >= transaction_deadline:
                raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)

    @property
    def human_admission_deadline(self) -> float:
        """Expose the trusted original bound only while a candidate is borrowed."""
        if self._human_deadline is None:
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        return self._human_deadline

    def bind_human(self, lease: AccessSession, *, persist_receipt: bool = False) -> ProfileHumanLoginReceipt:
        """Promote only the human candidate held by this admission context."""
        if self._human_candidate is None or self._human_deadline is None:
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        deadline = min(time.monotonic() + 10, self._human_deadline)
        if deadline <= time.monotonic():
            raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
        result = self._exchange(
            ProfileWorkerRequest(
                ProfileWorkerHumanBindingRequest(
                    request_id=uuid4(),
                    candidate_id=self._human_candidate,
                    lease=lease,
                    persist_receipt=persist_receipt,
                )
            ),
            ProfileWorkerHumanBound,
            deadline=deadline,
        )
        if result.session_id != lease.session_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        self._human_candidate = None
        return result.receipt

    def close(self, *, deadline: float | None = None) -> None:
        """Fence calls and terminate the complete owned process scope."""
        self._close_resources(deadline=deadline, retire_listeners=True)

    def _close_resources(self, *, deadline: float | None, retire_listeners: bool) -> None:
        self._stopping.set()
        failures: list[BaseException] = []
        if self._authorization is not None:
            try:
                self._authorization.close()
            except BaseException as error:
                failures.append(error)
        # Contain first: an operation may be waiting for the caller's profile
        # guard. Do not wait for its transport lock while it is still alive.
        try:
            self._contain_native_process(timeout=2.0 if deadline is None else max(0.0, deadline - time.monotonic()))
        except BaseException as error:
            failures.append(error)
        acquired_control = self._lock.acquire(
            timeout=2.0 if deadline is None else max(0.0, deadline - time.monotonic())
        )
        if acquired_control:
            try:
                if self._channel is not None:
                    try:
                        self._channel.close()
                    except BaseException as error:
                        failures.append(error)
                    else:
                        self._channel = None
            finally:
                self._lock.release()
        else:
            failures.append(RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED))
        acquired_operation = self._operation_lock.acquire(
            timeout=2.0 if deadline is None else max(0.0, deadline - time.monotonic())
        )
        if acquired_operation:
            try:
                if self._operation_channel is not None:
                    try:
                        self._operation_channel.close()
                    except BaseException as error:
                        failures.append(error)
                    else:
                        self._operation_channel = None
            finally:
                self._operation_lock.release()
        else:
            failures.append(RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED))
        if retire_listeners:
            try:
                _release_worker_resources(*self._listener_cleanup, *self._pending_channel_cleanup)
            except BaseException as error:
                failures.append(error)
        if len(failures) == 1:
            raise failures[0]
        if failures:
            raise BaseExceptionGroup("Profile worker release failed", failures)

    def settle(self, *, deadline: float | None = None) -> None:
        """Join authorization callbacks after releasing the profile admission guard."""
        if self._authorization is not None:
            if deadline is None:
                self._authorization.settle()
            else:
                self._authorization.settle(timeout=max(0.0, deadline - time.monotonic()))
