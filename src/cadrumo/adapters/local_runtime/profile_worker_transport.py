"""ProfileWorkerTransport for runtime-owned profile worker custody."""

from __future__ import annotations

import time
from threading import RLock
from uuid import UUID, uuid4

from pydantic import BaseModel

from ...application.operations.models import OperationIdentity
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.deadline_budget import remaining_budget
from ...application.runtime.profile_worker import (
    ProfileWorkerControlRequest,
    ProfileWorkerDrained,
    ProfileWorkerHumanBindingRequest,
    ProfileWorkerLeaseRequest,
    ProfileWorkerRefusal,
    ProfileWorkerReply,
    ProfileWorkerRequest,
    ProfileWorkerRetireRequest,
    ProfileWorkerSettlement,
    ProfileWorkerSettlementRequest,
    ProfileWorkerStatus,
)
from ...application.runtime.worker_authorization import AUTHORITY_SECTION_MAXIMUM_SECONDS
from ...application.user_profile.access_contracts import AccessDenialCode, AccessSession
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...application.user_profile.automation_custody_port import AutomationCustodyError
from .linux_worker_process import LinuxProcessScope
from .macos_worker_process import MacosProcessScope
from .profile_worker_lifetime import ProfileWorkerNativeLifetime
from .runtime_frame_io import read_document, write_document, write_secret
from .runtime_transport_cleanup import RuntimeTransportCleanup
from .worker_admission_budget import WORKER_ADMISSION_PREPARE_TIMEOUT_SECONDS
from .worker_lease_transfer import write_worker_lease
from .worker_resource_cleanup import WorkerResourceCleanup, release_worker_resources
from .worker_transport import WorkerChannel

#: A worker answers a registered-operation request only after it holds a fresh
#: runtime authority lease: it may spend 5 s connecting for one and
#: ``AUTHORITY_SECTION_MAXIMUM_SECONDS + 5`` acquiring it, then writes within
#: 5 s. A missed reply contains the whole worker, so a shorter wait would stop
#: every operation it runs while the worker is still inside its own bounded wait.
_OPERATION_EXCHANGE_SECONDS = AUTHORITY_SECTION_MAXIMUM_SECONDS + 15
_CONTROL_EXCHANGE_SECONDS = 10


class ProfileWorkerTransport(ProfileWorkerNativeLifetime):
    """Own the worker capability while retaining native custody and deadlines."""

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
            _acquire_exchange_lock(lock, deadline)
            acquired = True
            try:
                channel = self._exchange_channel(operation)
                default_seconds = _OPERATION_EXCHANGE_SECONDS if operation else _CONTROL_EXCHANGE_SECONDS
                wire_deadline = time.monotonic() + default_seconds if deadline is None else deadline
                return self._read_exchange_reply(channel, request, response, secret, wire_deadline)
            finally:
                lock.release()
        except (AutomationCustodyError, ProfileAccessRefusedError):
            raise
        except BaseException as error:
            # No frame was sent when a caller merely timed out waiting for
            # this shared channel. Keep other sessions' worker alive.
            if acquired:
                self._retire_failed_exchange(error, deadline)
            raise
        finally:
            if secret is not None:
                secret[:] = bytes(len(secret))

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
            deadline=(time.monotonic() + WORKER_ADMISSION_PREPARE_TIMEOUT_SECONDS if deadline is None else deadline),
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

    def _exchange_channel(self, operation: bool) -> WorkerChannel:
        """Require a retained channel and current native containment while its transport lock is held."""
        channel = self._operation_channel if operation else self._channel
        if channel is None or self._stopping.is_set():
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
        if isinstance(self._scope, LinuxProcessScope | MacosProcessScope):
            with self._native_guard:
                if self._stopping.is_set() or not self._scope.owns_process(self._scope.worker_pid):
                    raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        return channel

    def _read_exchange_reply[Result: BaseModel](
        self,
        channel: WorkerChannel,
        request: ProfileWorkerRequest,
        response: type[Result],
        secret: bytearray | None,
        wire_deadline: float,
    ) -> Result:
        """Exchange one addressed request and preserve exact application refusals."""
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
                raise ProfileAccessRefusedError(result.reason, sign_in=result.sign_in)
            raise AutomationCustodyError(result.reason)
        if not isinstance(result, response):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return result

    def _retire_failed_exchange(self, error: BaseException, deadline: float | None) -> None:
        """Retain failed native cleanup without closing an already released channel twice."""
        self._stopping.set()
        released = error.__dict__.get("_runtime_transport_cleanup")
        if isinstance(released, RuntimeTransportCleanup) and released.released:
            # Framing has already released this exact native channel.
            # Physical worker containment must not close it a second time.
            if released.resource is self._channel:
                self._channel = None
            if released.resource is self._operation_channel:
                self._operation_channel = None
        release_worker_resources(
            WorkerResourceCleanup(lambda: self.close(deadline=deadline), retry_release=self.close), primary_error=error
        )


def _acquire_exchange_lock(lock: RLock, deadline: float | None) -> None:
    """Refuse an expired queued caller before any frame is sent or custody is retired."""
    if deadline is None:
        lock.acquire()
        return
    remaining = remaining_budget(deadline)
    if not lock.acquire(timeout=remaining):
        raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
    try:
        remaining_budget(deadline)
    except RuntimeRefusalError:
        lock.release()
        raise
