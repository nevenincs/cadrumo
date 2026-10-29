"""Descriptor-allowlisted opaque record exchanges under the profile lifecycle fence."""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from cadrumo_client.contracts.access_refusals import AccessDenied
from cadrumo_client.contracts.contracts import ByteChannel
from cadrumo_client.contracts.extension_records import (
    ExtensionRecordCapability,
    ExtensionRecordRefusal,
    ExtensionRecordReply,
    ExtensionRecordRequest,
    ProfileWorkerExtensionRecordRequest,
)
from cadrumo_client.contracts.profile_access import ProfileStatus, SecretReady
from cadrumo_client.contracts.service_access import ServiceLease
from cadrumo_client.contracts.transport import ConnectionContext
from cadrumo_client.transport.frame_io import read_secret, write_document, write_secret

from .profile_connection import ProfileConnection
from .profile_host import RuntimeProfileHost
from .service_connection_records import ServiceConnection

if TYPE_CHECKING:
    from .profile_connections import RuntimeProfileConnections

# Both budgets start when their frames are due, never at dispatch: the client
# controls only its own input, and queueing for a fence or a worker is not its time.
_CLIENT_INPUT_SECONDS = 10
_REPLY_WRITE_SECONDS = 5


def extension_lease_matches(
    context: ConnectionContext,
    request: ExtensionRecordRequest,
    boot: UUID,
    connection: ProfileConnection,
    lease: ServiceLease,
) -> bool:
    """Check every bound lease coordinate before inspecting its policy."""
    return (
        connection.context == context
        and lease.runtime_boot_id == boot
        and lease.profile_id == request.profile_id
        and lease.session_id == request.session_id
        and lease.lease_id == request.lease_id
        and connection.session_id == request.session_id
    )


def extension_payload_matches(request: ExtensionRecordRequest, policy: ExtensionRecordCapability) -> bool:
    """Validate the installed key and byte restrictions."""
    return (request.object_key is None or re.fullmatch(policy.key_pattern, request.object_key) is not None) and (
        request.byte_count is None or request.byte_count <= policy.maximum_bytes
    )


def extension_current(
    closed: bool,
    current_service: ServiceConnection | None,
    service: ServiceConnection,
    current_connection: ProfileConnection | None,
    connection: ProfileConnection,
    current_host: RuntimeProfileHost | None,
    host: RuntimeProfileHost,
    lease: ServiceLease,
    session_id: UUID,
) -> bool:
    """Recheck the same live owners while the connection guard is held."""
    return (
        not closed
        and current_service is service
        and current_connection is connection
        and current_host is host
        and not connection.disconnecting
        and service.lease is lease
        and connection.session_id == session_id
    )


def extension_status_active(
    status: ProfileStatus | AccessDenied, service: ServiceConnection, lease: ServiceLease
) -> bool:
    """Require both current session authority and the same service lease."""
    return isinstance(status, ProfileStatus) and status.status.denial is None and service.lease is lease


def extension_policy(
    service: ServiceConnection, request: ExtensionRecordRequest, action: str
) -> tuple[ExtensionRecordCapability | None, ExtensionRecordRefusal]:
    """Find the installed capability and check its action and payload bounds."""
    policy = next(
        (item for item in service.descriptor.record_capabilities if item.capability == request.capability), None
    )
    if policy is None or action not in policy.actions:
        return None, ExtensionRecordRefusal.CAPABILITY_DENIED
    if not extension_payload_matches(request, policy):
        return None, ExtensionRecordRefusal.INVALID
    return policy, ExtensionRecordRefusal.LEASE_INACTIVE


@dataclass(slots=True)
class ExtensionExchange:
    """One already validated record request and its fresh authority checks."""

    context: ConnectionContext
    channel: ByteChannel
    request: ExtensionRecordRequest
    host: RuntimeProfileHost
    service: ServiceConnection
    lease: ServiceLease
    policy: ExtensionRecordCapability
    boot: UUID
    current: Callable[[], bool]
    status: Callable[[], ProfileStatus | AccessDenied]
    recheck: Callable[[], bool]
    refuse: Callable[[ExtensionRecordRefusal], None]

    def active(self) -> bool:
        """Check the current connection and then its session authority."""
        return self.current() and extension_status_active(self.status(), self.service, self.lease)


