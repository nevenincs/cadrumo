"""Bounded concurrent transport hosting over native owner-verified endpoints."""

from __future__ import annotations

import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor, wait
from threading import BoundedSemaphore, Event, RLock
from typing import Protocol
from uuid import UUID, uuid4

from ...application.runtime.access_management import (
    RuntimeAutomationDeny,
    RuntimeProfileRecoveryPrepare,
    RuntimeProfileResume,
    RuntimeSessionInventory,
)
from ...application.runtime.contracts import (
    RuntimeByteChannel,
    RuntimeRefusalCode,
    RuntimeRefusalError,
    RuntimeServerHello,
    RuntimeShutdownIncompleteError,
)
from ...application.runtime.enrollment_access import (
    RuntimeEnrollmentInspect,
    RuntimeEnrollmentPoll,
    RuntimeEnrollmentPrepare,
    RuntimeEnrollmentReconcile,
    RuntimeEnrollmentSubmit,
)
from ...application.runtime.login import RuntimeLoginEvidence
from ...application.runtime.operation_access import (
    RuntimeOperationContract,
    RuntimeOperationControl,
    RuntimeOperationManage,
    RuntimeOperationObserve,
    RuntimeOperationResult,
    RuntimeOperationResultPage,
    RuntimeOperationReview,
    RuntimeOperationSecret,
    RuntimeOperationSubmit,
    RuntimeOperationSubmitPayload,
)
from ...application.runtime.owner_control import RuntimeOwnerControl, RuntimeStopConfirm, RuntimeStopPreviewRequest
from ...application.runtime.profile_access import RuntimeAccessRefusal, RuntimeProfileHandler, RuntimeRequest
from ...application.runtime.transport import RuntimeConnectionContext, RuntimeStatusRequest, RuntimeTransportStatus
from ...core.time.clock import now
from .framing import accept_runtime_handshake, read_document, write_document
from .login import capture_runtime_login


class RuntimeListener(Protocol):
    """Exclusive native ownership with bounded acceptance and verified peers."""

    @property
    def storage_identity(self) -> str:
        """Return the canonical root identity selected by the native endpoint."""
        ...

    def listen(self) -> None:
        """Claim ownership, refusing any existing live owner."""
        ...

    def accept(self, *, timeout: float) -> RuntimeByteChannel:
        """Accept a kernel-verified peer within the supplied deadline."""
        ...

    def close(self) -> None:
        """Release native listener ownership after accepted channels settle."""
        ...


