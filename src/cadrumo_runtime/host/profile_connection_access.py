"""Runtime admission behavior for profile connections."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from cadrumo.application.user_profile.access_contracts import AccessDenialCode, AccessDenied, Availability
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.automation_administration import reconcile_automation_receipt
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo_client.contracts.access_management import (
    AccessManagementRequest,
    AutomationDeny,
    ProfileRecoveryPrepare,
    ProfileResume,
    SessionInventory,
)
from cadrumo_client.contracts.contracts import ByteChannel, RefusalCode, RefusalError
from cadrumo_client.contracts.enrollment_access import (
    EnrollmentPrepare,
    EnrollmentReconcile,
    EnrollmentRecorded,
    EnrollmentRequest,
)
from cadrumo_client.contracts.profile_access import AccessRefusal
from cadrumo_client.contracts.transport import ConnectionContext
from cadrumo_client.transport.frame_io import write_document

from .profile_host import ProfileConnection, RuntimeProfileHost

if TYPE_CHECKING:
    from .profile_connections import RuntimeProfileConnections


type _ExistingRuntimeAccessRequest = AutomationDeny | ProfileResume | SessionInventory


class ProfileConnectionAccessMixin:
    """Own the admission behavior of the profile connection service."""

    def _validate_access_connection(
        self: RuntimeProfileConnections, connection: ProfileConnection, host: RuntimeProfileHost
    ) -> None:
        with self._guard:
            if (
                not self._admitting()
                or self._connections.get(connection.context.connection_id) is not connection
                or self._profiles.get(connection.profile_id) is not host
            ):
                raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        observed = connection.login.observe(credential_facilities=Availability.UNAVAILABLE)
        if not observed.active or not observed.unlocked or observed.os_owner_id != connection.context.peer.os_owner_id:
            raise AutomationCustodyError(AutomationCustodyCode.NEEDS_USER)

    def _resolve_access_management(
        self: RuntimeProfileConnections,
        context: ConnectionContext,
        channel: ByteChannel,
        request: AccessManagementRequest,
    ) -> tuple[ProfileConnection, RuntimeProfileHost]:
        if context.runtime_boot_id != self.boot or context.peer != channel.peer:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED)
        if isinstance(request, ProfileRecoveryPrepare):
            connection, host = self._resolve_recovery_access(context, channel, request)
        else:
            connection, host = self._resolve_existing_access(context, request)
        self._validate_access_connection(connection, host)
        return connection, host

    def _resolve_recovery_access(
        self: RuntimeProfileConnections,
        context: ConnectionContext,
        channel: ByteChannel,
        request: ProfileRecoveryPrepare,
    ) -> tuple[ProfileConnection, RuntimeProfileHost]:
        with self._guard:
            connection = self._connections.get(context.connection_id)
        if connection is None:
            return self._prepare_unadmitted(context, channel, request, method="management")
        if (
            connection.context != context
            or connection.profile_id != request.profile_id
            or connection.frontend is not request.frontend
            or connection.method != "management"
            or connection.session_id is not None
        ):
            raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
        return connection, self._host(request.profile_id, context)

    def _resolve_existing_access(
        self: RuntimeProfileConnections,
        context: ConnectionContext,
        request: _ExistingRuntimeAccessRequest,
    ) -> tuple[ProfileConnection, RuntimeProfileHost]:
        connection = self._connected(context.connection_id)
        with self._guard:
            host = self._profiles.get(request.profile_id)
        if host is None or connection.context != context or connection.profile_id != request.profile_id:
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        if isinstance(request, ProfileResume):
            if (
                connection.method != "management"
                or connection.session_id is not None
                or connection.frontend is not request.frontend
                or connection.recovery_generation != request.lock_generation
            ):
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
        elif connection.session_id != request.session_id:
            raise ProfileAccessRefusedError(AccessDenialCode.CONNECTION_MISMATCH)
        return connection, host

    def _profile_lock_changed(self: RuntimeProfileConnections, profile_id: UUID) -> None:
        self._enrollments.retire_profile(profile_id)
        with self._guard:
            host = self._profiles.get(profile_id)
            connections = tuple(item for item in self._connections.values() if item.profile_id == profile_id)
        for connection in connections:
            connection.recovery_generation = None
            if host is not None:
                host.approvals.retire_connection(connection.context.connection_id)

    def _synchronize_profile_sessions(self: RuntimeProfileConnections, host: RuntimeProfileHost) -> None:
        with self._guard:
            connections = tuple(
                item for item in self._connections.values() if item.profile_id == host.store.binding.profile_id
            )
        retired: list[UUID] = []
        with host.guard:
            for connection in connections:
                session_id = connection.session_id
                if session_id is None:
                    continue
                try:
                    status = self._status(connection, host, uuid4(), session_id)
                    denied = isinstance(status, AccessDenied) or status.status.denial is not None
                except AutomationCustodyError:
                    denied = True
                if denied:
                    connection.session_id = None
                    retired.append(session_id)
            host.approvals.retire_sessions(tuple(retired))

    def manage_access(
        self: RuntimeProfileConnections,
        context: ConnectionContext,
        channel: ByteChannel,
        request: AccessManagementRequest,
    ) -> None:
        """Project the existing exact-profile security services over native transport."""
        named = request.frontend if isinstance(request, ProfileRecoveryPrepare | ProfileResume) else None
        if self._refused_as_persons_act(
            context, channel, request_id=request.request_id, frontend=named or self._connection_frontend(context)
        ):
            return
        self._management.handle(context, channel, request)

    def enrollment(
        self: RuntimeProfileConnections,
        context: ConnectionContext,
        channel: ByteChannel,
        request: EnrollmentRequest,
    ) -> None:
        """Dispatch the bounded pre-unlock request and protected client delivery door."""
        if context.runtime_boot_id != self.boot:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED)
        named = request.frontend if isinstance(request, EnrollmentPrepare) else None
        if self._refused_as_persons_act(
            context, channel, request_id=request.request_id, frontend=named or self._connection_frontend(context)
        ):
            return
        if isinstance(request, EnrollmentReconcile):
            self._reconcile_enrollment(context, channel, request)
            return
        self._enrollments.handle(context, channel, request)

    def _reconcile_enrollment(
        self: RuntimeProfileConnections,
        context: ConnectionContext,
        channel: ByteChannel,
        request: EnrollmentReconcile,
    ) -> None:
        """Release own-grant terminal metadata only under current root authority."""
        if context.peer != channel.peer:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED)
        try:
            connection = self._connected(context.connection_id)
            if (
                connection.context != context
                or connection.profile_id != request.profile_id
                or connection.method != "api_key"
                or connection.session_id != request.session_id
            ):
                raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
            host = self._host(request.profile_id, context)
            with host.authority.owner.admission_guard():
                if not self._admitting():
                    raise RefusalError(RefusalCode.DRAINING)
                session = host.authority.automation_request_session(
                    connection_id=context.connection_id, session_id=request.session_id
                )
                receipt = reconcile_automation_receipt(
                    state=host.store.enrollment_state(), session=session, request_id=request.enrollment_request_id
                )
                session = host.authority.automation_request_session(
                    connection_id=context.connection_id, session_id=request.session_id
                )
                remaining = min(5.0, (session.expires_at - self._wall_clock()).total_seconds())
                if remaining <= 0:
                    raise RefusalError(RefusalCode.DEADLINE_EXCEEDED)
                write_document(
                    channel,
                    EnrollmentRecorded(
                        request_id=request.request_id,
                        runtime_boot_id=context.runtime_boot_id,
                        connection_id=context.connection_id,
                        receipt=receipt,
                    ),
                    deadline=time.monotonic() + remaining,
                )
        except (AutomationCustodyError, ProfileAccessRefusedError) as error:
            write_document(
                channel,
                AccessRefusal(
                    request_id=request.request_id,
                    runtime_boot_id=context.runtime_boot_id,
                    connection_id=context.connection_id,
                    code=error.reason,
                ),
                deadline=time.monotonic() + 5,
            )
