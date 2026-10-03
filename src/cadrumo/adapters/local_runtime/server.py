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
from ...application.runtime.profile_access import (
    RuntimeAccessRefusal,
    RuntimeProfileDrainResult,
    RuntimeProfileHandler,
    RuntimeProfileStatus,
    RuntimeRequest,
)
from ...application.runtime.transport import RuntimeConnectionContext, RuntimeStatusRequest, RuntimeTransportStatus
from ...core.async_cleanup import AsyncResourceCleanupError
from ...core.time.clock import now
from .framing import (
    RuntimeTransportCleanup,
    accept_runtime_handshake,
    close_runtime_transport_after_failure,
    read_document,
    write_document,
    write_profile_status,
)
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
        finalize_owner_stop: Callable[[], None] | None = None,
    ) -> None:
        """Bind one endpoint and a fresh process boot, without claiming ownership yet."""
        self.listener = listener
        self._listener_owner = RuntimeTransportCleanup(listener)
        self.stop = stop
        self.profiles = profiles
        self._capture_owner_login = capture_owner_login
        self._owner_stop_available = owner_stop_available
        self._prepare_owner_stop = prepare_owner_stop
        self._finalize_owner_stop = finalize_owner_stop
        self._owner_stop_prepared = Event()
        self._owner_stop_finalized = Event()
        self.identity = RuntimeServerHello(
            product_version=product_version, storage_identity=listener.storage_identity, boot_id=boot_id or uuid4()
        )
        self.ready = Event()
        self._failed = Event()
        self._slots = BoundedSemaphore(32)
        self._channels_guard = RLock()
        self._channels: dict[int, RuntimeTransportCleanup] = {}
        self._owner_stop_completions: dict[int, Event] = {}
        self._requests: set[Future[None]] = set()
        self._drain_guard = RLock()
        self._serve_finished = Event()

    def _channel_owner(self, channel: RuntimeByteChannel) -> RuntimeTransportCleanup:
        with self._channels_guard:
            owner = self._channels.get(id(channel))
            if owner is None:
                owner = RuntimeTransportCleanup(channel)
                self._channels[id(channel)] = owner
            return owner

    def _retain_channel_cleanup(
        self,
        error: BaseException,
        *,
        channel: RuntimeByteChannel | None = None,
        require_registered: bool = False,
    ) -> RuntimeTransportCleanup | None:
        owner = error.__dict__.get("_runtime_transport_cleanup")
        if isinstance(owner, RuntimeTransportCleanup):
            if channel is not None and owner.resource is not channel:
                return None
            with self._channels_guard:
                if require_registered and id(owner.resource) not in self._channels:
                    return None
                self._channels[id(owner.resource)] = owner
            self._forget_closed_channel(owner)
            return owner
        return None

    def _forget_closed_channel(self, owner: RuntimeTransportCleanup) -> None:
        if owner.released:
            with self._channels_guard:
                if self._channels.get(id(owner.resource)) is owner:
                    self._channels.pop(id(owner.resource))

    def _close_owned_channel(self, owner: RuntimeTransportCleanup, *, deadline: float | None = None) -> None:
        try:
            owner.close_now(deadline=deadline)
        finally:
            self._forget_closed_channel(owner)

    def _connection(self, channel: RuntimeByteChannel) -> None:
        channel_owner = self._channel_owner(channel)
        context: RuntimeConnectionContext | None = None
        cleanup_deferred = False
        private_used = False
        owner_attempted = False
        owner: RuntimeOwnerControl | None = None
        try:
            context = RuntimeConnectionContext(uuid4(), self.identity.boot_id, channel.peer)
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
                                self._owner_stop_prepared.set()
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
                if isinstance(status, RuntimeProfileStatus):
                    write_profile_status(channel, status, deadline=time.monotonic() + 5)
                else:
                    write_document(channel, status, deadline=time.monotonic() + 5)
        except RuntimeRefusalError as error:
            retained = self._retain_channel_cleanup(error, channel=channel)
            if retained is not None:
                channel_owner = retained
                cleanup_deferred = not retained.released
            # No peer input or secret bytes become a diagnostic. Incompatible,
            # malformed, disconnected and timed-out connections end locally.
            return
        except BaseException as error:
            if not isinstance(error, Exception):
                close_runtime_transport_after_failure(channel, error)
            retained = self._retain_channel_cleanup(error, channel=channel)
            if retained is not None:
                channel_owner = retained
                cleanup_deferred = not retained.released
            self._failed.set()
            self.stop.set()
            if not isinstance(error, Exception):
                raise
        finally:
            try:
                if self.profiles is not None and context is not None:
                    self.profiles.disconnect(context)
            except Exception:
                self._failed.set()
                self.stop.set()
            finally:
                try:
                    if cleanup_deferred:
                        self._failed.set()
                        self.stop.set()
                    else:
                        self._close_owned_channel(channel_owner)
                except BaseException:
                    self._failed.set()
                    self.stop.set()
                    raise
                finally:
                    self._slots.release()

    def serve(self) -> None:
        """Hold singleton ownership through all accepted connection cleanup."""
        incomplete = Event()
        primary_error: BaseException | None = None
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
                    try:
                        result = self._drain_owned_resources(deadline=deadline)
                    except BaseException:
                        incomplete.set()
                        raise
                    if result is not None and result.missing_receipts:
                        self._failed.set()
                    try:
                        self._finalize_prepared_owner_stop()
                    except RuntimeShutdownIncompleteError:
                        incomplete.set()
                        raise
            finally:
                workers.shutdown(wait=False, cancel_futures=True)
            if self._failed.is_set():
                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        except BaseException as error:
            primary_error = error
            raise
        finally:
            self.ready.clear()
            try:
                if not incomplete.is_set():
                    self._release_listener(primary_error)
            finally:
                self._serve_finished.set()

    def retry_drain(self, *, deadline: float) -> None:
        """Retry a terminal host's retained shutdown within the caller's absolute bound."""
        if not self._serve_finished.is_set():
            raise RuntimeShutdownIncompleteError()
        if not self._drain_guard.acquire(timeout=max(0.0, deadline - time.monotonic())):
            raise RuntimeShutdownIncompleteError()
        try:
            if not self._listener_owner.released:
                result = self._drain_owned_resources(deadline=deadline)
                if result is not None and result.missing_receipts:
                    self._failed.set()
                self._finalize_prepared_owner_stop()
                self._release_listener(None, deadline=deadline)
            if self._failed.is_set():
                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        finally:
            self._drain_guard.release()

    def _finalize_prepared_owner_stop(self) -> None:
        if (
            not self._owner_stop_prepared.is_set()
            or self._finalize_owner_stop is None
            or self._owner_stop_finalized.is_set()
        ):
            return
        try:
            self._finalize_owner_stop()
        except BaseException as error:
            # Native termination may have uncertain effects. The retained
            # listener and same finalizer remain owned through a drain retry.
            raise RuntimeShutdownIncompleteError() from error
        self._owner_stop_finalized.set()

    def _drain_owned_resources(self, *, deadline: float) -> RuntimeProfileDrainResult | None:
        if not self._drain_guard.acquire(timeout=max(0.0, deadline - time.monotonic())):
            raise RuntimeShutdownIncompleteError()
        try:
            result = None
            drain_error: BaseException | None = None
            incomplete = False
            try:
                if self.profiles is not None:
                    result = self.profiles.drain(deadline=deadline)
            except BaseException as error:
                drain_error = error
                incomplete = True
            with self._channels_guard:
                owner_stops = tuple(self._owner_stop_completions.values())
            # A native manager may signal us while its confirming connection is
            # sending acceptance. Keep the same absolute drain budget.
            for completion in owner_stops:
                completion.wait(timeout=max(0.0, deadline - time.monotonic()))
            with self._channels_guard:
                channels = tuple(self._channels.values())
                requests = tuple(self._requests)
            for channel_owner in channels:
                try:
                    self._close_owned_channel(channel_owner, deadline=deadline)
                except BaseException:
                    incomplete = True
            _, pending = wait(requests, timeout=max(0.0, deadline - time.monotonic()))
            with self._channels_guard:
                unsettled_transport = bool(self._channels or self._requests)
            if (
                incomplete
                or pending
                or unsettled_transport
                or (result is not None and (result.uncontained or result.unsettled))
            ):
                raise RuntimeShutdownIncompleteError() from drain_error
            return result
        finally:
            self._drain_guard.release()

    def _release_listener(self, primary_error: BaseException | None, *, deadline: float | None = None) -> None:
        try:
            self._listener_owner.close_now(deadline=deadline)
        except BaseException as release_error:
            cleanup_error = AsyncResourceCleanupError(
                (self._listener_owner,),
                (release_error,),
                retry_task_name="runtime-listener-cleanup",
                close_attempts=1,
            )
            if primary_error is None:
                raise cleanup_error from release_error
            previous = primary_error.__dict__.get("async_cleanup_error")
            if isinstance(previous, AsyncResourceCleanupError):
                cleanup_error = previous.merged_with(cleanup_error)
            primary_error.__dict__["async_cleanup_error"] = cleanup_error
            primary_error.add_note("Listener cleanup also failed; retry through the attached async_cleanup_error")

    def _accept_connections(self, workers: ThreadPoolExecutor) -> None:
        while not self.stop.is_set():
            if self.profiles is not None:
                self.profiles.poll()
            if self.stop.is_set():
                return
            try:
                channel = self.listener.accept(timeout=0.2)
            except RuntimeRefusalError as error:
                retained = self._retain_channel_cleanup(error)
                if retained is not None and not retained.released:
                    self._failed.set()
                    self.stop.set()
                    raise
                if error.reason in {
                    RuntimeRefusalCode.DEADLINE_EXCEEDED,
                    RuntimeRefusalCode.PEER_UNTRUSTED,
                    RuntimeRefusalCode.CONNECTION_CLOSED,
                }:
                    continue
                raise
            except BaseException as error:
                self._retain_channel_cleanup(error)
                raise
            channel_owner = self._channel_owner(channel)
            if self.stop.is_set() or not self._slots.acquire(blocking=False):
                self._close_owned_channel(channel_owner)
                continue
            try:
                future = workers.submit(self._connection, channel)
            except BaseException as error:
                try:
                    close_runtime_transport_after_failure(channel, error)
                    self._retain_channel_cleanup(error, channel=channel)
                finally:
                    self._slots.release()
                raise
            with self._channels_guard:
                self._requests.add(future)
            future.add_done_callback(self._forget_request)

    def _forget_request(self, request: Future[None]) -> None:
        with self._channels_guard:
            if request.cancelled():
                self._failed.set()
                self.stop.set()
            else:
                error = request.exception()
                if error is not None:
                    self._retain_channel_cleanup(error, require_registered=True)
                    self._failed.set()
                    self.stop.set()
            self._requests.discard(request)
