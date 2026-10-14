"""Profile admission and management over one verified runtime transport."""

from __future__ import annotations

from ..contracts.access_management import (
    AutomationDenied,
    AutomationDeny,
    ProfileRecoveryPrepare,
    ProfileRecoveryPrepared,
    ProfileResume,
    ProfileResumed,
    SessionInventory,
    SessionInventoryReply,
)
from ..contracts.attendance import (
    AttendanceAsk,
    AttendanceDecide,
    AttendanceDecided,
    AttendanceInventory,
    AttendancePending,
)
from ..contracts.bootstrap import (
    PasswordReset,
    PasswordResetCompleted,
    PasswordResetPrepare,
    PasswordResetPrepared,
    PasswordResetRefused,
)
from ..contracts.bootstrap_delete import (
    ProfileDelete,
    ProfileDeleted,
    ProfileDeletePrepare,
    ProfileDeletePrepared,
    ProfileDeleteRefused,
)
from ..contracts.contracts import RefusalCode, RefusalError
from ..contracts.extension_records import ExtensionRecordReply, ExtensionRecordRequest
from ..contracts.operation_access import OperationAcknowledged, OperationSecret
from ..contracts.profile_access import (
    AccessRefusal,
    ProfileDisclosurePage,
    ProfileDisclosurePageRequest,
    ProfileLogin,
    ProfileStatus,
    SecretReady,
    SessionRequest,
    SessionsLocked,
)
from ..contracts.service_access import ServiceAdmission, ServiceConnect, ServiceConnected
from ..contracts.sign_in import HumanSignedOut, SignInStatusReply, SignInStatusRequest
from .frame_io import read_secret, write_document, write_secret
from .verified_transport import VerifiedTransport