class RuntimeTransportServer:
    """Host public readiness and the application-owned profile admission door.

    Each unauthenticated connection has bounded I/O and its own identity. The
    fixed worker count bounds peer resource consumption. Operation execution
    belongs to the application supervisor, never to this transport pool.
    """

    DRAIN_SECONDS = 15.0

    def __init__(
        self,
        listener: RuntimeListener,
        *,
        product_version: str,
        stop: Event,
        profiles: RuntimeProfileHandler | None = None,
        boot_id: UUID | None = None,
        capture_owner_login: Callable[[RuntimeByteChannel], RuntimeLoginEvidence] = capture_runtime_login,
        owner_stop_available: bool = True,
        prepare_owner_stop: Callable[[], None] | None = None,
    ) -> None:
        """Bind one endpoint and a fresh process boot, without claiming ownership yet."""
        self.listener = listener
        self.stop = stop
        self.profiles = profiles
        self._capture_owner_login = capture_owner_login
        self._owner_stop_available = owner_stop_available
        self._prepare_owner_stop = prepare_owner_stop
        self.identity = RuntimeServerHello(
            product_version=product_version, storage_identity=listener.storage_identity, boot_id=boot_id or uuid4()
        )
        self.ready = Event()
        self._failed = Event()
        self._slots = BoundedSemaphore(32)
        self._channels_guard = RLock()
        self._channels: dict[int, RuntimeByteChannel] = {}
        self._owner_stop_completions: dict[int, Event] = {}
        self._requests: set[Future[None]] = set()

    def _connection(self, channel: RuntimeByteChannel) -> None:
        context = RuntimeConnectionContext(uuid4(), self.identity.boot_id, channel.peer)
        private_used = False
        owner_attempted = False
        owner: RuntimeOwnerControl | None = None
        try:
            accept_runtime_handshake(channel, identity=self.identity, deadline=time.monotonic() + 5)
            while not self.stop.is_set():
                if not channel.read_ready():
                    self.stop.wait(0.05)
                    continue
                request = read_document(channel, RuntimeRequest, deadline=time.monotonic() + 5).root
                if isinstance(request, RuntimeStopPreviewRequest | RuntimeStopConfirm):
                    owner_attempted = True
                    completion: Event | None = None
                    try:
                        try:
                            if private_used:
                                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
                            if not self._owner_stop_available:
                                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
                            if owner is None:
                                owner = RuntimeOwnerControl(context, login=self._capture_owner_login(channel))
                            if isinstance(request, RuntimeStopPreviewRequest):
                                control_reply = owner.preview(request, now=now(), monotonic_now=time.monotonic())
                            else:
                                control_reply = owner.confirm(request, now=now(), monotonic_now=time.monotonic())
                                completion = Event()
                                with self._channels_guard:
                                    self._owner_stop_completions[id(channel)] = completion
                                if self._prepare_owner_stop is not None:
                                    self._prepare_owner_stop()
                        except RuntimeRefusalError as error:
                            write_document(
                                channel,
                                RuntimeAccessRefusal(
                                    request_id=request.request_id,
                                    runtime_boot_id=context.runtime_boot_id,
                                    connection_id=context.connection_id,
                                    code=error.reason,
                                ),
                                deadline=time.monotonic() + 5,
                            )
                            continue
                        try:
                            write_document(channel, control_reply, deadline=time.monotonic() + 5)
                        finally:
                            if isinstance(request, RuntimeStopConfirm):
                                # A lost acknowledgement cannot undo accepted
                                # manager preparation or imply domain rollback.
                                self.stop.set()
                    finally:
                        if completion is not None:
                            completion.set()
                            with self._channels_guard:
                                self._owner_stop_completions.pop(id(channel), None)
                    continue
                if not isinstance(request, RuntimeStatusRequest):
                    if owner_attempted:
                        write_document(
                            channel,
                            RuntimeAccessRefusal(
                                request_id=request.request_id,
                                runtime_boot_id=context.runtime_boot_id,
                                connection_id=context.connection_id,
                                code=RuntimeRefusalCode.PEER_UNTRUSTED,
                            ),
                            deadline=time.monotonic() + 5,
                        )
                        continue
                    private_used = True
                if isinstance(request, RuntimeStatusRequest):
                    status = RuntimeTransportStatus(
                        request_id=request.request_id,
                        runtime_boot_id=context.runtime_boot_id,
                        connection_id=context.connection_id,
                        accepting_connections=not self.stop.is_set(),
                    )
                elif isinstance(
                    request,
                    RuntimeAutomationDeny
                    | RuntimeProfileRecoveryPrepare
                    | RuntimeProfileResume
                    | RuntimeSessionInventory,
                ):
                    if self.profiles is not None:
                        self.profiles.manage_access(context, channel, request)
                        continue
                    status = RuntimeAccessRefusal(
                        request_id=request.request_id,
                        runtime_boot_id=context.runtime_boot_id,
                        connection_id=context.connection_id,
                        code=RuntimeRefusalCode.UNAVAILABLE,
                    )
                elif isinstance(
                    request,
                    RuntimeEnrollmentPrepare
                    | RuntimeEnrollmentSubmit
                    | RuntimeEnrollmentInspect
                    | RuntimeEnrollmentPoll
                    | RuntimeEnrollmentReconcile,
                ):
                    if self.profiles is not None:
                        self.profiles.enrollment(context, channel, request)
                        continue
                    status = RuntimeAccessRefusal(
                        request_id=request.request_id,
                        runtime_boot_id=context.runtime_boot_id,
                        connection_id=context.connection_id,
                        code=RuntimeRefusalCode.UNAVAILABLE,
                    )
                elif isinstance(
                    request,
                    RuntimeOperationSubmit
                    | RuntimeOperationSubmitPayload
                    | RuntimeOperationControl
                    | RuntimeOperationObserve
                    | RuntimeOperationContract
                    | RuntimeOperationResult
                    | RuntimeOperationResultPage
                    | RuntimeOperationReview
                    | RuntimeOperationManage
                    | RuntimeOperationSecret,
                ):
                    if self.profiles is not None:
                        self.profiles.operation(context, channel, request)
                        continue
                    status = RuntimeAccessRefusal(
                        request_id=request.request_id,
                        runtime_boot_id=context.runtime_boot_id,
                        connection_id=context.connection_id,
                        code=RuntimeRefusalCode.UNAVAILABLE,
                    )
                elif self.profiles is not None:
                    status = self.profiles.handle(context, channel, request)
                else:
                    status = RuntimeAccessRefusal(
                        request_id=request.request_id,
                        runtime_boot_id=context.runtime_boot_id,
                        connection_id=context.connection_id,
                        code=RuntimeRefusalCode.UNAVAILABLE,
                    )
                write_document(channel, status, deadline=time.monotonic() + 5)
        except RuntimeRefusalError:
            # No peer input or secret bytes become a diagnostic. Incompatible,
            # malformed, disconnected and timed-out connections end locally.
            return
        except Exception:
            self._failed.set()
            self.stop.set()
        finally:
            try:
                if self.profiles is not None:
                    self.profiles.disconnect(context)
            except Exception:
                self._failed.set()
                self.stop.set()
            finally:
                channel.close()
                with self._channels_guard:
                    self._channels.pop(id(channel), None)
                self._slots.release()

    def serve(self) -> None:
        """Hold singleton ownership through all accepted connection cleanup."""
        incomplete = Event()
        try:
            self.listener.listen()
            workers = ThreadPoolExecutor(max_workers=32, thread_name_prefix="cadrumo-ipc")
            try:
                self.ready.set()
                try:
                    self._accept_connections(workers)
                finally:
                    self.stop.set()
                    deadline = time.monotonic() + self.DRAIN_SECONDS
                    result = None
                    drain_error: BaseException | None = None
                    try:
                        if self.profiles is not None:
                            result = self.profiles.drain(deadline=deadline)
                    except BaseException as error:
                        drain_error = error
                        incomplete.set()
                    finally:
                        with self._channels_guard:
                            owner_stops = tuple(self._owner_stop_completions.values())
                        # A native manager may signal us while its confirming
                        # connection is still sending the acceptance. Retain
                        # that connection within the same global drain bound.
                        for completion in owner_stops:
                            completion.wait(timeout=max(0.0, deadline - time.monotonic()))
                        with self._channels_guard:
                            channels = tuple(self._channels.values())
                            requests = tuple(self._requests)
                        for channel in channels:
                            try:
                                channel.close()
                            except BaseException:
                                incomplete.set()
                    _, pending = wait(requests, timeout=max(0.0, deadline - time.monotonic()))
                    if pending or (result is not None and (result.uncontained or result.unsettled)):
                        incomplete.set()
                    if incomplete.is_set():
                        raise RuntimeShutdownIncompleteError() from drain_error
                    if result is not None and result.missing_receipts:
                        self._failed.set()
            finally:
                workers.shutdown(wait=False, cancel_futures=True)
            if self._failed.is_set():
                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        finally:
            self.ready.clear()
            if not incomplete.is_set():
                self.listener.close()

    def _accept_connections(self, workers: ThreadPoolExecutor) -> None:
        while not self.stop.is_set():
            if self.profiles is not None:
                self.profiles.poll()
            try:
                channel = self.listener.accept(timeout=0.2)
            except RuntimeRefusalError as error:
                if error.reason in {
                    RuntimeRefusalCode.DEADLINE_EXCEEDED,
                    RuntimeRefusalCode.PEER_UNTRUSTED,
                    RuntimeRefusalCode.CONNECTION_CLOSED,
                }:
                    continue
                raise
            if self.stop.is_set() or not self._slots.acquire(blocking=False):
                channel.close()
                continue
            try:
                with self._channels_guard:
                    self._channels[id(channel)] = channel
                future = workers.submit(self._connection, channel)
                with self._channels_guard:
                    self._requests.add(future)
                future.add_done_callback(self._forget_request)
            except BaseException:
                with self._channels_guard:
                    self._channels.pop(id(channel), None)
                channel.close()
                self._slots.release()
                raise

    def _forget_request(self, request: Future[None]) -> None:
        with self._channels_guard:
            self._requests.discard(request)
