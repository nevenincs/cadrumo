"""Descriptor-allowlisted opaque record exchanges under the profile lifecycle fence."""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING

from cadrumo_client.contracts.contracts import ByteChannel
from cadrumo_client.contracts.extension_records import (
    ExtensionRecordRefusal,
    ExtensionRecordReply,
    ExtensionRecordRequest,
    ProfileWorkerExtensionRecordRequest,
)
from cadrumo_client.contracts.profile_access import ProfileStatus, SecretReady
from cadrumo_client.contracts.transport import ConnectionContext
from cadrumo_client.transport.frame_io import read_secret, write_document, write_secret

if TYPE_CHECKING:
    from .profile_connections import RuntimeProfileConnections


class ProfileConnectionExtensionRecordsMixin:
    """Serve lease-bound extension-record operations on profile connections."""

    def extension_record(
        self: RuntimeProfileConnections,
        context: ConnectionContext,
        channel: ByteChannel,
        request: ExtensionRecordRequest,
    ) -> None:
        """Read, write, delete, or report a record generation for one request."""
        material = bytearray()
        payload = bytearray()
        deadline = time.monotonic() + 10
        refusal = ExtensionRecordRefusal.LEASE_INACTIVE
        try:
            with self._guard:
                service = self._services.get(context.connection_id)
                connection = self._connections.get(context.connection_id)
                host = self._profiles.get(request.profile_id)
            if service is None or connection is None or host is None or service.lease is None:
                return self._extension_refused(context, request, channel, refusal)
            lease = service.lease
            if (
                connection.context != context
                or lease.runtime_boot_id != self.boot
                or lease.profile_id != request.profile_id
                or lease.session_id != request.session_id
                or lease.lease_id != request.lease_id
                or connection.session_id != request.session_id
            ):
                return self._extension_refused(context, request, channel, refusal)
            policy = next(
                (item for item in service.descriptor.record_capabilities if item.capability == request.capability), None
            )
            action = request.action.removeprefix("extension_record_")
            if policy is None or action not in policy.actions:
                return self._extension_refused(context, request, channel, ExtensionRecordRefusal.CAPABILITY_DENIED)
            if (request.object_key is not None and re.fullmatch(policy.key_pattern, request.object_key) is None) or (
                request.byte_count is not None and request.byte_count > policy.maximum_bytes
            ):
                return self._extension_refused(context, request, channel, ExtensionRecordRefusal.INVALID)
            with host.guard:
                status = self._status(connection, host, request.request_id, request.session_id)
                if not isinstance(status, ProfileStatus) or status.status.denial is not None:
                    return self._extension_refused(context, request, channel, refusal)
                if self._service_verifier.verify_service(context, channel, service.descriptor) != service.peer:
                    return self._extension_refused(context, request, channel, refusal)
                if action == "write":
                    write_document(
                        channel,
                        SecretReady(
                            request_id=request.request_id,
                            runtime_boot_id=self.boot,
                            connection_id=context.connection_id,
                        ),
                        deadline=deadline,
                    )
            # Slow input never keeps profile retirement or locking behind its socket.
            if action == "write":
                with read_secret(channel, deadline=deadline) as incoming:
                    if len(incoming) != request.byte_count:
                        return self._extension_refused(context, request, channel, ExtensionRecordRefusal.INVALID)
                    payload.extend(incoming)
            with host.guard:
                status = self._status(connection, host, request.request_id, request.session_id)
                if (
                    not isinstance(status, ProfileStatus)
                    or status.status.denial is not None
                    or service.lease != lease
                    or self._service_verifier.verify_service(context, channel, service.descriptor) != service.peer
                ):
                    return self._extension_refused(context, request, channel, refusal)
                result, material = host.owner.extension_record(
                    ProfileWorkerExtensionRecordRequest(request_id=request.request_id, request=request, policy=policy),
                    payload if action == "write" else None,
                )
                status = self._status(connection, host, request.request_id, request.session_id)
                if not isinstance(status, ProfileStatus) or status.status.denial is not None:
                    return self._extension_refused(
                        context,
                        request,
                        channel,
                        ExtensionRecordRefusal.OUTCOME_UNKNOWN if action in {"write", "delete"} else refusal,
                    )
                write_document(channel, result, deadline=deadline)
                if material:
                    write_secret(channel, material, deadline=deadline)
        finally:
            material[:] = bytes(len(material))
            payload[:] = bytes(len(payload))

    def _extension_refused(self: RuntimeProfileConnections, context, request, channel, refusal) -> None:
        write_document(
            channel,
            ExtensionRecordReply(
                request_id=request.request_id,
                runtime_boot_id=self.boot,
                connection_id=context.connection_id,
                state="refused",
                refusal=refusal,
            ),
            deadline=time.monotonic() + 5,
        )
