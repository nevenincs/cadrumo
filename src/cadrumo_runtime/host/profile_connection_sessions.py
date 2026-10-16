"""Runtime session behavior for profile connections."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import SecretBytes

from cadrumo.adapters.persistence.storage.custody.acceleration_receipt import ReceiptDeletion
from cadrumo.application.user_profile.access_contracts import (
    AccessDenialCode,
    AccessDenied,
    AccessScope,
    AccessSession,
    AuthorityState,
    Availability,
)
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.access_policy import intersect_scopes
from cadrumo.application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
    AutomationCustodySnapshot,
)
from cadrumo.application.user_profile.session_retirement import SessionRetirementKind
from cadrumo.core.config import load_settings
from cadrumo.core.time.clock import now
from cadrumo_client.contracts.attendance import (
    AttendanceAsk,
    AttendanceDecide,
    AttendanceDecided,
    AttendanceInventory,
    AttendancePending,
)
from cadrumo_client.contracts.contracts import ByteChannel, RefusalCode, RefusalError
from cadrumo_client.contracts.profile_access import (
    AccessRefusal,
    ProfileDisclosurePage,
    ProfileDisclosurePageRequest,
    ProfileLogin,
    ProfileStatus,
    SecretReady,
    SessionRequest,
    SessionsLocked,
)
from cadrumo_client.contracts.sign_in import HumanSignedOut, SignInStatusReply, SignInStatusRequest
from cadrumo_client.contracts.transport import ConnectionContext
from cadrumo_client.transport.frame_io import read_secret, write_document

from .profile_host import ProfileConnection, RuntimeProfileHost
from .sign_in_status import observe_sign_in
from .sign_in_sweep import revoke_other_saved_sign_ins

if TYPE_CHECKING:
    from .profile_connections import RuntimeProfileConnections


def _issued_key_can_admit(snapshot: AutomationCustodySnapshot, instant: datetime) -> bool:
    """Say whether an issued key could still admit an automation: a sign-out ends no key session."""
    if not snapshot.automation_enabled:
        return False
    live_grants = {
        grant.grant_id
        for grant in snapshot.grants
        if grant.state is AuthorityState.ACTIVE and grant.unattended and grant.valid_from <= instant < grant.expires_at
    }
    return any(
        key.grant_id in live_grants
        and key.state is AuthorityState.ACTIVE
        and key.valid_from <= instant < key.expires_at
        for key in snapshot.keys
    )


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
    ) -> ProfileStatus | AccessDenied:
        status = host.authority.status(
            connection_id=connection.context.connection_id,
            session_id=session_id,
            published_authority=Availability.UNAVAILABLE,
            provider=Availability.NEEDS_USER,
        )
        if isinstance(status, AccessDenied):
            return status
        # An uncertain native observation denies work but preserves the live
        # lease. Keep its wire identity so a fresh observation can recover;
        # every later request still reauthorizes against the runtime authority.
        if status.denial not in {None, AccessDenialCode.OS_SESSION_UNAVAILABLE}:
            connection.session_id = None
        return ProfileStatus(
            request_id=request_id,
            runtime_boot_id=self.boot,
            connection_id=connection.context.connection_id,
            status=status,
        )

    def _login(
        self: RuntimeProfileConnections,
        context: ConnectionContext,
        channel: ByteChannel,
        request: ProfileLogin,
    ) -> ProfileStatus | AccessDenied:
        connection, host = self._prepare(context, channel, request)
        write_document(
            channel,
            SecretReady(request_id=request.request_id, runtime_boot_id=self.boot, connection_id=context.connection_id),
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
        if request.activity_only or request.method == "api_key":
            return self._finish_login(connection, host, context, request, admitted)
        # Publish the ordinary handover and retire other profiles as one ordered
        # effect. Proof/KDF stays outside this lock and the profile-map lock is
        # never held across worker I/O. A concurrently admitted loser rechecks
        # its revoked lease before it can perform another cross-profile sweep.
        with self._human_handover_guard:
            finished = self._finish_login(connection, host, context, request, admitted)
            if (
                isinstance(finished, ProfileStatus)
                and finished.status.denial is None
                and finished.status.connected
                and finished.status.credential_authenticated
                and finished.status.profile_bound
            ):
                self._sign_out_other_profiles(keep=request.profile_id)
            return finished

    def _sign_out_other_profiles(self: RuntimeProfileConnections, *, keep: UUID) -> None:
        """Keep one profile signed in: a person's sign-in to ``keep`` signs every other profile out everywhere.

        Each other hosted profile is signed out as the person's sign-out does
        it: its generation advances, its stored sign-in is deleted and every
        human session it holds ends, on every frontend, an automation's resumed
        session included. A key session needs no sign-in and stays. A profile
        that is not hosted has no live session, so only its stored sign-in is
        revoked.
        """
        with self._guard:
            hosts = {profile_id: host for profile_id, host in self._profiles.items() if profile_id != keep}
            installation = self._installation
        for host in hosts.values():
            _deletion, retired = host.revoke_human_sign_in(kind=SessionRetirementKind.SIGNED_OUT)
            self._retired(retired)
        # Their automation trees are gone before this sign-in is answered and its profile is usable.
        if installation is not None:
            revoke_other_saved_sign_ins(
                root=self.root, installation=installation, keep=keep, hosted_profiles=frozenset(hosts)
            )

    def _admit_human_login(
        self: RuntimeProfileConnections,
        connection: ProfileConnection,
        host: RuntimeProfileHost,
        context: ConnectionContext,
        secret: bytearray,
    ) -> AccessSession | AccessDenied:
        with host.guard:
            if not self._admitting():
                raise RefusalError(RefusalCode.DRAINING)
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
        request: ProfileLogin,
    ) -> _ApiKeyLogin | AccessDenied:
        with host.guard:
            if not self._admitting():
                raise RefusalError(RefusalCode.DRAINING)
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
            requested_scope = request.scope or grant.scope
            operation_ceiling = requested_scope.model_copy(
                update={
                    "disclosures": grant.scope.disclosures,
                    "disclosure_categories": grant.scope.disclosure_categories,
                }
            )
            return _ApiKeyLogin(credential, intersect_scopes((operation_ceiling, grant.scope)))

    def _finish_login(
        self: RuntimeProfileConnections,
        connection: ProfileConnection,
        host: RuntimeProfileHost,
        context: ConnectionContext,
        request: ProfileLogin,
        admitted: AccessSession | AccessDenied,
    ) -> ProfileStatus | AccessDenied:
        with host.guard:
            if isinstance(admitted, AccessDenied):
                return admitted
            if not self._admitting():
                host.authority.disconnect(context.connection_id)
                raise RefusalError(RefusalCode.DRAINING)
            connection.session_id = admitted.session_id
            receipt = host.owner.take_human_login_receipt(admitted.session_id)
            result = self._status(connection, host, request.request_id, admitted.session_id)
            if isinstance(result, ProfileStatus):
                return result.model_copy(update={"human_login": receipt})
            return result

    def _session(
        self: RuntimeProfileConnections, context: ConnectionContext, request: SessionRequest
    ) -> ProfileStatus | SessionsLocked | HumanSignedOut | AccessDenied:
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
        context: ConnectionContext,
        request: SessionRequest,
    ) -> ProfileStatus | SessionsLocked | HumanSignedOut | AccessDenied:
        with host.guard:
            if not self._admitting():
                raise RefusalError(RefusalCode.DRAINING)
            if request.action in {"session_lock", "human_sign_out", "session_activity"}:
                # Locking a session and signing the person out are the person's acts, never an automation's.
                self._require_persons_frontend(connection.frontend)
            if request.action == "session_lock":
                return self._lock_session(connection, host, context, request)
            if request.target_session_id is not None:
                raise RefusalError(RefusalCode.INVALID_FRAME)
            if request.action == "human_sign_out":
                return self._human_sign_out(host, context, request)
            if request.action == "session_refresh":
                return self._refresh_session(connection, host, context, request)
            if request.action == "session_activity":
                renewed = host.authority.note_human_activity(
                    connection_id=context.connection_id,
                    session_id=request.session_id,
                    idle_window=timedelta(minutes=load_settings().cadrumo_bucket_default_idle_lock_minutes),
                )
                if isinstance(renewed, AccessDenied):
                    return renewed
            return self._status(connection, host, request.request_id, request.session_id)

    def _disclosure_page(
        self: RuntimeProfileConnections, context: ConnectionContext, request: ProfileDisclosurePageRequest
    ) -> ProfileDisclosurePage | AccessDenied:
        """Page the disclosures the caller's own status counts, under the same connection checks as a status."""
        connection = self._connected(context.connection_id)
        if connection.context != context or connection.profile_id != request.profile_id:
            return AccessDenied(code=AccessDenialCode.PROFILE_MISMATCH)
        if connection.session_id != request.session_id:
            return AccessDenied(code=AccessDenialCode.CONNECTION_MISMATCH)
        with self._guard:
            host = self._profiles[connection.profile_id]
        with host.guard:
            if not self._admitting():
                raise RefusalError(RefusalCode.DRAINING)
            page = host.authority.disclosure_page(
                connection_id=context.connection_id, session_id=request.session_id, request=request.page
            )
        if isinstance(page, AccessDenied):
            return page
        return ProfileDisclosurePage(
            request_id=request.request_id,
            runtime_boot_id=self.boot,
            connection_id=context.connection_id,
            page=page,
        )

    def _human_sign_out(
        self: RuntimeProfileConnections,
        host: RuntimeProfileHost,
        context: ConnectionContext,
        request: SessionRequest,
    ) -> HumanSignedOut:
        # Signing the person out is theirs alone: a session of the human kind, on any frontend.
        host.authority.human_administration_facts(connection_id=context.connection_id, session_id=request.session_id)
        try:
            automation_enabled = host.store.enrollment_state().automation_enabled
        except AutomationCustodyError:
            automation_enabled = None
        deletion, retired = host.revoke_human_sign_in()
        try:
            automation_access_remains: bool | None = _issued_key_can_admit(host.store.snapshot(), now())
        except AutomationCustodyError as error:
            # A profile that never published automation control has issued no key; any other failure is unknown.
            automation_access_remains = False if error.reason is AutomationCustodyCode.MISSING else None
        self._retired(retired)
        return HumanSignedOut(
            request_id=request.request_id,
            runtime_boot_id=self.boot,
            connection_id=context.connection_id,
            profile_id=request.profile_id,
            session_ids=retired,
            receipt_removed=deletion is not ReceiptDeletion.RECEIPT_RETAINED,
            keychain_removed=deletion in {ReceiptDeletion.DELETED, ReceiptDeletion.NOT_REQUIRED},
            automation_enabled=automation_enabled,
            automation_access_remains=automation_access_remains,
        )

    def _lock_session(
        self: RuntimeProfileConnections,
        connection: ProfileConnection,
        host: RuntimeProfileHost,
        context: ConnectionContext,
        request: SessionRequest,
    ) -> SessionsLocked | AccessDenied:
        retired = host.authority.lock_session(
            connection_id=context.connection_id,
            session_id=request.session_id,
            target_session_id=request.target_session_id or request.session_id,
        )
        if isinstance(retired, AccessDenied):
            return retired
        self._retired(retired)
        return SessionsLocked(
            request_id=request.request_id,
            runtime_boot_id=self.boot,
            connection_id=context.connection_id,
            session_ids=retired,
        )

    def _refresh_session(
        self: RuntimeProfileConnections,
        connection: ProfileConnection,
        host: RuntimeProfileHost,
        context: ConnectionContext,
        request: SessionRequest,
    ) -> ProfileStatus | AccessDenied:
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
        if identities:
            self._sign_in_changed()

    def handle(
        self: RuntimeProfileConnections,
        context: ConnectionContext,
        channel: ByteChannel,
        request: ProfileLogin
        | SessionRequest
        | ProfileDisclosurePageRequest
        | SignInStatusRequest
        | AttendanceAsk
        | AttendanceDecide,
    ) -> (
        ProfileStatus
        | ProfileDisclosurePage
        | SessionsLocked
        | SignInStatusReply
        | HumanSignedOut
        | AttendancePending
        | AttendanceInventory
        | AttendanceDecided
        | AccessRefusal
    ):
        """Keep credentials out of request/response documents and refuse unknown authority."""
        sign_in = None
        try:
            if context.runtime_boot_id != self.boot or context.peer != channel.peer:
                raise RefusalError(RefusalCode.PEER_UNTRUSTED)
            if not self._admitting():
                raise RefusalError(RefusalCode.DRAINING)
            if (
                isinstance(request, SessionRequest)
                and request.action == "session_activity"
                and self._nonhuman_peer(context, channel)
            ):
                raise ProfileAccessRefusedError(AccessDenialCode.PERSON_ACT_REQUIRED)
            if isinstance(request, SignInStatusRequest):
                login = self._capture(channel).observe(credential_facilities=Availability.UNAVAILABLE)
                if login.os_owner_id != context.peer.os_owner_id:
                    raise RefusalError(RefusalCode.PEER_UNTRUSTED)
                if request.watch:
                    # Watch before reading, so a change racing this read still cues the watcher.
                    self.watch_sign_in(context)
                return SignInStatusReply(
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
            if isinstance(request, AttendanceAsk):
                result = self._attendance_ask(context, channel, request)
            elif isinstance(request, AttendanceDecide):
                result = self._attendance_decide(context, request)
            elif isinstance(request, ProfileLogin):
                result = self._login(context, channel, request)
                if not isinstance(result, AccessDenied):
                    # Admission has published the session and minted any receipt.
                    self._sign_in_changed()
            elif isinstance(request, ProfileDisclosurePageRequest):
                result = self._disclosure_page(context, request)
            else:
                result = self._session(context, request)
            if not isinstance(result, AccessDenied):
                return result
            code = result.code
            sign_in = result.sign_in
        except (AutomationCustodyError, ProfileAccessRefusedError) as error:
            code = error.reason
            if isinstance(error, ProfileAccessRefusedError):
                sign_in = error.sign_in
        except RefusalError as error:
            code = error.reason
        return AccessRefusal(
            request_id=request.request_id,
            runtime_boot_id=self.boot,
            connection_id=context.connection_id,
            code=code,
            sign_in=sign_in,
        )

    def disconnect(self: RuntimeProfileConnections, context: ConnectionContext) -> None:
        """Release only this connection's authority; keep native login provenance separate."""
        self._events.disconnect(context)
        self._enrollments.disconnect(context.connection_id)
        self._forget_attendance(context.connection_id)
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
                self._language_observations.pop(context.connection_id, None)
                self._notice_connections.pop(context.connection_id, None)
                self._services.pop(context.connection_id, None)
                self._sign_in_watchers.discard(context.connection_id)
            if connection is not None and connection.session_id is not None:
                # A held sign-in lives on its connection and ends with it.
                self._sign_in_changed()
