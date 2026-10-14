"""Human-approved installed service leases on verified native connections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from cadrumo.application.operations.person_acts import is_persons_frontend
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import AccessDenialCode, AccessDenied, Availability
from cadrumo_client.contracts.contracts import ByteChannel, RefusalCode, RefusalError
from cadrumo_client.contracts.service_access import (
    InstalledServiceDescriptor,
    ServiceAdmission,
    ServiceConnect,
    ServiceConnected,
    ServiceLease,
    VerifiedServicePeer,
)
from cadrumo_client.contracts.transport import ConnectionContext

from .profile_host import ProfileConnection

if TYPE_CHECKING:
    from .profile_connections import RuntimeProfileConnections


@dataclass(slots=True)
class ServiceConnection:
    """Retain a verified service peer, channel, descriptor, and optional lease."""

    descriptor: InstalledServiceDescriptor
    peer: VerifiedServicePeer
    channel: ByteChannel
    lease: ServiceLease | None = None


class ProfileConnectionServicesMixin:
    """Handle installed-service connections owned by the runtime profile host."""

    def service(
        self: RuntimeProfileConnections,
        context: ConnectionContext,
        channel: ByteChannel,
        request: ServiceConnect | ServiceAdmission,
    ):
        """Register a verified peer or approve it from an exact live human session."""
        if isinstance(request, ServiceAdmission):
            return self._admit_service(context, request)
        descriptor = self._service_descriptors.get(request.service_id)
        if descriptor is None:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED)
        peer = self._service_verifier.verify_service(context, channel, descriptor)
        if peer is None:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED)
        with self._guard:
            existing = self._services.get(context.connection_id)
            connection = self._connections.get(context.connection_id)
        if existing is not None:
            if existing.peer != peer or connection is None or connection.profile_id != request.profile_id:
                raise RefusalError(RefusalCode.PEER_UNTRUSTED)
            if existing.lease is not None:
                with self._profiles[request.profile_id].guard:
                    status = self._status(
                        connection, self._profiles[request.profile_id], request.request_id, existing.lease.session_id
                    )
                    if isinstance(status, AccessDenied) or status.status.denial is not None:
                        approved = existing.lease
                        try:
                            holder_id = self._human_parent_connection(approved)
                            host = self._profiles[request.profile_id]
                            host.authority.human_administration_facts(
                                connection_id=holder_id, session_id=approved.parent_session_id
                            )
                            child = host.authority.attend(
                                connection_id=holder_id,
                                parent_session_id=approved.parent_session_id,
                                recipient_connection_id=context.connection_id,
                                scope=existing.descriptor.operation_scope,
                            )
                        except Exception:
                            existing.lease = None
                        else:
                            if isinstance(child, AccessDenied):
                                existing.lease = None
                            else:
                                connection.session_id = child.session_id
                                existing.lease = approved.model_copy(update={"session_id": child.session_id})
            return ServiceConnected(
                request_id=request.request_id,
                runtime_boot_id=self.boot,
                connection_id=context.connection_id,
                profile_id=request.profile_id,
                service_id=request.service_id,
                lease=existing.lease,
            )
        if connection is not None:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED)
        login = self._capture(channel)
        observed = login.observe(credential_facilities=Availability.UNAVAILABLE)
        if not observed.active or observed.os_owner_id != context.peer.os_owner_id:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED)
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

    def _admit_service(self: RuntimeProfileConnections, context: ConnectionContext, request: ServiceAdmission):
        holder = self._connected(context.connection_id)
        if (
            holder.context != context
            or holder.profile_id != request.profile_id
            or holder.session_id != request.session_id
            or not is_persons_frontend(holder.frontend)
        ):
            return AccessDenied(code=AccessDenialCode.HUMAN_AUTHORITY_REQUIRED)
        with self._guard:
            service = self._services.get(request.recipient_connection_id)
            recipient = self._connections.get(request.recipient_connection_id)
            host = self._profiles.get(request.profile_id)
        if service is None or recipient is None or host is None or service.descriptor.service_id != request.service_id:
            return AccessDenied(code=AccessDenialCode.CONNECTION_MISMATCH)
        with host.guard:
            host.authority.human_administration_facts(
                connection_id=context.connection_id, session_id=request.session_id
            )
            current = self._service_verifier.verify_service(recipient.context, service.channel, service.descriptor)
            if current != service.peer or recipient.profile_id != request.profile_id or service.lease is not None:
                return AccessDenied(code=AccessDenialCode.CONNECTION_MISMATCH)
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
            return ServiceConnected(
                request_id=request.request_id,
                runtime_boot_id=self.boot,
                connection_id=context.connection_id,
                profile_id=request.profile_id,
                service_id=request.service_id,
                lease=service.lease,
            )

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
            raise RefusalError(RefusalCode.PEER_UNTRUSTED)
        return holder.context.connection_id

    def _verify_desktop_holder(self: RuntimeProfileConnections, context, channel, request) -> None:
        from ..adapters.service_verification import native_process_identity
        from ..application.development_root import verify_development_root

        descriptor = self._service_descriptors.get("desktop-session")
        development_password = (
            request.method == "password"
            and not request.persist_receipt
            and verify_development_root(self.root, self.storage_identity)
        )
        if descriptor is None:
            if development_password and context.peer.process_id is not None:
                native_process_identity(context.peer.process_id, context.peer.os_owner_id)
                return
            raise RefusalError(RefusalCode.PEER_UNTRUSTED)
        if self._service_verifier.verify_service(context, channel, descriptor) is None:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED)
        child = native_process_identity(context.peer.process_id, context.peer.os_owner_id)
        if development_password:
            return
        parent = native_process_identity(child.parent_pid, context.peer.os_owner_id)
        if parent.born > child.born:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED)
        if not any(
            self._service_verifier.installed_parent_image_matches(parent.image, item.launch_image, item.image_digest)
            for item in descriptor.allowed_parent_images
        ):
            raise RefusalError(RefusalCode.PEER_UNTRUSTED)
        if native_process_identity(parent.pid, context.peer.os_owner_id) != parent:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED)

    def _nonhuman_peer(self: RuntimeProfileConnections, context, channel) -> bool:
        if self._service_tree_owner(context, channel) is not None:
            return True
        return any(
            descriptor.service_id != "desktop-session"
            and self._service_verifier.verify_service(context, channel, descriptor) is not None
            for descriptor in self._service_descriptors.values()
        )
