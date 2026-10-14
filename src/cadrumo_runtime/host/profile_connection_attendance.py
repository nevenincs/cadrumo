"""Attendance: admit an automation connection under a person's live sign-in only on that person's decision.

The person's connection holds a password sign-in and decides each ask by its
attendance id. The asking connection is identified by what the kernel says of
it, never by an id it names. An approved connection holds an attended child of
the person's session; when that session ends, the child ends with it.

Attendance state is read and written only in short sections under the
connections guard, and never while the profile authority is called, so the
existing order of the profile guard before the connections guard holds.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from cadrumo.application.operations.person_acts import is_persons_frontend
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import AccessDenialCode, AccessDenied, AccessScope, Availability
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo.core.time.utc import UtcInstant
from cadrumo_client.contracts.attendance import (
    ATTENDANCE_PENDING_LIMIT,
    ATTENDANCE_PENDING_SECONDS,
    AttendanceAsk,
    AttendanceCandidate,
    AttendanceDecide,
    AttendanceDecided,
    AttendanceInventory,
    AttendancePending,
)
from cadrumo_client.contracts.contracts import ByteChannel, RefusalCode, RefusalError
from cadrumo_client.contracts.profile_access import ProfileStatus
from cadrumo_client.contracts.transport import ConnectionContext

from .profile_host import ProfileConnection

if TYPE_CHECKING:
    from .profile_connections import RuntimeProfileConnections
    from .profile_host import RuntimeProfileHost

ATTENDANCE_METHOD = "attendance"
"""The method of a connection admitted only by attendance; it never presented a credential."""


@dataclass(slots=True)
class PendingAttendance:
    """One ask: the asking connection, what the kernel says of it, and the person's answer so far."""

    attendance_id: UUID
    profile_id: UUID
    connection_id: UUID
    process_id: int | None
    image_path: str | None
    scope: AccessScope
    requested_at: UtcInstant
    expires_at: UtcInstant
    monotonic_deadline: float
    approved: bool | None = None


@dataclass(frozen=True, slots=True)
class AttendedConnection:
    """The person's session an approved connection follows, so its lapsed child can be issued again."""

    holder_connection_id: UUID
    parent_session_id: UUID


