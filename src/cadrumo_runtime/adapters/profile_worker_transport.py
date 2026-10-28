"""ProfileWorkerTransport for runtime-owned profile worker custody."""

from __future__ import annotations

import logging
import time
from threading import RLock
from typing import NoReturn
from uuid import UUID, uuid4

from pydantic import BaseModel

from cadrumo.application.operations.models import OperationIdentity
from cadrumo.application.user_profile.access_contracts import AccessSession
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.proof_cancellation import ProfileProofCancelledError
from cadrumo.core.diagnostic_log import diagnostic_error_fields, diagnostic_event
from cadrumo.core.logging import get_logger
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.automation_codes import AutomationCustodyCode, AutomationCustodyError
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.deadline_budget import (
    DEFAULT_TIMEOUT_POLICY,
    MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS,
    remaining_budget,
)
from cadrumo_client.contracts.extension_records import ExtensionRecordReply, ProfileWorkerExtensionRecordRequest
from cadrumo_client.transport.frame_io import read_document, read_secret, write_document, write_secret
from cadrumo_client.transport.transport_cleanup import TransportCleanup
from cadrumo_runtime.contracts.profile_worker import (
    ProfileWorkerActivity,
    ProfileWorkerControlRequest,
    ProfileWorkerDrained,
    ProfileWorkerExtensionRecordReply,
    ProfileWorkerHumanBindingRequest,
    ProfileWorkerLeaseRequest,
    ProfileWorkerProofTransfer,
    ProfileWorkerRefusal,
    ProfileWorkerReply,
    ProfileWorkerRequest,
    ProfileWorkerRetireRequest,
    ProfileWorkerSettlement,
    ProfileWorkerSettlementRequest,
    ProfileWorkerStatus,
)

from .linux_worker_process import LinuxProcessScope
from .macos_worker_process import MacosProcessScope
from .profile_worker_lifetime import ProfileWorkerNativeLifetime
from .worker_admission_budget import WORKER_ADMISSION_PREPARE_TIMEOUT_SECONDS
from .worker_lease_transfer import write_worker_lease
from .worker_resource_cleanup import WorkerResourceCleanup, release_worker_resources
from .worker_transport import WorkerChannel

#: A worker answers a registered-operation request only after it holds a fresh
#: runtime authority lease, which the runtime may queue behind a running
#: COMMIT's fence. The worker allows that acquisition the runtime's
#: single-exchange budget, so this wait matches it: a missed reply contains the
#: whole worker, and a shorter wait would stop it while it still waits its turn.
_OPERATION_EXCHANGE_SECONDS = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS
#: Control waits end on the reply or actual channel/process loss. The remaining
#: finite bound is timeout containment, never a readiness or performance test.
_CONTROL_EXCHANGE_SECONDS = DEFAULT_TIMEOUT_POLICY.timeout_seconds
#: How often an owed activity reply is looked for. Readiness is observed without
#: consuming bytes, so a probe can stop waiting without desynchronising the stream.
_PROBE_POLL_SECONDS = 0.02

_LOGGER = get_logger(__name__)


