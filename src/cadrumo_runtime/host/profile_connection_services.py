"""Human-approved installed service leases on verified native connections."""

from __future__ import annotations

from threading import Thread
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from cadrumo.application.operations.person_acts import is_persons_frontend
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo_client.contracts.access_refusals import AccessDenialCode, AccessDenied
from cadrumo_client.contracts.access_vocabulary import Availability
from cadrumo_client.contracts.contracts import ByteChannel, RefusalCode, RefusalError
from cadrumo_client.contracts.profile_access import ProfileLogin
from cadrumo_client.contracts.service_access import (
    InstalledServiceDescriptor,
    ServiceAdmission,
    ServiceAdmissionStatusQuery,
    ServiceConnect,
    ServiceConnected,
    ServiceLease,
    VerifiedServicePeer,
)
from cadrumo_client.contracts.session_events import ServiceAdmissionChanged, ServiceLeaseChanged
from cadrumo_client.contracts.transport import ConnectionContext

from .desktop_holder_identity import verify_desktop_holder
from .profile_connection import ProfileConnection
from .profile_host import RuntimeProfileHost
from .service_connection_records import (
    PendingServiceAdmission,
    ServiceConnection,
    admission_status_matches,
    cancel_pending_status,
    cancel_service_admissions,
    pending_service_reply,
    person_holder_matches,
)

if TYPE_CHECKING:
    from .profile_connections import RuntimeProfileConnections