class ProfileTransport(VerifiedTransport):
    """Profile admission and management over one verified runtime transport."""

    def delete_profile(
        self,
        request: ProfileDeletePrepare | ProfileDelete,
        *,
        deadline: float,
    ) -> ProfileDeletePrepared | ProfileDeleted | ProfileDeleteRefused | AccessRefusal:
        """Echo only existing journal confirmation; never send authentication secrets."""
        with self._exchange(deadline=deadline):
            try:
                if self._closed:
                    raise RefusalError(RefusalCode.CONNECTION_CLOSED)
                write_document(self._channel, request, deadline=deadline)
                reply = self._reply(request.request_id, deadline=deadline).root
                if isinstance(reply, AccessRefusal):
                    return reply
                if not isinstance(reply, ProfileDeletePrepared | ProfileDeleted | ProfileDeleteRefused):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                if reply.profile_id != request.profile_id:
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                if isinstance(reply, ProfileDeletePrepared) and (
                    not isinstance(request, ProfileDeletePrepare) or reply.confirmation.profile_id != request.profile_id
                ):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                if isinstance(reply, ProfileDeleted) and (
                    not isinstance(request, ProfileDelete)
                    or reply.receipt.profile_id != request.profile_id
                    or reply.receipt.transaction_id != request.confirmation.transaction_id
                ):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                return reply
            except BaseException as error:
                self._close_after_failure(error)
                raise

    def password_reset_prepare(
        self,
        request: PasswordResetPrepare,
        *,
        deadline: float,
    ) -> PasswordResetPrepared | AccessRefusal:
        """Capture a predecessor on this exact verified connection."""
        with self._exchange(deadline=deadline):
            try:
                if self._closed:
                    raise RefusalError(RefusalCode.CONNECTION_CLOSED)
                write_document(self._channel, request, deadline=deadline)
                reply = self._reply(request.request_id, deadline=deadline).root
                if not isinstance(reply, PasswordResetPrepared | AccessRefusal):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                if isinstance(reply, PasswordResetPrepared) and reply.profile_id != request.profile_id:
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                return reply
            except BaseException as error:
                self._close_after_failure(error)
                raise

    def password_reset(
        self,
        request: PasswordReset,
        secret: bytearray,
        *,
        deadline: float,
    ) -> PasswordResetCompleted | PasswordResetRefused | AccessRefusal:
        """Consume reset credentials only after correlated secret readiness."""
        with self._exchange(deadline=deadline, secret=secret):
            try:
                if self._closed:
                    raise RefusalError(RefusalCode.CONNECTION_CLOSED)
                delivered = self._deliver_secret(request, secret, deadline=deadline)
                if isinstance(delivered, AccessRefusal):
                    return delivered
                _, document = delivered
                reply = document.root
                if not isinstance(reply, PasswordResetCompleted | PasswordResetRefused | AccessRefusal):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                if (
                    isinstance(reply, PasswordResetCompleted | PasswordResetRefused)
                    and reply.profile_id != request.profile_id
                ):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                if isinstance(reply, PasswordResetCompleted) and reply.outcome.profile_id != str(request.profile_id):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                return reply
            except BaseException as error:
                self._close_after_failure(error)
                raise
            finally:
                secret[:] = bytes(len(secret))

    def sign_in_status(self, request: SignInStatusRequest, *, deadline: float) -> SignInStatusReply | AccessRefusal:
        """Observe presence through the same correlated, credential-free exchange."""
        with self._exchange(deadline=deadline):
            try:
                if self._closed:
                    raise RefusalError(RefusalCode.CONNECTION_CLOSED)
                write_document(self._channel, request, deadline=deadline)
                result = self._reply(request.request_id, deadline=deadline).root
                if not isinstance(result, SignInStatusReply | AccessRefusal):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                if isinstance(result, SignInStatusReply) and result.profile_id != request.profile_id:
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                return result
            except BaseException as error:
                self._close_after_failure(error)
                raise

    def login(self, request: ProfileLogin, secret: bytearray, *, deadline: float) -> ProfileStatus | AccessRefusal:
        """Consume credentials only after the exact peer accepts this login request."""
        with self._exchange(deadline=deadline, secret=secret):
            try:
                if self._closed:
                    raise RefusalError(RefusalCode.CONNECTION_CLOSED)
                delivered = self._deliver_secret(request, secret, deadline=deadline)
                if isinstance(delivered, AccessRefusal):
                    return delivered
                ready, reply_document = delivered
                result = reply_document.root
                if (
                    not isinstance(result, (ProfileStatus, AccessRefusal))
                    or result.connection_id != ready.connection_id
                ):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                return result
            except BaseException as error:
                self._close_after_failure(error)
                raise
            finally:
                secret[:] = bytes(len(secret))

    def session(
        self, request: SessionRequest, *, deadline: float
    ) -> ProfileStatus | SessionsLocked | HumanSignedOut | AccessRefusal:
        """Use one current connection's lease; copied IDs confer no authority."""
        with self._exchange(deadline=deadline):
            if self._closed:
                raise RefusalError(RefusalCode.CONNECTION_CLOSED)
            try:
                write_document(self._channel, request, deadline=deadline)
                result = self._reply(request.request_id, deadline=deadline).root
                if not isinstance(result, (ProfileStatus, SessionsLocked, HumanSignedOut, AccessRefusal)):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                return result
            except BaseException as error:
                self._close_after_failure(error)
                raise

    def disclosure_page(
        self, request: ProfileDisclosurePageRequest, *, deadline: float
    ) -> ProfileDisclosurePage | AccessRefusal:
        """Read one page of the disclosures this connection's own status counts."""
        with self._exchange(deadline=deadline):
            if self._closed:
                raise RefusalError(RefusalCode.CONNECTION_CLOSED)
            try:
                write_document(self._channel, request, deadline=deadline)
                result = self._reply(request.request_id, deadline=deadline).root
                if not isinstance(result, (ProfileDisclosurePage, AccessRefusal)):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                return result
            except BaseException as error:
                self._close_after_failure(error)
                raise

    def attendance(
        self, request: AttendanceAsk | AttendanceDecide, *, deadline: float
    ) -> AttendancePending | AttendanceInventory | AttendanceDecided | ProfileStatus | AccessRefusal:
        """Ask to be attended, observe that ask, or list and decide asks as the person."""
        with self._exchange(deadline=deadline):
            if self._closed:
                raise RefusalError(RefusalCode.CONNECTION_CLOSED)
            try:
                write_document(self._channel, request, deadline=deadline)
                result = self._reply(request.request_id, deadline=deadline).root
                if not isinstance(
                    result,
                    (
                        AttendancePending,
                        AttendanceInventory,
                        AttendanceDecided,
                        ProfileStatus,
                        AccessRefusal,
                    ),
                ):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                return result
            except BaseException as error:
                self._close_after_failure(error)
                raise

    def recovery_prepare(
        self, request: ProfileRecoveryPrepare, *, deadline: float
    ) -> ProfileRecoveryPrepared | AccessRefusal:
        """Read exact nonsecret lock state before a separate human proof."""
        with self._exchange(deadline=deadline):
            try:
                if self._closed:
                    raise RefusalError(RefusalCode.CONNECTION_CLOSED)
                write_document(self._channel, request, deadline=deadline)
                reply = self._reply(request.request_id, deadline=deadline).root
                if not isinstance(reply, ProfileRecoveryPrepared | AccessRefusal):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                if isinstance(reply, ProfileRecoveryPrepared) and reply.profile_id != request.profile_id:
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                return reply
            except BaseException as error:
                self._close_after_failure(error)
                raise

    def deny_automation(self, request: AutomationDeny, *, deadline: float) -> AutomationDenied | AccessRefusal:
        """Return only the durable denial receipt for this exact profile change."""
        with self._exchange(deadline=deadline):
            try:
                if self._closed:
                    raise RefusalError(RefusalCode.CONNECTION_CLOSED)
                write_document(self._channel, request, deadline=deadline)
                reply = self._reply(request.request_id, deadline=deadline).root
                if not isinstance(reply, AutomationDenied | AccessRefusal):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                if isinstance(reply, AutomationDenied) and (
                    reply.receipt.request_id != request.request_id or reply.receipt.profile_id != request.profile_id
                ):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                return reply
            except BaseException as error:
                self._close_after_failure(error)
                raise

    def resume_profile(
        self, request: ProfileResume, password: bytearray, *, deadline: float
    ) -> ProfileResumed | AccessRefusal:
        """Send proof only after correlated readiness and verify the selected generation."""
        with self._exchange(deadline=deadline, secret=password):
            try:
                if self._closed:
                    raise RefusalError(RefusalCode.CONNECTION_CLOSED)
                delivered = self._deliver_secret(request, password, deadline=deadline)
                if isinstance(delivered, AccessRefusal):
                    return delivered
                _, reply_document = delivered
                reply = reply_document.root
                if not isinstance(reply, ProfileResumed | AccessRefusal):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                if isinstance(reply, ProfileResumed) and (
                    reply.receipt.request_id != request.request_id
                    or reply.receipt.profile_id != request.profile_id
                    or reply.receipt.lock_generation != request.lock_generation
                    or not reply.receipt.reactivated_grants <= request.grants
                ):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                return reply
            except BaseException as error:
                self._close_after_failure(error)
                raise
            finally:
                password[:] = bytes(len(password))

    def session_inventory(self, request: SessionInventory, *, deadline: float) -> SessionInventoryReply | AccessRefusal:
        """Read an allowlisted inventory for exactly this profile."""
        with self._exchange(deadline=deadline):
            try:
                if self._closed:
                    raise RefusalError(RefusalCode.CONNECTION_CLOSED)
                write_document(self._channel, request, deadline=deadline)
                reply = self._reply(request.request_id, deadline=deadline).root
                if not isinstance(reply, SessionInventoryReply | AccessRefusal):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                if isinstance(reply, SessionInventoryReply) and any(
                    session.profile_id != request.profile_id for session in reply.sessions
                ):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                return reply
            except BaseException as error:
                self._close_after_failure(error)
                raise

    def operation_secret(
        self, request: OperationSecret, secret: bytearray, *, deadline: float
    ) -> OperationAcknowledged | AccessRefusal:
        """Deliver bytes only after current authority accepts this exact requirement."""
        with self._exchange(deadline=deadline, secret=secret):
            try:
                if self._closed:
                    raise RefusalError(RefusalCode.CONNECTION_CLOSED)
                delivered = self._deliver_secret(request, secret, deadline=deadline)
                if isinstance(delivered, AccessRefusal):
                    return delivered
                _, reply_document = delivered
                result = reply_document.root
                if not isinstance(result, OperationAcknowledged | AccessRefusal):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                if isinstance(result, OperationAcknowledged) and (
                    result.operation_id != request.requirement.identity.operation_id
                ):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                return result
            except BaseException as error:
                self._close_after_failure(error)
                raise
            finally:
                secret[:] = bytes(len(secret))

    def service_access(
        self, request: ServiceConnect | ServiceAdmission, *, deadline: float
    ) -> ServiceConnected | AccessRefusal:
        """Submit a typed service-admission request over this verified connection."""
        with self._exchange(deadline=deadline):
            try:
                write_document(self._channel, request, deadline=deadline)
                reply = self._reply(request.request_id, deadline=deadline).root
                if not isinstance(reply, ServiceConnected | AccessRefusal):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                return reply
            except BaseException as error:
                self._close_after_failure(error)
                raise

    def extension_record(
        self, request: ExtensionRecordRequest, payload: bytearray | None = None, *, deadline: float
    ) -> tuple[ExtensionRecordReply | AccessRefusal, bytearray]:
        """Exchange one lease-bound extension-record request and payload."""
        material = bytearray()
        with self._exchange(deadline=deadline):
            try:
                write_document(self._channel, request, deadline=deadline)
                reply = self._reply(request.request_id, deadline=deadline).root
                if isinstance(reply, SecretReady):
                    if payload is None or len(payload) != request.byte_count:
                        raise RefusalError(RefusalCode.INVALID_FRAME)
                    write_secret(self._channel, payload, deadline=deadline)
                    reply = self._reply(request.request_id, deadline=deadline).root
                if not isinstance(reply, ExtensionRecordReply | AccessRefusal):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                if isinstance(reply, ExtensionRecordReply) and reply.byte_count:
                    with read_secret(self._channel, deadline=deadline) as incoming:
                        if len(incoming) != reply.byte_count:
                            raise RefusalError(RefusalCode.INVALID_FRAME)
                        material.extend(incoming)
                return reply, material
            except BaseException as error:
                material[:] = bytes(len(material))
                self._close_after_failure(error)
                raise