class ProfileWorkerTransport(ProfileWorkerNativeLifetime):
    """Own the worker capability while retaining native custody and deadlines."""

    #: The activity request whose reply has not been read yet. It is the next
    #: frame on the control stream, so it is consumed before any other exchange.
    _unanswered_probe: UUID | None = None

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
        dispatched = False
        started = time.monotonic()
        default_seconds = _OPERATION_EXCHANGE_SECONDS if operation else _CONTROL_EXCHANGE_SECONDS
        wire_deadline = started + default_seconds if deadline is None else deadline
        queue_seconds = 0.0
        try:
            _acquire_exchange_lock(lock, wire_deadline, request, operation=operation)
            try:
                channel = self._exchange_channel(operation)
                queue_seconds = time.monotonic() - started
                dispatched = True
                try:
                    if not operation and not self._settle_unanswered_probe(channel, wire_deadline):
                        # Nothing of this request was sent; the worker has not answered an earlier probe yet.
                        dispatched = False
                        raise RefusalError(RefusalCode.TIMEOUT)
                    return self._read_exchange_reply(channel, request, response, secret, wire_deadline)
                except (AutomationCustodyError, ProfileAccessRefusedError):
                    raise
                except BaseException:
                    if dispatched:
                        # Fence the failed stream before a queued caller can borrow it.
                        self._stopping.set()
                    raise
            finally:
                lock.release()
        except (AutomationCustodyError, ProfileAccessRefusedError):
            raise
        except BaseException as error:
            # No frame was sent when a caller merely timed out waiting for
            # this shared channel. Keep other sessions' worker alive.
            if dispatched:
                self._retire_failed_dispatch(
                    request,
                    error,
                    operation=operation,
                    queue_seconds=queue_seconds,
                    elapsed_seconds=time.monotonic() - started,
                    budget_seconds=wire_deadline - started,
                    deadline=deadline,
                )
            raise
        finally:
            if secret is not None:
                secret[:] = bytes(len(secret))

    def _retire_failed_dispatch(
        self,
        request: ProfileWorkerRequest,
        error: BaseException,
        *,
        operation: bool,
        queue_seconds: float,
        elapsed_seconds: float,
        budget_seconds: float,
        deadline: float | None,
    ) -> None:
        # Retiring ends the worker and every session and operation it holds: say which exchange did it.
        diagnostic_event(
            _LOGGER,
            "profile_worker_exchange_failed",
            fields={
                "request_type": type(request.root).__name__,
                "request_action": request.root.action
                if isinstance(request.root, ProfileWorkerControlRequest | ProfileWorkerLeaseRequest)
                else None,
                "operation_channel": operation,
                "phase": "exchange",
                "reason": error.reason.value if isinstance(error, RefusalError) else None,
                "queue_seconds": round(queue_seconds, 3),
                "elapsed_seconds": round(elapsed_seconds, 3),
                "budget_seconds": round(budget_seconds, 3),
                **diagnostic_error_fields(error),
            },
            level=logging.WARNING,
            primary_error=error,
        )
        self._retire_failed_exchange(error, deadline)

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

    def activity(self, *, deadline: float) -> ProfileWorkerActivity | None:
        """Read how many operations the worker is running, without revalidating its custody.

        Return ``None`` when the worker has not answered by ``deadline``. A late
        answer is no evidence the worker is dead, so it is neither fenced nor
        contained. Its reply stays owed: the next control exchange consumes it
        first, and no further probe is sent until it arrives. A closed channel,
        an exited process or a malformed reply still contains the worker.
        """
        request = ProfileWorkerRequest(ProfileWorkerControlRequest(action="activity", request_id=uuid4()))
        started = time.monotonic()
        try:
            # The heartbeat expects to queue behind a busy channel now and then.
            _acquire_exchange_lock(self._lock, deadline, request, operation=False, level=logging.DEBUG)
        except RefusalError:
            return None
        queue_seconds = time.monotonic() - started
        try:
            channel = self._exchange_channel(False)
            try:
                if not self._settle_unanswered_probe(channel, deadline):
                    return None
                # A one-frame request: bound only a stalled pipe, never the worker's answer.
                write_document(channel, request, deadline=time.monotonic() + _CONTROL_EXCHANGE_SECONDS)
                self._unanswered_probe = request.root.request_id
                reply = self._take_probe_reply(channel, deadline)
            except BaseException as error:
                self._stopping.set()
                self._retire_failed_dispatch(
                    request,
                    error,
                    operation=False,
                    queue_seconds=queue_seconds,
                    elapsed_seconds=time.monotonic() - started,
                    budget_seconds=deadline - started,
                    deadline=None,
                )
                raise
        finally:
            self._lock.release()
        if isinstance(reply, ProfileWorkerRefusal):
            _raise_worker_refusal(reply)
        return reply

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
            raise RefusalError(RefusalCode.INVALID_FRAME)
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

    def extension_record(
        self, request: ProfileWorkerExtensionRecordRequest, payload: bytearray | None = None
    ) -> tuple[ExtensionRecordReply, bytearray]:
        """Exchange opaque bytes on the existing protected worker control pipe."""
        deadline = time.monotonic() + _CONTROL_EXCHANGE_SECONDS
        material = bytearray()
        undispatched = False
        _acquire_exchange_lock(self._lock, deadline, ProfileWorkerRequest(request), operation=False)
        try:
            channel = self._exchange_channel(False)
            if not self._settle_unanswered_probe(channel, deadline):
                undispatched = True
                raise RefusalError(RefusalCode.TIMEOUT)
            reply = self._read_exchange_reply(
                channel, ProfileWorkerRequest(request), ProfileWorkerExtensionRecordReply, payload, deadline
            ).result
            if reply.byte_count:
                with read_secret(channel, deadline=deadline) as secret:
                    if len(secret) != reply.byte_count:
                        raise RefusalError(RefusalCode.INVALID_FRAME)
                    material.extend(secret)
            return reply, material
        except BaseException as error:
            material[:] = bytes(len(material))
            if not undispatched:
                self._retire_failed_exchange(error, deadline)
            raise
        finally:
            self._lock.release()

    def _exchange_channel(self, operation: bool) -> WorkerChannel:
        """Require a retained channel and current native containment while its transport lock is held."""
        channel = self._operation_channel if operation else self._channel
        if channel is None or self._stopping.is_set():
            raise RefusalError(RefusalCode.CONNECTION_CLOSED)
        if isinstance(self._scope, LinuxProcessScope | MacosProcessScope):
            with self._native_guard, self._native_call("exchange_membership"):
                if self._stopping.is_set() or not self._scope.owns_process(self._scope.worker_pid):
                    raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
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
        proof = request.root if isinstance(request.root, ProfileWorkerControlRequest) else None
        if proof is not None and proof.proof_attempt_id is not None and self._human_cancellation is not None:
            try:
                self._human_cancellation.raise_if_cancelled()
            except ProfileProofCancelledError:
                raise AutomationCustodyError(AutomationCustodyCode.REQUESTER_DISCONNECTED) from None
        if isinstance(request.root, ProfileWorkerLeaseRequest | ProfileWorkerHumanBindingRequest):
            write_worker_lease(channel, request, deadline=wire_deadline)
        else:
            write_document(channel, request, deadline=wire_deadline)
        if proof is not None and proof.proof_attempt_id is not None:
            cancelled = False
            if self._human_cancellation is not None:
                try:
                    self._human_cancellation.raise_if_cancelled()
                except ProfileProofCancelledError:
                    cancelled = True
            write_document(
                channel,
                ProfileWorkerProofTransfer(proof_attempt_id=proof.proof_attempt_id, cancelled=cancelled),
                deadline=wire_deadline,
            )
            if cancelled:
                secret = None
        if secret is not None:
            write_secret(channel, secret, deadline=wire_deadline)
        result = read_document(channel, ProfileWorkerReply, deadline=wire_deadline).root
        if result.identity != self.identity or result.request_id != request.root.request_id:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        if isinstance(result, ProfileWorkerRefusal):
            _raise_worker_refusal(result)
        if not isinstance(result, response):
            raise RefusalError(RefusalCode.INVALID_FRAME)
        return result

    def _settle_unanswered_probe(self, channel: WorkerChannel, deadline: float) -> bool:
        """Discard an owed activity reply, or report it is still owed at ``deadline`` with nothing consumed."""
        return self._unanswered_probe is None or self._take_probe_reply(channel, deadline) is not None

    def _take_probe_reply(
        self, channel: WorkerChannel, deadline: float
    ) -> ProfileWorkerActivity | ProfileWorkerRefusal | None:
        """Consume the owed activity reply once it begins to arrive; ``None`` leaves it owed."""
        while not channel.read_ready():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            time.sleep(min(_PROBE_POLL_SECONDS, remaining))
        # The worker writes a reply as one frame. Once it has begun, a frame
        # that does not complete within the control budget is a framing fault.
        reply = read_document(channel, ProfileWorkerReply, deadline=time.monotonic() + _CONTROL_EXCHANGE_SECONDS).root
        if (
            reply.identity != self.identity
            or reply.request_id != self._unanswered_probe
            or not isinstance(reply, ProfileWorkerActivity | ProfileWorkerRefusal)
        ):
            raise RefusalError(RefusalCode.INVALID_FRAME)
        self._unanswered_probe = None
        return reply

    def _retire_failed_exchange(self, error: BaseException, deadline: float | None) -> None:
        """Retain failed native cleanup without closing an already released channel twice."""
        self._stopping.set()
        released = error.__dict__.get("_transport_cleanup")
        if isinstance(released, TransportCleanup) and released.released:
            # Framing has already released this exact native channel.
            # Physical worker containment must not close it a second time.
            if released.resource is self._channel:
                self._channel = None
            if released.resource is self._operation_channel:
                self._operation_channel = None
        release_worker_resources(
            WorkerResourceCleanup(lambda: self.close(deadline=deadline), retry_release=self.close), primary_error=error
        )


