"""Profile admission and management over one verified runtime transport."""

from __future__ import annotations

from ...application.runtime.access_management import (
    RuntimeAutomationDenied,
    RuntimeAutomationDeny,
    RuntimeProfileRecoveryPrepare,
    RuntimeProfileRecoveryPrepared,
    RuntimeProfileResume,
    RuntimeProfileResumed,
    RuntimeSessionInventory,
    RuntimeSessionInventoryReply,
)
from ...application.runtime.contracts import (
    RuntimeRefusalCode,
    RuntimeRefusalError,
)
from ...application.runtime.operation_access import (
    RuntimeOperationAcknowledged,
    RuntimeOperationSecret,
)
from ...application.runtime.profile_access import (
    RuntimeAccessRefusal,
    RuntimeProfileLogin,
    RuntimeProfileStatus,
    RuntimeSessionRequest,
    RuntimeSessionsLocked,
)
from .runtime_frame_io import (
    write_document,
)
from .runtime_verified_transport import RuntimeVerifiedTransport


class RuntimeProfileTransport(RuntimeVerifiedTransport):
    """Profile admission and management over one verified runtime transport."""

    def login(
        self, request: RuntimeProfileLogin, secret: bytearray, *, deadline: float
    ) -> RuntimeProfileStatus | RuntimeAccessRefusal:
        """Consume credentials only after the exact peer accepts this login request."""
        with self._exchange(deadline=deadline, secret=secret):
            try:
                if self._closed:
                    raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
                delivered = self._deliver_secret(request, secret, deadline=deadline)
                if isinstance(delivered, RuntimeAccessRefusal):
                    return delivered
                ready, reply_document = delivered
                result = reply_document.root
                if (
                    not isinstance(result, (RuntimeProfileStatus, RuntimeAccessRefusal))
                    or result.connection_id != ready.connection_id
                ):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                return result
            except BaseException as error:
                self._close_after_failure(error)
                raise
            finally:
                secret[:] = bytes(len(secret))

    def session(
        self, request: RuntimeSessionRequest, *, deadline: float
    ) -> RuntimeProfileStatus | RuntimeSessionsLocked | RuntimeAccessRefusal:
        """Use one current connection's lease; copied IDs confer no authority."""
        with self._exchange(deadline=deadline):
            if self._closed:
                raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
            try:
                write_document(self._channel, request, deadline=deadline)
                result = self._reply(request.request_id, deadline=deadline).root
                if not isinstance(result, (RuntimeProfileStatus, RuntimeSessionsLocked, RuntimeAccessRefusal)):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                return result
            except BaseException as error:
                self._close_after_failure(error)
                raise

    def recovery_prepare(
        self, request: RuntimeProfileRecoveryPrepare, *, deadline: float
    ) -> RuntimeProfileRecoveryPrepared | RuntimeAccessRefusal:
        """Read exact nonsecret lock state before a separate human proof."""
        with self._exchange(deadline=deadline):
            try:
                if self._closed:
                    raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
                write_document(self._channel, request, deadline=deadline)
                reply = self._reply(request.request_id, deadline=deadline).root
                if not isinstance(reply, RuntimeProfileRecoveryPrepared | RuntimeAccessRefusal):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                if isinstance(reply, RuntimeProfileRecoveryPrepared) and reply.profile_id != request.profile_id:
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                return reply
            except BaseException as error:
                self._close_after_failure(error)
                raise

    def deny_automation(
        self, request: RuntimeAutomationDeny, *, deadline: float
    ) -> RuntimeAutomationDenied | RuntimeAccessRefusal:
        """Return only the durable denial receipt for this exact profile change."""
        with self._exchange(deadline=deadline):
            try:
                if self._closed:
                    raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
                write_document(self._channel, request, deadline=deadline)
                reply = self._reply(request.request_id, deadline=deadline).root
                if not isinstance(reply, RuntimeAutomationDenied | RuntimeAccessRefusal):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                if isinstance(reply, RuntimeAutomationDenied) and (
                    reply.receipt.request_id != request.request_id or reply.receipt.profile_id != request.profile_id
                ):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                return reply
            except BaseException as error:
                self._close_after_failure(error)
                raise

    def resume_profile(
        self, request: RuntimeProfileResume, password: bytearray, *, deadline: float
    ) -> RuntimeProfileResumed | RuntimeAccessRefusal:
        """Send proof only after correlated readiness and verify the selected generation."""
        with self._exchange(deadline=deadline, secret=password):
            try:
                if self._closed:
                    raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
                delivered = self._deliver_secret(request, password, deadline=deadline)
                if isinstance(delivered, RuntimeAccessRefusal):
                    return delivered
                _, reply_document = delivered
                reply = reply_document.root
                if not isinstance(reply, RuntimeProfileResumed | RuntimeAccessRefusal):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                if isinstance(reply, RuntimeProfileResumed) and (
                    reply.receipt.request_id != request.request_id
                    or reply.receipt.profile_id != request.profile_id
                    or reply.receipt.lock_generation != request.lock_generation
                    or not reply.receipt.reactivated_grants <= request.grants
                ):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                return reply
            except BaseException as error:
                self._close_after_failure(error)
                raise
            finally:
                password[:] = bytes(len(password))

    def session_inventory(
        self, request: RuntimeSessionInventory, *, deadline: float
    ) -> RuntimeSessionInventoryReply | RuntimeAccessRefusal:
        """Read an allowlisted inventory for exactly this profile."""
        with self._exchange(deadline=deadline):
            try:
                if self._closed:
                    raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
                write_document(self._channel, request, deadline=deadline)
                reply = self._reply(request.request_id, deadline=deadline).root
                if not isinstance(reply, RuntimeSessionInventoryReply | RuntimeAccessRefusal):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                if isinstance(reply, RuntimeSessionInventoryReply) and any(
                    session.profile_id != request.profile_id for session in reply.sessions
                ):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                return reply
            except BaseException as error:
                self._close_after_failure(error)
                raise

    def operation_secret(
        self, request: RuntimeOperationSecret, secret: bytearray, *, deadline: float
    ) -> RuntimeOperationAcknowledged | RuntimeAccessRefusal:
        """Deliver bytes only after current authority accepts this exact requirement."""
        with self._exchange(deadline=deadline, secret=secret):
            try:
                if self._closed:
                    raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
                delivered = self._deliver_secret(request, secret, deadline=deadline)
                if isinstance(delivered, RuntimeAccessRefusal):
                    return delivered
                _, reply_document = delivered
                result = reply_document.root
                if not isinstance(result, RuntimeOperationAcknowledged | RuntimeAccessRefusal):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                if isinstance(result, RuntimeOperationAcknowledged) and (
                    result.operation_id != request.requirement.identity.operation_id
                ):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                return result
            except BaseException as error:
                self._close_after_failure(error)
                raise
            finally:
                secret[:] = bytes(len(secret))