class ProfileConnectionServicesMixin:
    """Handle installed-service connections owned by the runtime profile host."""

    def _restore_service_lease(
        self: RuntimeProfileConnections,
        context: ConnectionContext,
        existing: ServiceConnection,
        connection: ProfileConnection,
        host: RuntimeProfileHost,
        lease: ServiceLease,
    ) -> None:
        approved = lease
        try:
            holder_id = self._human_parent_connection(approved)
            host.authority.human_administration_facts(connection_id=holder_id, session_id=approved.parent_session_id)
            child = host.authority.attend(
                connection_id=holder_id,
                parent_session_id=approved.parent_session_id,
                recipient_connection_id=context.connection_id,
                scope=existing.descriptor.operation_scope,
            )
        except Exception:
            with self._guard:
                if existing.lease is approved:
                    self._withdraw_lease(existing)
        else:
            if isinstance(child, AccessDenied):
                with self._guard:
                    if existing.lease is approved:
                        self._withdraw_lease(existing)
            elif existing.lease is approved:
                connection.session_id = child.session_id
                existing.lease = approved.model_copy(update={"session_id": child.session_id})

    def _reattach_service(
        self: RuntimeProfileConnections,
        context: ConnectionContext,
        request: ServiceConnect,
        descriptor: InstalledServiceDescriptor,
        existing: ServiceConnection,
        connection: ProfileConnection | None,
        host: RuntimeProfileHost | None,
    ) -> ServiceConnected:
        if (
            existing.descriptor != descriptor
            or connection is None
            or connection.profile_id != request.profile_id
            or host is None
        ):
            raise RefusalError(RefusalCode.PEER_UNTRUSTED, check="service_connection_mismatch")
        with host.guard:
            lease = existing.lease
            if lease is not None:
                status = self._status(connection, host, request.request_id, lease.session_id)
                denial = status.code if isinstance(status, AccessDenied) else status.status.denial
                # A suspended lease is restored with its parent's rebind; re-approval would withdraw it.
                if existing.lease is lease and denial is not None and denial is not AccessDenialCode.CUSTODY_RECOVERING:
                    self._restore_service_lease(context, existing, connection, host, lease)
            return ServiceConnected(
                request_id=request.request_id,
                runtime_boot_id=self.boot,
                connection_id=context.connection_id,
                profile_id=request.profile_id,
                service_id=request.service_id,
                lease=existing.lease,
            )

    def _register_service(
        self: RuntimeProfileConnections,
        context: ConnectionContext,
        channel: ByteChannel,
        request: ServiceConnect,
        descriptor: InstalledServiceDescriptor,
        peer: VerifiedServicePeer,
        connection: ProfileConnection | None,
    ) -> ServiceConnected:
        if connection is not None:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED, check="service_connection_exists")
        login = self._capture(channel)
        observed = login.observe(credential_facilities=Availability.UNAVAILABLE)
        if not observed.active or observed.os_owner_id != context.peer.os_owner_id:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED, check="service_login_inactive_or_mismatch")
        with self._guard:
            self._connections[context.connection_id] = ProfileConnection(
                context,
                login,
                uuid4(),
                request.profile_id,
                OperationFrontendProjection.INSTALLED_SERVICE,
                method="service",
                requested_scope=descriptor.operation_scope,
            )
            self._logins[login.login_id] = login
            self._services[context.connection_id] = ServiceConnection(descriptor, peer, channel)
        return ServiceConnected(
            request_id=request.request_id,
            runtime_boot_id=self.boot,
            connection_id=context.connection_id,
            profile_id=request.profile_id,
            service_id=request.service_id,
        )

    def service(
        self: RuntimeProfileConnections,
        context: ConnectionContext,
        channel: ByteChannel,
        request: ServiceConnect | ServiceAdmission | ServiceAdmissionStatusQuery,
    ):
        """Register a verified peer or approve it from an exact live human session."""
        if isinstance(request, ServiceAdmissionStatusQuery):
            return self._service_admission_status(context, request)
        if isinstance(request, ServiceAdmission):
            return self._begin_service_admission(context, request)
        descriptor = self._service_descriptors.get(request.service_id)
        if descriptor is None:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED, check="service_descriptor_unknown")
        with self._guard:
            existing = self._services.get(context.connection_id)
            connection = self._connections.get(context.connection_id)
            host = self._profiles.get(request.profile_id) if existing is not None else None
        # A registered connection proves its admitted incarnation; only a new one hashes the image.
        if existing is None:
            peer = self._service_verifier.verify_service(context, channel, descriptor)
        elif self._service_verifier.recheck_service(context, channel, existing.peer):
            peer = existing.peer
        else:
            peer = None
        if peer is None:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED, check="service_verification_failed")
        if existing is not None:
            return self._reattach_service(context, request, descriptor, existing, connection, host)
        return self._register_service(context, channel, request, descriptor, peer, connection)

    def _begin_service_admission(
        self: RuntimeProfileConnections, context: ConnectionContext, request: ServiceAdmission
    ):
        holder = self._connected(context.connection_id)
        if (
            holder.context != context
            or holder.profile_id != request.profile_id
            or holder.session_id != request.session_id
            or not is_persons_frontend(holder.frontend)
        ):
            return AccessDenied(code=AccessDenialCode.HUMAN_AUTHORITY_REQUIRED)
        with self._guard:
            if self._closed:
                return AccessDenied(code=AccessDenialCode.RUNTIME_CHANGED)
            # One pending admission per human connection, and bounded work for
            # the runtime as a whole. A busy answer did not start any mutation.
            if any(
                item.context.connection_id == context.connection_id and item.active()
                for item in self._service_admissions.values()
            ):
                return AccessDenied(code=AccessDenialCode.SUBJECT_BUSY)
            if len(self._service_admissions) >= 32:
                return AccessDenied(code=AccessDenialCode.SUBJECT_BUSY)
            pending = PendingServiceAdmission(uuid4(), context, request)
            self._service_admissions[pending.admission_id] = pending
        self._start_service_admission_jobs()
        return pending_service_reply(self.boot, pending, request.request_id)

    def _start_service_admission_jobs(self: RuntimeProfileConnections) -> None:
        """Take available verification slots; their completions dispatch queued work."""
        while True:
            with self._guard:
                if self._closed:
                    return
                pending = next(
                    (item for item in self._service_admissions.values() if not item.started and item.active()), None
                )
                if pending is None or not self._service_admission_slots.acquire(blocking=False):
                    return
                pending.started = True
            try:
                Thread(
                    target=self._verify_pending_service_admission,
                    args=(pending,),
                    name="service-admission",
                    daemon=True,
                ).start()
            except BaseException:
                with self._guard:
                    self._service_admissions.pop(pending.admission_id, None)
                self._service_admission_slots.release()
                raise

    def _verify_pending_service_admission(self: RuntimeProfileConnections, pending: PendingServiceAdmission) -> None:
        context, request = pending.context, pending.request
        try:
            result = self._admit_service(context, request, pending=pending)
        except Exception:
            result = AccessDenied(code=AccessDenialCode.AUTHORITY_UNAVAILABLE)
        with self._guard:
            pending.complete = True
            pending.result = result
            if not pending.active() or self._closed:
                self._service_admissions.pop(pending.admission_id, None)
        self._service_admission_slots.release()
        self._events.publish_cue(
            ServiceAdmissionChanged(
                runtime_boot_id=self.boot,
                connection_id=context.connection_id,
                profile_id=request.profile_id,
                session_id=request.session_id,
            )
        )
        self._start_service_admission_jobs()

    def _completed_admission_result(
        self: RuntimeProfileConnections,
        request: ServiceAdmissionStatusQuery,
        result: ServiceConnected | AccessDenied | None,
    ) -> ServiceConnected | AccessDenied:
        if isinstance(result, ServiceConnected):
            service = self._services.get(request.recipient_connection_id)
            if service is None or service.lease != result.lease:
                return AccessDenied(code=AccessDenialCode.CONNECTION_MISMATCH)
            return result.model_copy(update={"request_id": request.request_id})
        return result or AccessDenied(code=AccessDenialCode.AUTHORITY_UNAVAILABLE)

    def _service_admission_status(
        self: RuntimeProfileConnections, context: ConnectionContext, request: ServiceAdmissionStatusQuery
    ):
        with self._guard:
            pending = self._service_admissions.get(request.admission_id)
            holder = self._connections.get(context.connection_id)
            if pending is None or not admission_status_matches(pending, holder, context, request):
                return AccessDenied(code=AccessDenialCode.CONNECTION_MISMATCH)
            host = self._profiles.get(request.profile_id)
        if host is None:
            return AccessDenied(code=AccessDenialCode.CONNECTION_MISMATCH)
        with host.guard:
            # A queued or completed result belongs to the exact still-live
            # authority, never merely to someone holding its nonsecret id.
            host.authority.human_administration_facts(
                connection_id=context.connection_id, session_id=request.session_id
            )
            with self._guard:
                if not pending.active() or self._service_admissions.get(request.admission_id) is not pending:
                    return AccessDenied(code=AccessDenialCode.CONNECTION_MISMATCH)
                if request.action == "service_admission_cancel":
                    return cancel_pending_status(self._service_admissions, self.boot, pending, request)
                if not pending.complete:
                    return pending_service_reply(self.boot, pending, request.request_id)
                self._service_admissions.pop(request.admission_id, None)
                result = pending.result
            return self._completed_admission_result(request, result)

    def _cancel_service_admissions(
        self: RuntimeProfileConnections, connection_id: UUID | None = None, session_id: UUID | None = None
    ) -> None:
        """Fence late verification after either peer or its exact parent ends."""
        with self._guard:
            cancel_service_admissions(self._service_admissions, connection_id, session_id)

    def _admission_holder_changed(
        self: RuntimeProfileConnections,
        holder: ProfileConnection,
        context: ConnectionContext,
        request: ServiceAdmission,
        pending: PendingServiceAdmission | None,
    ) -> bool:
        return (
            self._closed
            or self._connections.get(context.connection_id) is not holder
            or holder.disconnecting
            or not person_holder_matches(holder, context, request)
            or (
                pending is not None
                and (pending.cancelled or self._service_admissions.get(pending.admission_id) is not pending)
            )
        )

    def _admission_recipient_changed(
        self: RuntimeProfileConnections,
        service: ServiceConnection,
        recipient: ProfileConnection,
        host: RuntimeProfileHost,
        request: ServiceAdmission,
    ) -> bool:
        return (
            self._services.get(request.recipient_connection_id) is not service
            or self._connections.get(request.recipient_connection_id) is not recipient
            or self._profiles.get(request.profile_id) is not host
            or recipient.disconnecting
            or recipient.profile_id != request.profile_id
            or service.lease is not None
        )

    def _commit_service_admission(
        self: RuntimeProfileConnections,
        context: ConnectionContext,
        request: ServiceAdmission,
        holder: ProfileConnection,
        recipient: ProfileConnection,
        host: RuntimeProfileHost,
        service: ServiceConnection,
        pending: PendingServiceAdmission | None,
    ) -> ServiceConnected | AccessDenied:
        host.authority.human_administration_facts(connection_id=context.connection_id, session_id=request.session_id)
        recipient.client_id = holder.client_id
        child = host.authority.attend(
            connection_id=context.connection_id,
            parent_session_id=request.session_id,
            recipient_connection_id=request.recipient_connection_id,
            scope=service.descriptor.operation_scope,
        )
        if isinstance(child, AccessDenied):
            return child
        recipient.session_id = child.session_id
        service.lease = ServiceLease(
            lease_id=uuid4(),
            session_id=child.session_id,
            profile_id=request.profile_id,
            parent_session_id=request.session_id,
            descriptor_digest=service.descriptor.descriptor_digest,
            service_id=request.service_id,
            runtime_boot_id=self.boot,
            connection_id=request.recipient_connection_id,
        )
        # The service learns of its lease by claiming again; this only tells it to.
        self._events.publish_cue(
            ServiceLeaseChanged(
                runtime_boot_id=self.boot,
                connection_id=request.recipient_connection_id,
                profile_id=request.profile_id,
            )
        )
        result = ServiceConnected(
            request_id=request.request_id,
            runtime_boot_id=self.boot,
            connection_id=context.connection_id,
            profile_id=request.profile_id,
            service_id=request.service_id,
            lease=service.lease,
        )
        if pending is not None:
            with self._guard:
                pending.result = result
                pending.complete = True
        return result

    def _admit_service(
        self: RuntimeProfileConnections,
        context: ConnectionContext,
        request: ServiceAdmission,
        *,
        pending: PendingServiceAdmission | None = None,
    ):
        holder = self._connected(context.connection_id)
        if not person_holder_matches(holder, context, request):
            return AccessDenied(code=AccessDenialCode.HUMAN_AUTHORITY_REQUIRED)
        with self._guard:
            service = self._services.get(request.recipient_connection_id)
            recipient = self._connections.get(request.recipient_connection_id)
            host = self._profiles.get(request.profile_id)
        if service is None or recipient is None or host is None or service.descriptor.service_id != request.service_id:
            return AccessDenied(code=AccessDenialCode.CONNECTION_MISMATCH)
        # Native process inspection can stall; it must not fence unrelated profile work.
        if not self._service_verifier.recheck_service(recipient.context, service.channel, service.peer):
            return AccessDenied(code=AccessDenialCode.CONNECTION_MISMATCH)
        with host.guard:
            with self._guard:
                if self._admission_holder_changed(holder, context, request, pending):
                    return AccessDenied(code=AccessDenialCode.HUMAN_AUTHORITY_REQUIRED)
                if self._admission_recipient_changed(service, recipient, host, request):
                    return AccessDenied(code=AccessDenialCode.CONNECTION_MISMATCH)
            return self._commit_service_admission(context, request, holder, recipient, host, service, pending)

    def _service_tree_owner(
        self: RuntimeProfileConnections, context: ConnectionContext, channel: ByteChannel
    ) -> ServiceConnection | None:
        with self._guard:
            services = tuple(self._services.values())
        for service in services:
            if service.descriptor.allow_descendants and self._service_verifier.verify_descendant(
                context, channel, service.peer, service.peer.connection_id
            ):
                return service
        return None

    def _human_parent_connection(self: RuntimeProfileConnections, lease: ServiceLease) -> UUID:
        with self._guard:
            holder = next(
                (
                    item
                    for item in self._connections.values()
                    if item.profile_id == lease.profile_id and item.session_id == lease.parent_session_id
                ),
                None,
            )
        if holder is None:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED, check="human_parent_connection_absent")
        return holder.context.connection_id

    def _verify_desktop_holder(
        self: RuntimeProfileConnections, context: ConnectionContext, channel: ByteChannel, request: ProfileLogin
    ) -> None:
        verify_desktop_holder(
            context,
            channel,
            request,
            self._service_descriptors.get("desktop-session"),
            self.root,
            self.storage_identity,
            self._service_verifier,
        )

    def _nonhuman_peer(self: RuntimeProfileConnections, context, channel) -> bool:
        if self._service_tree_owner(context, channel) is not None:
            return True
        return any(
            descriptor.service_id != "desktop-session"
            and self._service_verifier.verify_service(context, channel, descriptor) is not None
            for descriptor in self._service_descriptors.values()
        )
