"""Bounded request admission and retained connection cleanup for the runtime host."""

from __future__ import annotations

import logging
import time
from threading import BoundedSemaphore, Event, RLock
from typing import cast
from uuid import uuid4

from cadrumo.core.diagnostic_log import diagnostic_error_fields, diagnostic_event
from cadrumo.core.logging import get_logger
from cadrumo_client.contracts.access_management import (
    AccessManagementRequest,
    AutomationDeny,
    ProfileRecoveryPrepare,
    ProfileResume,
    SessionInventory,
)
from cadrumo_client.contracts.attendance import (
    AttendanceAsk,
    AttendanceDecide,
    AttendanceDecided,
    AttendanceInventory,
    AttendancePending,
)
from cadrumo_client.contracts.bootstrap import PasswordReset, PasswordResetPrepare
from cadrumo_client.contracts.bootstrap_delete import ProfileDelete, ProfileDeletePrepare
from cadrumo_client.contracts.contracts import ByteChannel, RefusalCode, RefusalError, ServerHello
from cadrumo_client.contracts.enrollment_access import (
    EnrollmentInspect,
    EnrollmentPoll,
    EnrollmentPrepare,
    EnrollmentReconcile,
    EnrollmentRequest,
    EnrollmentSubmit,
)
from cadrumo_client.contracts.extension_records import ExtensionRecordRequest
from cadrumo_client.contracts.installation_requests import InstallationActRequest
from cadrumo_client.contracts.model_runs import ModelRunCompleteRequest, ModelRunFetchRequest
from cadrumo_client.contracts.operation_access import (
    OperationContract,
    OperationControl,
    OperationFinancialInput,
    OperationManage,
    OperationObserve,
    OperationRequest,
    OperationResult,
    OperationResultPage,
    OperationReview,
    OperationSecret,
    OperationSubmit,
    OperationSubmitPayload,
)
from cadrumo_client.contracts.profile_access import (
    AccessRefusal,
    ProfileDisclosurePage,
    ProfileDisclosurePageRequest,
    ProfileLogin,
    ProfileLoginPending,
    ProfileLoginStatusQuery,
    ProfileStatus,
    Request,
    SessionRequest,
    SessionsLocked,
)
from cadrumo_client.contracts.profile_selection import (
    ActiveProfileReply,
    ActiveProfileRequest,
    LoginTargetReply,
    LoginTargetRequest,
)
from cadrumo_client.contracts.service_access import ServiceAdmission, ServiceAdmissionStatusQuery, ServiceConnect
from cadrumo_client.contracts.sign_in import HumanSignedOut, SignInStatusReply, SignInStatusRequest
from cadrumo_client.contracts.transport import ConnectionContext
from cadrumo_client.contracts.view_stream import ViewAttachRequest, ViewConnect
from cadrumo_client.transport.frame_io import read_document, write_document, write_profile_status, write_session_event
from cadrumo_client.transport.native_wake import NativeWake
from cadrumo_client.transport.transport_cleanup import TransportCleanup, close_transport_after_failure
from cadrumo_runtime.adapters.connection_handshake import accept_connection_handshake
from cadrumo_runtime.contracts.profile_host import ProfileHandler

_LOGGER = get_logger(__name__)

type _ProfileConnectionRequest = (
    ProfileLogin
    | ProfileLoginStatusQuery
    | ProfileDeletePrepare
    | ProfileDelete
    | PasswordResetPrepare
    | PasswordReset
    | SignInStatusRequest
    | ActiveProfileRequest
    | LoginTargetRequest
    | SessionRequest
    | ProfileDisclosurePageRequest
    | AttendanceAsk
    | AttendanceDecide
    | OperationRequest
    | EnrollmentRequest
    | AccessManagementRequest
    | InstallationActRequest
    | ServiceConnect
    | ServiceAdmission
    | ServiceAdmissionStatusQuery
    | ExtensionRecordRequest
    | ModelRunFetchRequest
    | ModelRunCompleteRequest
    | ViewAttachRequest
)