class ProfileConnectionAttendanceMixin:
    """Own attendance asks, the person's decisions and the attended children they admit."""

    def _attendance_ask(
        self: RuntimeProfileConnections,
        context: ConnectionContext,
        channel: ByteChannel,
        request: AttendanceAsk,
    ) -> AttendancePending | ProfileStatus | AccessDenied:
        if request.frontend is not OperationFrontendProjection.EXTERNAL_CLIENT:
            # Attendance is the external client automation's door; a person signs in with their own proof,
            # and the automation host only resumes the person's stored sign-in.
            raise RefusalError(RefusalCode.INVALID_FRAME)
        with self._guard:
            host = self._profiles.get(request.profile_id)
        if host is None:
            return AccessDenied(code=AccessDenialCode.AUTHENTICATION_REQUIRED)
        if request.action == "attendance_status":
            return self._attendance_status(context, host, request)
        connection = self._attendance_connection(
            context, channel, request, request.scope, persons_frontend=is_persons_frontend(request.frontend)
        )
        with host.guard:
            if not self._admitting():
                raise RefusalError(RefusalCode.DRAINING)
            renewed = self._renew_attended(connection, host, request.request_id)
            if renewed is not None:
                return renewed
            owner = self._service_tree_owner(context, channel)
            if owner is not None and owner.lease is not None:
                if owner.lease.profile_id != request.profile_id:
                    return AccessDenied(code=AccessDenialCode.PROFILE_MISMATCH)
                parent_connection = self._connected(owner.peer.connection_id)
                connection.client_id = parent_connection.client_id
                # Delegation follows the original human root and installed ceiling;
                # the service has no power to create new human authority.
                scope = request.scope.model_copy(
                    update={"operations": request.scope.operations & owner.descriptor.operation_scope.operations}
                )
                child = host.authority.attend(
                    connection_id=owner.peer.connection_id,
                    parent_session_id=owner.lease.session_id,
                    recipient_connection_id=context.connection_id,
                    scope=scope,
                    delegated_parent=True,
                )
                if isinstance(child, AccessDenied):
                    return child
                connection.session_id = child.session_id
                with self._guard:
                    self._attended[context.connection_id] = AttendedConnection(
                        owner.peer.connection_id, owner.lease.session_id
                    )
                return self._status(connection, host, request.request_id, child.session_id)
            with self._guard:
                spent = context.connection_id in self._attendance_spent
            if spent or not self._attendance_holder_present(request.profile_id):
                # A connection whose approval ended is let go and asks again on a new
                # connection, so an ask made here would wait for nobody.
                return AccessDenied(code=AccessDenialCode.AUTHENTICATION_REQUIRED)
            requested_at = self._wall_clock()
            ask = PendingAttendance(
                attendance_id=uuid4(),
                profile_id=request.profile_id,
                connection_id=context.connection_id,
                process_id=context.peer.process_id,
                image_path=context.peer.image_path,
                scope=request.scope,
                requested_at=requested_at,
                expires_at=requested_at + timedelta(seconds=ATTENDANCE_PENDING_SECONDS),
                monotonic_deadline=time.monotonic() + ATTENDANCE_PENDING_SECONDS,
            )
            with self._guard:
                self._expire_attendance()
                pending = [item for item in self._attendance.values() if item.profile_id == request.profile_id]
                if any(item.connection_id == context.connection_id for item in pending):
                    raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
                if sum(item.approved is None for item in pending) >= ATTENDANCE_PENDING_LIMIT:
                    return AccessDenied(code=AccessDenialCode.AUTHENTICATION_REQUIRED)
                self._attendance[ask.attendance_id] = ask
        return AttendancePending(
            request_id=request.request_id,
            runtime_boot_id=self.boot,
            connection_id=context.connection_id,
            attendance_id=ask.attendance_id,
            expires_at=ask.expires_at,
        )

    def _attendance_connection(
        self: RuntimeProfileConnections,
        context: ConnectionContext,
        channel: ByteChannel,
        request: AttendanceAsk,
        scope: AccessScope,
        *,
        persons_frontend: bool,
    ) -> ProfileConnection:
        """Register the asking connection with its kernel-observed login; a reused one must match exactly."""
        with self._guard:
            previous = self._connections.get(context.connection_id)
        if previous is not None:
            if (
                previous.context != context
                or previous.profile_id != request.profile_id
                or previous.frontend is not request.frontend
                or previous.requested_scope != scope
                or previous.method != ATTENDANCE_METHOD
            ):
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
            return previous
        # A process of a hosted automation's tree is attended only as an automation, never on a person's frontend.
        login = self._capture(channel)
        observed = login.observe(credential_facilities=Availability.UNAVAILABLE)
        if not observed.active or observed.os_owner_id != context.peer.os_owner_id:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED)
        connection = ProfileConnection(
            context,
            login,
            uuid4(),
            request.profile_id,
            request.frontend,
            method=ATTENDANCE_METHOD,
            requested_scope=scope,
        )
        with self._guard:
            if not self._admitting():
                raise RefusalError(RefusalCode.DRAINING)
            self._connections[context.connection_id] = connection
            self._logins[login.login_id] = login
        return connection

    def _attendance_status(
        self: RuntimeProfileConnections,
        context: ConnectionContext,
        host: RuntimeProfileHost,
        request: AttendanceAsk,
    ) -> AttendancePending | ProfileStatus | AccessDenied:
        with host.guard:
            with self._guard:
                self._expire_attendance()
                ask = self._attendance.get(request.attendance_id) if request.attendance_id is not None else None
                if ask is None or ask.connection_id != context.connection_id or ask.profile_id != request.profile_id:
                    # Lapsed, declined, or not this connection's ask: nothing admits it.
                    return AccessDenied(code=AccessDenialCode.AUTHENTICATION_REQUIRED)
                if ask.approved is None:
                    return AttendancePending(
                        request_id=request.request_id,
                        runtime_boot_id=self.boot,
                        connection_id=context.connection_id,
                        attendance_id=ask.attendance_id,
                        expires_at=ask.expires_at,
                    )
                del self._attendance[ask.attendance_id]
            connection = self._connected(context.connection_id)
            if not ask.approved or connection.session_id is None:
                return AccessDenied(code=AccessDenialCode.AUTHENTICATION_REQUIRED)
            return self._status(connection, host, request.request_id, connection.session_id)

    def _renew_attended(
        self: RuntimeProfileConnections, connection: ProfileConnection, host: RuntimeProfileHost, request_id: UUID
    ) -> ProfileStatus | AccessDenied | None:
        """Issue a lapsed child again to a connection the person already approved, while their session lives.

        The approval was for this exact connection under that exact session, so
        a new child widens nothing. Anything else needs a new decision.
        """
        with self._guard:
            attended = self._attended.get(connection.context.connection_id)
        if attended is None:
            return None
        if connection.session_id is not None:
            current = self._status(connection, host, request_id, connection.session_id)
            if isinstance(current, ProfileStatus) and current.status.denial is None:
                return current
            # The status read retired a lapsed child and cleared the connection's session.
            connection.session_id = None
        scope = connection.requested_scope
        if scope is None:
            with self._guard:
                self._attended.pop(connection.context.connection_id, None)
                self._attendance_spent.add(connection.context.connection_id)
            return AccessDenied(code=AccessDenialCode.OPERATION_UNAVAILABLE)
        child = host.authority.attend(
            connection_id=attended.holder_connection_id,
            parent_session_id=attended.parent_session_id,
            recipient_connection_id=connection.context.connection_id,
            scope=scope,
            delegated_parent=attended.holder_connection_id in self._services,
        )
        if isinstance(child, AccessDenied):
            try:
                host.authority.human_administration_facts(
                    connection_id=attended.holder_connection_id, session_id=attended.parent_session_id
                )
            except (ProfileAccessRefusedError, AutomationCustodyError):
                # The person's session has ended; the approval ended with it.
                with self._guard:
                    self._attended.pop(connection.context.connection_id, None)
                    self._attendance_spent.add(connection.context.connection_id)
                return None
            # The person's session lives: this refusal passes, and the approval stands for a later call.
            return child
        connection.session_id = child.session_id
        return self._status(connection, host, request_id, child.session_id)

    def _attendance_holder_present(self: RuntimeProfileConnections, profile_id: UUID) -> bool:
        with self._guard:
            return any(
                (holder := self._connections.get(connection_id)) is not None
                and holder.profile_id == profile_id
                and holder.session_id == session_id
                for connection_id, session_id in self._attendance_holders.items()
            )

    def _expire_attendance(self: RuntimeProfileConnections) -> None:
        """Drop lapsed asks; the caller holds the connections guard."""
        instant = time.monotonic()
        for identity in [
            item.attendance_id for item in self._attendance.values() if instant >= item.monotonic_deadline
        ]:
            del self._attendance[identity]

    def _attendance_decide(
        self: RuntimeProfileConnections, context: ConnectionContext, request: AttendanceDecide
    ) -> AttendanceInventory | AttendanceDecided | AccessDenied:
        connection = self._connected(context.connection_id)
        if connection.context != context or connection.profile_id != request.profile_id:
            return AccessDenied(code=AccessDenialCode.PROFILE_MISMATCH)
        if connection.session_id != request.session_id:
            return AccessDenied(code=AccessDenialCode.CONNECTION_MISMATCH)
        # Deciding who follows the person's sign-in is the person's act, never an automation's.
        self._require_persons_frontend(connection.frontend)
        with self._guard:
            host = self._profiles[connection.profile_id]
        with host.guard:
            if not self._admitting():
                raise RefusalError(RefusalCode.DRAINING)
            facts = host.authority.human_administration_facts(
                connection_id=context.connection_id, session_id=request.session_id
            )
            if facts.session is None:
                return AccessDenied(code=AccessDenialCode.HUMAN_AUTHORITY_REQUIRED)
            with self._guard:
                self._attendance_holders[context.connection_id] = request.session_id
                self._expire_attendance()
                candidates = tuple(
                    AttendanceCandidate(
                        attendance_id=item.attendance_id,
                        process_id=item.process_id,
                        image_path=item.image_path,
                        frontend=OperationFrontendProjection.EXTERNAL_CLIENT,
                        scope=item.scope,
                        requested_at=item.requested_at,
                        expires_at=item.expires_at,
                    )
                    for item in sorted(self._attendance.values(), key=lambda item: item.requested_at)
                    if item.profile_id == request.profile_id and item.approved is None
                )
            if request.action == "attendance_inventory":
                return AttendanceInventory(
                    request_id=request.request_id,
                    runtime_boot_id=self.boot,
                    connection_id=context.connection_id,
                    profile_id=request.profile_id,
                    session_expires_at=facts.session.expires_at,
                    candidates=candidates,
                )
            return self._decide_attendance(connection, host, context, request)

    def _decide_attendance(
        self: RuntimeProfileConnections,
        holder: ProfileConnection,
        host: RuntimeProfileHost,
        context: ConnectionContext,
        request: AttendanceDecide,
    ) -> AttendanceDecided | AccessDenied:
        with self._guard:
            ask = self._attendance.get(request.attendance_id) if request.attendance_id is not None else None
            if ask is None or ask.profile_id != request.profile_id or ask.approved is not None:
                return AccessDenied(code=AccessDenialCode.OPERATION_UNAVAILABLE)
            recipient = self._connections.get(ask.connection_id)
        approved = bool(request.approve)
        if approved:
            if recipient is None or recipient.method != ATTENDANCE_METHOD or recipient.session_id is not None:
                with self._guard:
                    self._attendance.pop(ask.attendance_id, None)
                return AccessDenied(code=AccessDenialCode.OPERATION_UNAVAILABLE)
            scope = recipient.requested_scope
            if scope is None:
                with self._guard:
                    self._attendance.pop(ask.attendance_id, None)
                return AccessDenied(code=AccessDenialCode.OPERATION_UNAVAILABLE)
            # Disclosures name the person's sign-in as their destination: the attended
            # connection receives what the person's own session may receive, and nothing more.
            with self._guard:
                own_client_id, recipient.client_id = recipient.client_id, holder.client_id
            try:
                child = host.authority.attend(
                    connection_id=context.connection_id,
                    parent_session_id=request.session_id,
                    recipient_connection_id=ask.connection_id,
                    scope=scope,
                )
            except BaseException:
                with self._guard:
                    recipient.client_id = own_client_id
                raise
            if isinstance(child, AccessDenied):
                # Nothing was admitted, so the connection keeps only its own identity.
                with self._guard:
                    recipient.client_id = own_client_id
                    self._attendance.pop(ask.attendance_id, None)
                return child
            recipient.session_id = child.session_id
            with self._guard:
                self._attended[ask.connection_id] = AttendedConnection(context.connection_id, request.session_id)
        with self._guard:
            ask.approved = approved
        return AttendanceDecided(
            request_id=request.request_id,
            runtime_boot_id=self.boot,
            connection_id=context.connection_id,
            attendance_id=ask.attendance_id,
            approved=approved,
        )

    def _forget_attendance(self: RuntimeProfileConnections, connection_id: UUID) -> None:
        """Drop every ask, approval and holder role tied to a closed connection."""
        with self._guard:
            self._attendance_holders.pop(connection_id, None)
            self._attended.pop(connection_id, None)
            self._attendance_spent.discard(connection_id)
            for identity in [
                item.attendance_id for item in self._attendance.values() if item.connection_id == connection_id
            ]:
                del self._attendance[identity]
            for recipient, attended in tuple(self._attended.items()):
                if attended.holder_connection_id == connection_id:
                    del self._attended[recipient]
                    self._attendance_spent.add(recipient)
