"""Human-approved installed service leases on verified native connections."""

from __future__ import annotations

import os
from dataclasses import dataclass
from threading import Thread
from typing import TYPE_CHECKING, Protocol
from uuid import UUID, uuid4

from cadrumo.application.operations.person_acts import is_persons_frontend
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo_client.contracts.access_refusals import AccessDenialCode, AccessDenied
from cadrumo_client.contracts.access_vocabulary import Availability
from cadrumo_client.contracts.contracts import ByteChannel, Peer, RefusalCode, RefusalError
from cadrumo_client.contracts.service_access import (
    InstalledServiceDescriptor,
    ServiceAdmission,
    ServiceAdmissionPending,
    ServiceAdmissionStatusQuery,
    ServiceConnect,
    ServiceConnected,
    ServiceLease,
    VerifiedServicePeer,
)
from cadrumo_client.contracts.session_events import ServiceAdmissionChanged, ServiceLeaseChanged
from cadrumo_client.contracts.transport import ConnectionContext

from .profile_host import ProfileConnection

if TYPE_CHECKING:
    from ..adapters.service_verification import NativeProcessIdentity
    from .profile_connections import RuntimeProfileConnections

_MAXIMUM_ANCESTRY_DEPTH = 32


# The argument that starts the desktop image as one of its roles; the window has none.
_ROLE_ARGUMENT = "--role"


class DesktopImageMatcher(Protocol):
    """The one verifier question a desktop window's admission asks."""

    def installed_parent_image_matches(self, image_path: str, descriptor_path: str, image_digest: str) -> bool:
        """Whether ``image_path`` is the package's ``descriptor_path`` image with ``image_digest``."""
        ...


def desktop_window_peer(
    verifier: DesktopImageMatcher,
    context: ConnectionContext,
    channel_peer: Peer,
    descriptor: InstalledServiceDescriptor,
) -> bool:
    """Whether the peer is the installed desktop image itself, connected from its window.

    The desktop window holds its own runtime connection. It is admitted as the
    desktop holder on the same evidence its hold child's parent was: the peer
    runs one of the images the package names as a desktop, by exact bytes, and
    was not started by this runtime. A role argument makes the image one of the
    runtime's own children, never the window.
    """
    from pathlib import Path

    from ..adapters.service_verification import native_process_arguments, native_process_identity

    pid, owner = context.peer.process_id, context.peer.os_owner_id
    if pid is None or context.peer != channel_peer or not descriptor.allowed_parent_images:
        return False
    try:
        identity = native_process_identity(pid, owner)
        image = channel_peer.image_path
        if image is None or Path(image).resolve() != Path(identity.image).resolve():
            return False
        if not any(
            verifier.installed_parent_image_matches(identity.image, item.launch_image, item.image_digest)
            for item in descriptor.allowed_parent_images
        ):
            return False
        if native_process_arguments(pid, owner)[:1] == (_ROLE_ARGUMENT,):
            return False
        if _descends_from_this_runtime(identity, owner):
            return False
        return native_process_identity(pid, owner) == identity
    except (RefusalError, OSError):
        return False


def _descends_from_this_runtime(process: NativeProcessIdentity, owner: str) -> bool:
    """Whether this runtime started ``process``, directly or through its own children.

    The runtime's workers run the same image as the desktop, so a desktop holder must not
    trace back to this process. A chain that ends, leaves the owner, or reaches a parent born
    after its child (a reused id) no longer leads back here; one too deep to follow is refused.
    """
    from ..adapters.service_verification import native_process_identity

    runtime = os.getpid()
    current = process
    for _ in range(_MAXIMUM_ANCESTRY_DEPTH):
        if current.pid == runtime:
            return True
        if current.parent_pid in (0, current.pid):
            return False
        try:
            parent = native_process_identity(current.parent_pid, owner)
        except (RefusalError, OSError):
            return False
        if parent.born > current.born:
            return False
        current = parent
    return True


@dataclass(slots=True)
class ServiceConnection:
    """Retain a verified service peer, channel, descriptor, and optional lease."""

    descriptor: InstalledServiceDescriptor
    peer: VerifiedServicePeer
    channel: ByteChannel
    lease: ServiceLease | None = None
    # Model-run disclosures being written under the lease; withdrawing it waits for them.
    disclosing: int = 0


@dataclass(slots=True)
class PendingServiceAdmission:
    """One retained verification job; its handle grants no authority."""

    admission_id: UUID
    context: ConnectionContext
    request: ServiceAdmission
    cancelled: bool = False
    started: bool = False
    complete: bool = False
    result: ServiceConnected | AccessDenied | None = None

    def active(self) -> bool:
        """Read cancellation afresh after work that can run beside the owner."""
        return not self.cancelled