def _raise_worker_refusal(result: ProfileWorkerRefusal) -> NoReturn:
    """Preserve the worker's exact application refusal."""
    if result.reason is RefusalCode.TIMEOUT:
        raise RefusalError(RefusalCode.TIMEOUT)
    if isinstance(result.reason, AccessDenialCode):
        raise ProfileAccessRefusedError(
            result.reason, sign_in=result.sign_in, holder_operation_id=result.holder_operation_id
        )
    raise AutomationCustodyError(result.reason, request_faults=result.request_faults)


def _acquire_exchange_lock(
    lock: RLock,
    deadline: float | None,
    request: ProfileWorkerRequest,
    *,
    operation: bool,
    level: int = logging.WARNING,
) -> None:
    """Refuse an expired queued caller before any frame is sent or custody is retired."""
    if deadline is None:
        lock.acquire()
        return
    started = time.monotonic()
    try:
        remaining = remaining_budget(deadline)
        if not lock.acquire(timeout=remaining):
            raise RefusalError(RefusalCode.TIMEOUT)
    except RefusalError as error:
        _log_queue_timeout(request, error, operation=operation, started=started, deadline=deadline, level=level)
        raise
    try:
        remaining_budget(deadline)
    except RefusalError as error:
        lock.release()
        _log_queue_timeout(request, error, operation=operation, started=started, deadline=deadline, level=level)
        raise


def _log_queue_timeout(
    request: ProfileWorkerRequest,
    error: RefusalError,
    *,
    operation: bool,
    started: float,
    deadline: float,
    level: int,
) -> None:
    """Name a caller that gave up waiting for the shared channel; nothing was sent and the worker is kept."""
    diagnostic_event(
        _LOGGER,
        "profile_worker_exchange_queue_timeout",
        fields={
            "request_type": type(request.root).__name__,
            "request_action": request.root.action
            if isinstance(request.root, ProfileWorkerControlRequest | ProfileWorkerLeaseRequest)
            else None,
            "operation_channel": operation,
            "reason": error.reason.value,
            "queue_seconds": round(time.monotonic() - started, 3),
            "budget_seconds": round(max(0.0, deadline - started), 3),
        },
        level=level,
        primary_error=error,
    )
