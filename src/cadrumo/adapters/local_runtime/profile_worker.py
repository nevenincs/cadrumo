"""Runtime-owned Windows worker with containment established before secret delivery."""

from __future__ import annotations

import os
import sys
import time
from collections.abc import Generator
from contextlib import contextmanager
from importlib.metadata import version
from pathlib import Path
from threading import RLock
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
from .framing import accept_runtime_handshake, read_document, write_document, write_secret
from .windows import WindowsRuntimeChannel, WindowsRuntimeEndpoint
from .windows_process import WindowsOwnedProcess, WindowsProcessScope
from .worker_authorization import WorkerAuthorizationServer


def worker_operation_namespace(worker_id: UUID) -> UUID:
    """Separate private execution I/O from authority-held custody control calls."""
    return uuid5(worker_id, "cadrumo-profile-operations")


def _verified_worker_pid(channel: WindowsRuntimeChannel, scope: WindowsProcessScope, os_owner_id: str) -> int:
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
    _scope: WindowsProcessScope
    _process: WindowsOwnedProcess
    _authorization: WorkerAuthorizationServer | None

    def __init__(
        self,
        identity: ProfileWorkerIdentity,
        *,
        storage_root: Path,
        authorization: WorkerAuthorizationOwner | None = None,
    ) -> None:
        """Launch and authenticate a contained installed worker before key access."""
        if sys.platform != "win32":
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        self.identity = identity
        self._lock = RLock()
        self._operation_lock = RLock()
        self._channel: WindowsRuntimeChannel | None = None
        self._operation_channel: WindowsRuntimeChannel | None = None
        self._human_candidate: UUID | None = None
        self._authorization = None
        endpoint = WindowsRuntimeEndpoint(storage_root=storage_root, worker_namespace=identity.worker_id)
        operation_endpoint = WindowsRuntimeEndpoint(
            storage_root=storage_root, worker_namespace=worker_operation_namespace(identity.worker_id)
        )
        self._scope = WindowsProcessScope()
        try:
            endpoint.listen()
            operation_endpoint.listen()
            environment = {
                key: value
                for key, value in os.environ.items()
                if not key.upper().startswith(("PYTHON", "LD_", "DYLD_"))
            }
            environment["PYDANTIC_DISABLE_PLUGINS"] = "__all__"
            product_version = version("cadrumo")
            self._process = self._scope.launch(
                executable=Path(sys.executable),
                arguments=(
                    "-I",
                    "-m",
                    "cadrumo.entrypoints.runtime.worker",
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
            channel = endpoint.accept(timeout=10)
            self._channel = channel
            worker_process_id = _verified_worker_pid(channel, self._scope, identity.binding.os_owner_id)
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
                owns_process=lambda pid: pid in self._scope.active_process_ids(),
                contain=self._scope.terminate,
                owner=authorization,
            )
            operation_channel = operation_endpoint.accept(timeout=10)
            self._operation_channel = operation_channel
            if operation_channel.peer != channel.peer:
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
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
        except BaseException:
            self.close()
            raise
        finally:
            endpoint.close()
            operation_endpoint.close()

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
                if channel is None:
                    raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
                wire_deadline = time.monotonic() + 10 if deadline is None else deadline
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
        except BaseException:
            # No frame was sent when a caller merely timed out waiting for
            # this shared channel. Keep other sessions' worker alive.
            if acquired:
                self.close(deadline=deadline)
            raise
        finally:
            if secret is not None:
                secret[:] = bytes(len(secret))

    def require_alive(self) -> None:
        """Observe the retained worker process handle, without trusting a reused PID."""
        with self._lock:
            if self._channel is None:
                raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
            if self._authorization is not None:
                self._authorization.require_healthy()
            try:
                self._process.wait(timeout=0)
            except RuntimeRefusalError as error:
                if error.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED:
                    return
                raise
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)

    def install(self, lease: AccessSession, dek: bytearray) -> None:
        """Consume verified material only after native containment and mutual readiness."""
        self._exchange(
            ProfileWorkerRequest(ProfileWorkerLeaseRequest(action="install", request_id=uuid4(), lease=lease)),
            ProfileWorkerStatus,
            dek,
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
        with self._lock:
            try:
                result = self._exchange(
                    ProfileWorkerRequest(ProfileWorkerControlRequest(action=method, request_id=uuid4())),
                    ProfileWorkerHumanOutcome,
                    secret,
                )
                self._human_candidate = result.candidate_id
                yield result.login
            finally:
                self._human_candidate = None
                secret[:] = bytes(len(secret))
                if self._channel is not None:
                    self._exchange(
                        ProfileWorkerRequest(ProfileWorkerControlRequest(action="cancel_human", request_id=uuid4())),
                        ProfileWorkerStatus,
                    )

    def bind_human(self, lease: AccessSession, *, persist_receipt: bool = False) -> ProfileHumanLoginReceipt:
        """Promote only the human candidate held by this admission context."""
        with self._lock:
            if self._human_candidate is None:
                raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
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
            )
            if result.session_id != lease.session_id:
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            self._human_candidate = None
            return result.receipt

    def close(self, *, deadline: float | None = None) -> None:
        """Fence calls and terminate the complete owned process scope."""
        if self._authorization is not None:
            self._authorization.close()
        # Contain first: an operation may be waiting for the caller's profile
        # guard. Do not wait for its transport lock while it is still alive.
        self._scope.terminate(timeout=2.0 if deadline is None else max(0.0, deadline - time.monotonic()))
        acquired_control = self._lock.acquire(
            timeout=2.0 if deadline is None else max(0.0, deadline - time.monotonic())
        )
        if not acquired_control:
            raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
        try:
            acquired_operation = self._operation_lock.acquire(
                timeout=2.0 if deadline is None else max(0.0, deadline - time.monotonic())
            )
            if not acquired_operation:
                raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
            try:
                if self._channel is not None:
                    self._channel.close()
                    self._channel = None
                if self._operation_channel is not None:
                    self._operation_channel.close()
                    self._operation_channel = None
            finally:
                self._operation_lock.release()
        finally:
            self._lock.release()

    def settle(self, *, deadline: float | None = None) -> None:
        """Join authorization callbacks after releasing the profile admission guard."""
        if self._authorization is not None:
            if deadline is None:
                self._authorization.settle()
            else:
                self._authorization.settle(timeout=max(0.0, deadline - time.monotonic()))