class ProfileConnectionServicesMixin:
    """Handle installed-service connections owned by the runtime profile host."""

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
                    if (
                        existing.lease is lease
                        and denial is not None
                        and denial is not AccessDenialCode.CUSTODY_RECOVERING
                    ):
                        approved = lease
                        try:
                            holder_id = self._human_parent_connection(approved)
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
                return ServiceConnected(
                    request_id=request.request_id,
                    runtime_boot_id=self.boot,
                    connection_id=context.connection_id,
                    profile_id=request.profile_id,
                    service_id=request.service_id,
                    lease=existing.lease,
                )
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
        return self._pending_service_reply(pending, request.request_id)

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

    def _pending_service_reply(self: RuntimeProfileConnections, pending: PendingServiceAdmission, request_id: UUID):
        return ServiceAdmissionPending(
            request_id=request_id,
            runtime_boot_id=self.boot,
            connection_id=pending.context.connection_id,
            profile_id=pending.request.profile_id,
            service_id=pending.request.service_id,
            admission_id=pending.admission_id,
        )

    def _service_admission_status(
        self: RuntimeProfileConnections, context: ConnectionContext, request: ServiceAdmissionStatusQuery
    ):
        with self._guard:
            pending = self._service_admissions.get(request.admission_id)
            holder = self._connections.get(context.connection_id)
            if (
                pending is None
                or not pending.active()
                or pending.context != context
                or pending.request.profile_id != request.profile_id
                or pending.request.session_id != request.session_id
                or pending.request.recipient_connection_id != request.recipient_connection_id
                or pending.request.service_id != request.service_id
                or holder is None
                or holder.session_id != request.session_id
                or holder.disconnecting
            ):
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
                    if isinstance(pending.result, ServiceConnected):
                        self._service_admissions.pop(request.admission_id, None)
                        return pending.result.model_copy(update={"request_id": request.request_id})
                    pending.cancelled = True
                    if pending.complete or not pending.started:
                        self._service_admissions.pop(request.admission_id, None)
                    return self._pending_service_reply(pending, request.request_id).model_copy(
                        update={"cancelled": True}
                    )
                if not pending.complete:
                    return self._pending_service_reply(pending, request.request_id)
                self._service_admissions.pop(request.admission_id, None)
                result = pending.result
            if isinstance(result, ServiceConnected):
                service = self._services.get(request.recipient_connection_id)
                if service is None or service.lease != result.lease:
                    return AccessDenied(code=AccessDenialCode.CONNECTION_MISMATCH)
                return result.model_copy(update={"request_id": request.request_id})
            return result or AccessDenied(code=AccessDenialCode.AUTHORITY_UNAVAILABLE)

    def _cancel_service_admissions(
        self: RuntimeProfileConnections, connection_id: UUID | None = None, session_id: UUID | None = None
    ) -> None:
        """Fence late verification after either peer or its exact parent ends."""
        with self._guard:
            for admission_id, pending in tuple(self._service_admissions.items()):
                if (
                    connection_id is None
                    or pending.context.connection_id == connection_id
                    or pending.request.recipient_connection_id == connection_id
                    or (session_id is not None and pending.request.session_id == session_id)
                ):
                    pending.cancelled = True
                    if pending.complete or not pending.started:
                        self._service_admissions.pop(admission_id, None)

    def _admit_service(
        self: RuntimeProfileConnections,
        context: ConnectionContext,
        request: ServiceAdmission,
        *,
        pending: PendingServiceAdmission | None = None,
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
                if (
                    self._closed
                    or self._connections.get(context.connection_id) is not holder
                    or holder.disconnecting
                    or holder.context != context
                    or holder.profile_id != request.profile_id
                    or holder.session_id != request.session_id
                    or not is_persons_frontend(holder.frontend)
                    or (
                        pending is not None
                        and (pending.cancelled or self._service_admissions.get(pending.admission_id) is not pending)
                    )
                ):
                    return AccessDenied(code=AccessDenialCode.HUMAN_AUTHORITY_REQUIRED)
                if (
                    self._services.get(request.recipient_connection_id) is not service
                    or self._connections.get(request.recipient_connection_id) is not recipient
                    or self._profiles.get(request.profile_id) is not host
                    or recipient.disconnecting
                    or recipient.profile_id != request.profile_id
                    or service.lease is not None
                ):
                    return AccessDenied(code=AccessDenialCode.CONNECTION_MISMATCH)
            host.authority.human_administration_facts(
                connection_id=context.connection_id, session_id=request.session_id
            )
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
            raise RefusalError(RefusalCode.PEER_UNTRUSTED, check="desktop_holder_descriptor_absent")
        if self._desktop_window_peer(context, channel, descriptor):
            return
        if self._service_verifier.verify_service(context, channel, descriptor) is None:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED, check="desktop_holder_unverified")
        child = native_process_identity(context.peer.process_id, context.peer.os_owner_id)
        if development_password:
            return
        parent = native_process_identity(child.parent_pid, context.peer.os_owner_id)
        if parent.born > child.born:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED, check="desktop_holder_parent_born_after_child")
        if not any(
            self._service_verifier.installed_parent_image_matches(parent.image, item.launch_image, item.image_digest)
            for item in descriptor.allowed_parent_images
        ):
            raise RefusalError(RefusalCode.PEER_UNTRUSTED, check="desktop_holder_parent_image_unlisted")
        if native_process_identity(parent.pid, context.peer.os_owner_id) != parent:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED, check="desktop_holder_parent_identity_changed")
        if _descends_from_this_runtime(parent, context.peer.os_owner_id):
            raise RefusalError(RefusalCode.PEER_UNTRUSTED, check="desktop_holder_started_by_runtime")

    def _desktop_window_peer(self: RuntimeProfileConnections, context, channel, descriptor) -> bool:
        return desktop_window_peer(self._service_verifier, context, channel.peer, descriptor)

    def _nonhuman_peer(self: RuntimeProfileConnections, context, channel) -> bool:
        if self._service_tree_owner(context, channel) is not None:
            return True
        return any(
            descriptor.service_id != "desktop-session"
            and self._service_verifier.verify_service(context, channel, descriptor) is not None
            for descriptor in self._service_descriptors.values()
        )
