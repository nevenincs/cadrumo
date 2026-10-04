"""Bounded request admission and retained connection cleanup for the runtime host."""

from __future__ import annotations

import time
from threading import BoundedSemaphore, Event, RLock
from uuid import uuid4

from ...application.runtime.access_management import (
    RuntimeAccessManagementRequest,
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
)
from ...application.runtime.enrollment_access import (
    RuntimeEnrollmentInspect,
    RuntimeEnrollmentPoll,
    RuntimeEnrollmentPrepare,
    RuntimeEnrollmentReconcile,
    RuntimeEnrollmentRequest,
    RuntimeEnrollmentSubmit,
)
from ...application.runtime.operation_access import (
    RuntimeOperationContract,
    RuntimeOperationControl,
    RuntimeOperationManage,
    RuntimeOperationObserve,
    RuntimeOperationRequest,
    RuntimeOperationResult,
    RuntimeOperationResultPage,
    RuntimeOperationReview,
    RuntimeOperationSecret,
    RuntimeOperationSubmit,
    RuntimeOperationSubmitPayload,
)
from ...application.runtime.profile_access import (
    RuntimeAccessRefusal,
    RuntimeProfileHandler,
    RuntimeProfileLogin,
    RuntimeProfileStatus,
    RuntimeRequest,
    RuntimeSessionRequest,
    RuntimeSessionsLocked,
)
from ...application.runtime.transport import RuntimeConnectionContext
from ...core.logging import get_logger
from .framing import accept_runtime_handshake
from .runtime_frame_io import read_document, write_document, write_profile_status
from .runtime_transport_cleanup import RuntimeTransportCleanup, close_runtime_transport_after_failure

_LOGGER = get_logger(__name__)

type _ProfileConnectionRequest = (
    RuntimeProfileLogin
    | RuntimeSessionRequest
    | RuntimeOperationRequest
    | RuntimeEnrollmentRequest
    | RuntimeAccessManagementRequest
)


class RuntimeConnectionHandling:
    """Canonical connection admission, dispatch, and cleanup custody for the runtime host."""

    identity: RuntimeServerHello
    stop: Event
    profiles: RuntimeProfileHandler | None
    _failed: Event
    _slots: BoundedSemaphore
    _channels_guard: RLock
    _channels: dict[int, RuntimeTransportCleanup]

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
        try:
            context = RuntimeConnectionContext(uuid4(), self.identity.boot_id, channel.peer)
            accept_runtime_handshake(channel, identity=self.identity, deadline=time.monotonic() + 5)
            self._serve_connection_requests(channel, context)
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
            _LOGGER.error(
                "runtime connection failed unexpectedly; stopping the runtime error_type=%s",
                type(error).__name__,
                exc_info=error,
            )
            self._failed.set()
            self.stop.set()
            if not isinstance(error, Exception):
                raise
        finally:
            self._finish_connection(channel_owner, context, cleanup_deferred)

    def _serve_connection_requests(self, channel: RuntimeByteChannel, context: RuntimeConnectionContext) -> None:
        """Serve the admitted request sequence until the peer or host closes it."""
        while not self.stop.is_set():
            if not channel.read_ready():
                self.stop.wait(0.05)
                continue
            request = read_document(channel, RuntimeRequest, deadline=time.monotonic() + 5).root
            status = self._dispatch_profile_request(channel, context, request)
            if status is None:
                continue
            if isinstance(status, RuntimeProfileStatus):
                write_profile_status(channel, status, deadline=time.monotonic() + 5)
            else:
                write_document(channel, status, deadline=time.monotonic() + 5)

    def _dispatch_profile_request(
        self, channel: RuntimeByteChannel, context: RuntimeConnectionContext, request: _ProfileConnectionRequest
    ) -> RuntimeProfileStatus | RuntimeSessionsLocked | RuntimeAccessRefusal | None:
        """Dispatch the closed profile request families through their application owner."""
        if self.profiles is None:
            return RuntimeAccessRefusal(
                request_id=request.request_id,
                runtime_boot_id=context.runtime_boot_id,
                connection_id=context.connection_id,
                code=RuntimeRefusalCode.UNAVAILABLE,
            )
        if isinstance(
            request,
            RuntimeAutomationDeny | RuntimeProfileRecoveryPrepare | RuntimeProfileResume | RuntimeSessionInventory,
        ):
            self.profiles.manage_access(context, channel, request)
            return None
        if isinstance(
            request,
            RuntimeEnrollmentPrepare
            | RuntimeEnrollmentSubmit
            | RuntimeEnrollmentInspect
            | RuntimeEnrollmentPoll
            | RuntimeEnrollmentReconcile,
        ):
            self.profiles.enrollment(context, channel, request)
            return None
        if isinstance(
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
            self.profiles.operation(context, channel, request)
            return None
        return self.profiles.handle(context, channel, request)

    def _finish_connection(
        self,
        channel_owner: RuntimeTransportCleanup,
        context: RuntimeConnectionContext | None,
        cleanup_deferred: bool,
    ) -> None:
        """Disconnect, retain incomplete cleanup, and release the slot in the original order."""
        try:
            if self.profiles is not None and context is not None:
                self.profiles.disconnect(context)
        except Exception as error:
            _LOGGER.error(
                "runtime connection disconnect failed; stopping the runtime error_type=%s",
                type(error).__name__,
                exc_info=error,
            )
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
