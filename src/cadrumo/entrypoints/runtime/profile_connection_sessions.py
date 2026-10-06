"""Runtime session behavior for profile connections."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import SecretBytes

from ...adapters.local_runtime.runtime_frame_io import read_secret, write_document
from ...adapters.persistence.storage.custody.acceleration_receipt import ReceiptDeletion
from ...application.runtime.contracts import (
    RuntimeByteChannel,
    RuntimeRefusalCode,
    RuntimeRefusalError,
)
from ...application.runtime.profile_access import (
    RuntimeAccessRefusal,
    RuntimeProfileLogin,
    RuntimeProfileStatus,
    RuntimeSecretReady,
    RuntimeSessionRequest,
    RuntimeSessionsLocked,
)
from ...application.runtime.sign_in import RuntimeHumanSignedOut, RuntimeSignInStatusReply, RuntimeSignInStatusRequest
from ...application.runtime.transport import RuntimeConnectionContext
from ...application.user_profile.access_contracts import (
    AccessDenialCode,
    AccessDenied,
    AccessScope,
    AccessSession,
    Availability,
)
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...application.user_profile.automation_custody_port import (
    AutomationCustodyError,
)
from .profile_host import ProfileConnection, RuntimeProfileHost
from .sign_in_status import observe_sign_in

if TYPE_CHECKING:
    from .profile_connections import RuntimeProfileConnections


@dataclass(frozen=True, slots=True)
class _ApiKeyLogin:
    credential: SecretBytes
    scope: AccessScope


class ProfileConnectionSessionMixin:
    """Own the session behavior of the profile connection service."""

    def _status(
        self: RuntimeProfileConnections,
        connection: ProfileConnection,
        host: RuntimeProfileHost,
        request_id: UUID,
        session_id: UUID,
    ) -> RuntimeProfileStatus | AccessDenied:
        status = host.authority.status(
            connection_id=connection.context.connection_id,
            session_id=session_id,
            published_authority=Availability.UNAVAILABLE,
            provider=Availability.NEEDS_USER,
        )
        if isinstance(status, AccessDenied):
            return status
        if status.denial is not None:
            connection.session_id = None
        return RuntimeProfileStatus(
            request_id=request_id,
            runtime_boot_id=self.boot,
            connection_id=connection.context.connection_id,
            status=status,
        )

    def _login(
        self: RuntimeProfileConnections,
        context: RuntimeConnectionContext,
        channel: RuntimeByteChannel,
        request: RuntimeProfileLogin,
    ) -> RuntimeProfileStatus | AccessDenied:
        connection, host = self._prepare(context, channel, request)
        write_document(
            channel,
            RuntimeSecretReady(
                request_id=request.request_id, runtime_boot_id=self.boot, connection_id=context.connection_id
            ),
            deadline=time.monotonic() + 5,
        )
        # Slow/unresponsive secret senders do not hold any profile admission guard.
        with read_secret(channel, deadline=time.monotonic() + 10) as secret:
            if request.method in {"password", "receipt"}:
                admitted = self._admit_human_login(connection, host, context, secret)
            else:
                api_login = self._prepare_api_key_login(connection, host, secret, request)
                if isinstance(api_login, AccessDenied):
                    return api_login
                admitted = host.authority.admit_api_key(
                    connection_id=context.connection_id,
                    target=host.store.binding,
                    credential=api_login.credential,
                    scope=api_login.scope,
                )
        return self._finish_login(connection, host, context, request, admitted)

    def _admit_human_login(
        self: RuntimeProfileConnections,
        connection: ProfileConnection,
        host: RuntimeProfileHost,
        context: RuntimeConnectionContext,
        secret: bytearray,
    ) -> AccessSession | AccessDenied:
        with host.guard:
            if not self._admitting():
                raise RuntimeRefusalError(RuntimeRefusalCode.DRAINING)
            connection.human_secret = secret
        try:
            return host.authority.admit_human(connection_id=context.connection_id)
        finally:
            with host.guard:
                connection.human_secret = None

    def _prepare_api_key_login(
        self: RuntimeProfileConnections,
        connection: ProfileConnection,
        host: RuntimeProfileHost,
        secret: bytearray,
        request: RuntimeProfileLogin,
    ) -> _ApiKeyLogin | AccessDenied:
        with host.guard:
            if not self._admitting():
                raise RuntimeRefusalError(RuntimeRefusalCode.DRAINING)
            credential = SecretBytes(bytes(secret))
            key_id, _ = host.issuer.verifier(credential)
            snapshot = host.store.snapshot()
            key = next((item for item in snapshot.keys if item.key_id == key_id), None)
            grant = next((item for item in snapshot.grants if key is not None and item.grant_id == key.grant_id), None)
            if grant is None:
                return AccessDenied(code=AccessDenialCode.AUTHENTICATION_REQUIRED)
            # This is routing from protected state, not proof. No lease is
            # published until the existing authority verifies and unwraps it.
            connection.client_id = grant.client_id
            return _ApiKeyLogin(credential, request.scope or grant.scope)

    def _finish_login(
        self: RuntimeProfileConnections,
        connection: ProfileConnection,
        host: RuntimeProfileHost,
        context: RuntimeConnectionContext,
        request: RuntimeProfileLogin,
        admitted: AccessSession | AccessDenied,
    ) -> RuntimeProfileStatus | AccessDenied:
        with host.guard:
            if isinstance(admitted, AccessDenied):
                return admitted
            if not self._admitting():
                host.authority.disconnect(context.connection_id)
                raise RuntimeRefusalError(RuntimeRefusalCode.DRAINING)
            connection.session_id = admitted.session_id
            receipt = host.owner.take_human_login_receipt(admitted.session_id)
            result = self._status(connection, host, request.request_id, admitted.session_id)
            if isinstance(result, RuntimeProfileStatus):
                return result.model_copy(update={"human_login": receipt})
            return result

    def _session(
        self: RuntimeProfileConnections, context: RuntimeConnectionContext, request: RuntimeSessionRequest
    ) -> RuntimeProfileStatus | RuntimeSessionsLocked | RuntimeHumanSignedOut | AccessDenied:
        connection = self._connected(context.connection_id)
        if connection.context != context or connection.profile_id != request.profile_id:
            return AccessDenied(code=AccessDenialCode.PROFILE_MISMATCH)
        if connection.session_id != request.session_id:
            return AccessDenied(code=AccessDenialCode.CONNECTION_MISMATCH)
        with self._guard:
            host = self._profiles[connection.profile_id]
        return self._handle_session_action(connection, host, context, request)

    def _handle_session_action(
        self: RuntimeProfileConnections,
        connection: ProfileConnection,
        host: RuntimeProfileHost,
        context: RuntimeConnectionContext,
        request: RuntimeSessionRequest,
    ) -> RuntimeProfileStatus | RuntimeSessionsLocked | RuntimeHumanSignedOut | AccessDenied:
        with host.guard:
            if not self._admitting():
                raise RuntimeRefusalError(RuntimeRefusalCode.DRAINING)
            if request.action == "session_lock":
                return self._lock_session(connection, host, context, request)
            if request.target_session_id is not None:
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            if request.action == "human_sign_out":
                return self._human_sign_out(host, context, request)
            if request.action == "session_refresh":
                return self._refresh_session(connection, host, context, request)
            return self._status(connection, host, request.request_id, request.session_id)

    def _human_sign_out(
        self: RuntimeProfileConnections,
        host: RuntimeProfileHost,
        context: RuntimeConnectionContext,
        request: RuntimeSessionRequest,
    ) -> RuntimeHumanSignedOut:
        host.authority.human_administration_facts(connection_id=context.connection_id, session_id=request.session_id)
        try:
            automation_enabled = host.store.enrollment_state().automation_enabled
        except AutomationCustodyError:
            automation_enabled = None
        deletion, retired = host.revoke_human_sign_in()
        self._retired(retired)
        return RuntimeHumanSignedOut(
            request_id=request.request_id,
            runtime_boot_id=self.boot,
            connection_id=context.connection_id,
            profile_id=request.profile_id,
            session_ids=retired,
            receipt_removed=deletion is not ReceiptDeletion.RECEIPT_RETAINED,
            keychain_removed=deletion in {ReceiptDeletion.DELETED, ReceiptDeletion.NOT_REQUIRED},
            automation_enabled=automation_enabled,
        )

    def _lock_session(
        self: RuntimeProfileConnections,
        connection: ProfileConnection,
        host: RuntimeProfileHost,
        context: RuntimeConnectionContext,
        request: RuntimeSessionRequest,
    ) -> RuntimeSessionsLocked | AccessDenied:
        retired = host.authority.lock_session(
            connection_id=context.connection_id,
            session_id=request.session_id,
            target_session_id=request.target_session_id or request.session_id,
        )
        if isinstance(retired, AccessDenied):
            return retired
        self._retired(retired)
        return RuntimeSessionsLocked(
            request_id=request.request_id,
            runtime_boot_id=self.boot,
            connection_id=context.connection_id,
            session_ids=retired,
        )

    def _refresh_session(
        self: RuntimeProfileConnections,
        connection: ProfileConnection,
        host: RuntimeProfileHost,
        context: RuntimeConnectionContext,
        request: RuntimeSessionRequest,
    ) -> RuntimeProfileStatus | AccessDenied:
        refreshed = host.authority.refresh_api_key(connection_id=context.connection_id, session_id=request.session_id)
        if not isinstance(refreshed, AccessSession):
            return refreshed
        return self._status(connection, host, request.request_id, request.session_id)

    def _retired(self: RuntimeProfileConnections, identities: tuple[UUID, ...]) -> None:
        with self._guard:
            hosts = tuple(self._profiles.values())
            for connection in self._connections.values():
                if connection.session_id in identities:
                    connection.session_id = None
        for host in hosts:
            host.approvals.retire_sessions(identities)

    def handle(
        self: RuntimeProfileConnections,
        context: RuntimeConnectionContext,
        channel: RuntimeByteChannel,
        request: RuntimeProfileLogin | RuntimeSessionRequest | RuntimeSignInStatusRequest,
    ) -> (
        RuntimeProfileStatus
        | RuntimeSessionsLocked
        | RuntimeSignInStatusReply
        | RuntimeHumanSignedOut
        | RuntimeAccessRefusal
    ):
        """Keep credentials out of request/response documents and refuse unknown authority."""
        sign_in = None
        try:
            if context.runtime_boot_id != self.boot or context.peer != channel.peer:
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            if not self._admitting():
                raise RuntimeRefusalError(RuntimeRefusalCode.DRAINING)
            if isinstance(request, RuntimeSignInStatusRequest):
                login = self._capture(channel).observe(credential_facilities=Availability.UNAVAILABLE)
                if login.os_owner_id != context.peer.os_owner_id:
                    raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
                return RuntimeSignInStatusReply(
                    request_id=request.request_id,
                    runtime_boot_id=self.boot,
                    connection_id=context.connection_id,
                    profile_id=request.profile_id,
                    status=observe_sign_in(
                        root=self.root,
                        storage_identity=self.storage_identity,
                        profile_id=request.profile_id,
                        login=login,
                        instant=self._wall_clock(),
                    ),
                )
            result = (
                self._login(context, channel, request)
                if isinstance(request, RuntimeProfileLogin)
                else self._session(context, request)
            )
            if not isinstance(result, AccessDenied):
                return result
            code = result.code
            sign_in = result.sign_in
        except (AutomationCustodyError, ProfileAccessRefusedError) as error:
            code = error.reason
            if isinstance(error, ProfileAccessRefusedError):
                sign_in = error.sign_in
        except RuntimeRefusalError as error:
            code = error.reason
        return RuntimeAccessRefusal(
            request_id=request.request_id,
            runtime_boot_id=self.boot,
            connection_id=context.connection_id,
            code=code,
            sign_in=sign_in,
        )

    def disconnect(self: RuntimeProfileConnections, context: RuntimeConnectionContext) -> None:
        """Release only this connection's authority; keep native login provenance separate."""
        self._events.disconnect(context)
        self._enrollments.disconnect(context.connection_id)
        with self._guard:
            connection = self._connections.get(context.connection_id)
            host = None if connection is None else self._profiles.get(connection.profile_id)
        try:
            if host is not None:
                host.authority.disconnect(context.connection_id)
        finally:
            if host is not None:
                host.approvals.retire_connection(context.connection_id)
            with self._guard:
                self._connections.pop(context.connection_id, None)