def read_extension_input(exchange: ExtensionExchange, payload: bytearray) -> bool:
    """Authorize a write, then read its input outside the profile fence."""
    if not exchange.recheck():
        exchange.refuse(ExtensionRecordRefusal.LEASE_INACTIVE)
        return False
    with exchange.host.guard:
        if not exchange.active():
            exchange.refuse(ExtensionRecordRefusal.LEASE_INACTIVE)
            return False
        deadline = time.monotonic() + _CLIENT_INPUT_SECONDS
        write_document(
            exchange.channel,
            SecretReady(
                request_id=exchange.request.request_id,
                runtime_boot_id=exchange.boot,
                connection_id=exchange.context.connection_id,
            ),
            deadline=deadline,
        )
    with read_secret(exchange.channel, deadline=deadline) as incoming:
        if len(incoming) != exchange.request.byte_count:
            exchange.refuse(ExtensionRecordRefusal.INVALID)
            return False
        payload.extend(incoming)
    return True


def run_extension_exchange(exchange: ExtensionExchange, payload: bytearray, action: str) -> None:
    """Execute and publish while the exact profile and lease stay fenced."""
    if not exchange.recheck():
        exchange.refuse(ExtensionRecordRefusal.LEASE_INACTIVE)
        return
    material = bytearray()
    try:
        with exchange.host.guard:
            if not exchange.active():
                exchange.refuse(ExtensionRecordRefusal.LEASE_INACTIVE)
                return
            result, material = exchange.host.owner.extension_record(
                ProfileWorkerExtensionRecordRequest(
                    request_id=exchange.request.request_id, request=exchange.request, policy=exchange.policy
                ),
                payload if action == "write" else None,
            )
            status = exchange.status()
            if not isinstance(status, ProfileStatus) or status.status.denial is not None:
                exchange.refuse(
                    ExtensionRecordRefusal.OUTCOME_UNKNOWN
                    if action in {"write", "delete"}
                    else ExtensionRecordRefusal.LEASE_INACTIVE
                )
                return
            deadline = time.monotonic() + _REPLY_WRITE_SECONDS
            write_document(exchange.channel, result, deadline=deadline)
            if material:
                write_secret(exchange.channel, material, deadline=deadline)
    finally:
        material[:] = bytes(len(material))


class ProfileConnectionExtensionRecordsMixin:
    """Serve lease-bound extension-record operations on profile connections."""

    def extension_record(
        self: RuntimeProfileConnections,
        context: ConnectionContext,
        channel: ByteChannel,
        request: ExtensionRecordRequest,
    ) -> None:
        """Read, write, delete, or report a record generation for one request."""
        payload = bytearray()
        refusal = ExtensionRecordRefusal.LEASE_INACTIVE
        try:
            with self._guard:
                service = self._services.get(context.connection_id)
                connection = self._connections.get(context.connection_id)
                host = self._profiles.get(request.profile_id)
            if service is None or connection is None or host is None or service.lease is None:
                return self._extension_refused(context, request, channel, refusal)
            lease = service.lease
            if not extension_lease_matches(context, request, self.boot, connection, lease):
                return self._extension_refused(context, request, channel, refusal)
            action = request.action.removeprefix("extension_record_")
            policy, policy_refusal = extension_policy(service, request, action)
            if policy is None:
                return self._extension_refused(context, request, channel, policy_refusal)

            def current() -> bool:
                with self._guard:
                    return extension_current(
                        self._closed,
                        self._services.get(context.connection_id),
                        service,
                        self._connections.get(context.connection_id),
                        connection,
                        self._profiles.get(request.profile_id),
                        host,
                        lease,
                        request.session_id,
                    )

            exchange = ExtensionExchange(
                context=context,
                channel=channel,
                request=request,
                host=host,
                service=service,
                lease=lease,
                policy=policy,
                boot=self.boot,
                current=current,
                status=lambda: self._status(connection, host, request.request_id, request.session_id),
                recheck=lambda: self._service_verifier.recheck_service(context, channel, service.peer),
                refuse=lambda reason: self._extension_refused(context, request, channel, reason),
            )
            if action == "write" and not read_extension_input(exchange, payload):
                return
            run_extension_exchange(exchange, payload, action)
        finally:
            payload[:] = bytes(len(payload))

    def _extension_refused(
        self: RuntimeProfileConnections,
        context: ConnectionContext,
        request: ExtensionRecordRequest,
        channel: ByteChannel,
        refusal: ExtensionRecordRefusal,
    ) -> None:
        write_document(
            channel,
            ExtensionRecordReply(
                request_id=request.request_id,
                runtime_boot_id=self.boot,
                connection_id=context.connection_id,
                state="refused",
                refusal=refusal,
            ),
            deadline=time.monotonic() + _REPLY_WRITE_SECONDS,
        )
