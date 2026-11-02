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
from ..contracts.contracts import RefusalCode, RefusalError
from ..contracts.operation_access import OperationAcknowledged, OperationSecret
from ..contracts.profile_access import (
    AccessRefusal,
    ProfileDisclosurePage,
    ProfileDisclosurePageRequest,
    ProfileStatus,
    SessionRequest,
    SessionsLocked,
)
from ..contracts.sign_in import HumanSignedOut
from .frame_io import write_document
from .profile_service_transport import ProfileServiceTransport


class ProfileOperationsTransport(ProfileServiceTransport):
    """Exchange profile-scoped operations on one verified connection."""

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
        return self._request_reply(
            request,
            request.request_id,
            (ProfileRecoveryPrepared, AccessRefusal),
            deadline=deadline,
            admits=lambda reply: (
                not isinstance(reply, ProfileRecoveryPrepared) or reply.profile_id == request.profile_id
            ),
        )

    def deny_automation(self, request: AutomationDeny, *, deadline: float) -> AutomationDenied | AccessRefusal:
        """Return only the durable denial receipt for this exact profile change."""
        return self._request_reply(
            request,
            request.request_id,
            (AutomationDenied, AccessRefusal),
            deadline=deadline,
            admits=lambda reply: (
                not isinstance(reply, AutomationDenied)
                or (reply.receipt.request_id == request.request_id and reply.receipt.profile_id == request.profile_id)
            ),
        )

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
        return self._request_reply(
            request,
            request.request_id,
            (SessionInventoryReply, AccessRefusal),
            deadline=deadline,
            admits=lambda reply: (
                not isinstance(reply, SessionInventoryReply)
                or all(session.profile_id == request.profile_id for session in reply.sessions)
            ),
        )

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