class RuntimeConnectionHandling:
    """Canonical connection admission, dispatch, and cleanup custody for the runtime host."""

    identity: ServerHello
    stop: Event
    # Set once ``stop`` is, so a connection blocked between requests sees it.
    _stopping: NativeWake
    profiles: ProfileHandler | None
    _failed: Event
    _slots: BoundedSemaphore
    _channels_guard: RLock
    _channels: dict[int, TransportCleanup]

    def _channel_owner(self, channel: ByteChannel) -> TransportCleanup:
        with self._channels_guard:
            owner = self._channels.get(id(channel))
            if owner is None:
                owner = TransportCleanup(channel)
                self._channels[id(channel)] = owner
            return owner

    def _retain_channel_cleanup(
        self,
        error: BaseException,
        *,
        channel: ByteChannel | None = None,
        require_registered: bool = False,
    ) -> TransportCleanup | None:
        owner = error.__dict__.get("_transport_cleanup")
        if isinstance(owner, TransportCleanup):
            if channel is not None and owner.resource is not channel:
                return None
            with self._channels_guard:
                if require_registered and id(owner.resource) not in self._channels:
                    return None
                self._channels[id(owner.resource)] = owner
            self._forget_closed_channel(owner)
            return owner
        return None

    def _forget_closed_channel(self, owner: TransportCleanup) -> None:
        if owner.released:
            with self._channels_guard:
                if self._channels.get(id(owner.resource)) is owner:
                    self._channels.pop(id(owner.resource))

    def _close_owned_channel(self, owner: TransportCleanup, *, deadline: float | None = None) -> None:
        try:
            owner.close_now(deadline=deadline)
        finally:
            self._forget_closed_channel(owner)

    def _connection(self, channel: ByteChannel) -> None:
        channel_owner = self._channel_owner(channel)
        context: ConnectionContext | None = None
        cleanup_deferred = False
        try:
            context = ConnectionContext(uuid4(), self.identity.boot_id, channel.peer)
            hello = accept_connection_handshake(channel, identity=self.identity, deadline=time.monotonic() + 5)
            context = ConnectionContext(
                context.connection_id,
                context.runtime_boot_id,
                context.peer,
                lifecycle_notices=hello.lifecycle_notices == "v1",
            )
            queued = NativeWake()
            if self.profiles is not None:
                self.profiles.connect_events(context, channel, queued=queued)
            self._serve_connection_requests(channel, context, queued)
        except RefusalError as error:
            retained = self._retain_channel_cleanup(error, channel=channel)
            if retained is not None:
                channel_owner = retained
                cleanup_deferred = not retained.released
            # No peer input or secret bytes become a diagnostic. Incompatible,
            # malformed, disconnected and timed-out connections end locally,
            # recording only the refusal code and where it was raised.
            diagnostic_event(
                _LOGGER,
                "runtime_connection_closed"
                if error.reason is RefusalCode.CONNECTION_CLOSED
                else "runtime_connection_refused",
                fields={"reason": error.reason.value, "refusal_check": error.check, **diagnostic_error_fields(error)},
                # A peer that closes its connection is the ordinary end of every command.
                level=logging.DEBUG if error.reason is RefusalCode.CONNECTION_CLOSED else logging.INFO,
            )
            return
        except BaseException as error:
            if not isinstance(error, Exception):
                close_transport_after_failure(channel, error)
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

    def _flush_connection_events(self, channel: ByteChannel, context: ConnectionContext) -> None:
        """Write queued events and acknowledge each exact successful frame."""
        if self.profiles is not None:
            for event in self.profiles.take_events(context):
                write_session_event(channel, event, deadline=time.monotonic() + 5)
                self.profiles.event_flushed(context, event)

    def _wait_connection_input(self, channel: ByteChannel, queued: NativeWake) -> bool | None:
        """Treat an EOF between requests as a completed lifetime."""
        try:
            return channel.wait_readable(queued, self._stopping)
        except RefusalError as error:
            if error.reason is not RefusalCode.CONNECTION_CLOSED:
                raise
            diagnostic_event(_LOGGER, "runtime_connection_closed", level=logging.DEBUG)
            return None

    def _serve_connection_requests(self, channel: ByteChannel, context: ConnectionContext, queued: NativeWake) -> None:
        """Serve the admitted request sequence until the peer or host closes it.

        Between requests the thread blocks on the channel, the connection's
        queued events and the runtime stop together; nothing wakes it on a timer.
        """
        first = True
        while not self.stop.is_set():
            # Cleared before taking, so an event queued meanwhile still ends the wait.
            queued.clear()
            self._flush_connection_events(channel, context)
            ready = self._wait_connection_input(channel, queued)
            if ready is None:
                return
            if not ready:
                continue
            request = read_document(channel, Request, deadline=time.monotonic() + 5).root
            if isinstance(request, ViewConnect):
                # Only a fresh connection becomes a view connection, and it carries nothing else after.
                if not first or self.profiles is None:
                    raise RefusalError(RefusalCode.INVALID_FRAME, check="view_connect_not_first")
                self.profiles.view_connect(context, channel, request)
                return
            first = False
            status = self._dispatch_profile_request(channel, context, request)
            if self.profiles is not None:
                # What the request changed may move a lease's deadline or end one.
                self.profiles.lifecycle_changed()
            if status is None:
                continue
            if isinstance(status, ProfileStatus):
                write_profile_status(channel, status, deadline=time.monotonic() + 5)
            else:
                write_document(channel, status, deadline=time.monotonic() + 5)

    def _dispatch_profile_request(
        self, channel: ByteChannel, context: ConnectionContext, request: _ProfileConnectionRequest
    ) -> (
        ProfileStatus
        | ProfileLoginPending
        | ProfileDisclosurePage
        | SessionsLocked
        | SignInStatusReply
        | ActiveProfileReply
        | LoginTargetReply
        | HumanSignedOut
        | AttendancePending
        | AttendanceInventory
        | AttendanceDecided
        | AccessRefusal
        | None
    ):
        """Dispatch the closed profile request families through their application owner."""
        if self.profiles is None:
            return AccessRefusal(
                request_id=request.request_id,
                runtime_boot_id=context.runtime_boot_id,
                connection_id=context.connection_id,
                code=RefusalCode.UNAVAILABLE,
            )
        if isinstance(request, ServiceConnect | ServiceAdmission | ServiceAdmissionStatusQuery):
            return self.profiles.service(context, channel, request)
        if isinstance(request, ProfileDeletePrepare | ProfileDelete):
            self.profiles.bootstrap_delete(context, channel, request)
            return None
        if self._dispatch_owned_request(channel, context, request):
            return None
        if isinstance(
            request,
            ProfileLogin
            | ProfileLoginStatusQuery
            | SessionRequest
            | ProfileDisclosurePageRequest
            | SignInStatusRequest
            | ActiveProfileRequest
            | LoginTargetRequest
            | AttendanceAsk
            | AttendanceDecide,
        ):
            return self.profiles.handle(context, channel, request)
        self.profiles.installation(context, channel, cast("InstallationActRequest", request))
        return None

    def _dispatch_owned_request(
        self, channel: ByteChannel, context: ConnectionContext, request: _ProfileConnectionRequest
    ) -> bool:
        """Dispatch request families that own their own replies."""
        if self.profiles is None:
            return False
        if isinstance(request, ViewAttachRequest):
            self.profiles.view_attach(context, channel, request)
            return True
        if isinstance(request, ExtensionRecordRequest):
            self.profiles.extension_record(context, channel, request)
            return True
        if isinstance(request, ModelRunFetchRequest):
            self.profiles.model_run_fetch(context, channel, request)
            return True
        if isinstance(request, ModelRunCompleteRequest):
            self.profiles.model_run_complete(context, channel, request)
            return True
        if isinstance(request, PasswordResetPrepare | PasswordReset):
            self.profiles.bootstrap(context, channel, request)
            return True
        if isinstance(
            request,
            AutomationDeny | ProfileRecoveryPrepare | ProfileResume | SessionInventory,
        ):
            self.profiles.manage_access(context, channel, request)
            return True
        if isinstance(
            request,
            EnrollmentPrepare | EnrollmentSubmit | EnrollmentInspect | EnrollmentPoll | EnrollmentReconcile,
        ):
            self.profiles.enrollment(context, channel, request)
            return True
        if isinstance(
            request,
            OperationSubmit
            | OperationSubmitPayload
            | OperationControl
            | OperationObserve
            | OperationContract
            | OperationResult
            | OperationResultPage
            | OperationReview
            | OperationManage
            | OperationFinancialInput
            | OperationSecret,
        ):
            self.profiles.operation(context, channel, request)
            return True
        return False

    def _finish_connection(
        self,
        channel_owner: TransportCleanup,
        context: ConnectionContext | None,
        cleanup_deferred: bool,
    ) -> None:
        """Disconnect, retain incomplete cleanup, and release the slot in the original order."""
        try:
            if self.profiles is not None and context is not None:
                self.profiles.disconnect(context)
                self.profiles.lifecycle_changed()
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
