"""Verified installed-service access without profile keys or repository handles."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Literal
from uuid import UUID, uuid4

from ..contracts.extension_records import ExtensionRecordRequest
from ..contracts.profile_access import AccessRefusal, SessionRequest
from ..contracts.service_access import ServiceConnect, ServiceConnected, ServiceLease
from .framing import VerifiedConnection
from .frontend_client_contracts import FrontendRefusedError


class InstalledServiceClient:
    """Hold one runtime connection; a person's approval is acquired on that connection."""

    def __init__(self, connection: VerifiedConnection, *, profile_id: UUID, service_id: str) -> None:
        """Bind service operations to one verified connection and identity."""
        self.connection = connection
        self.profile_id, self.service_id = profile_id, service_id
        self.connected: ServiceConnected | None = None
        self.lease: ServiceLease | None = None

    def subscribe_changes(self, changed: Callable[[], None]) -> Callable[[], None]:
        """Call ``changed`` for every frame the runtime pushes on this connection, and when it is lost.

        Everything pushed to a service connection concerns its lease or session:
        an issued or withdrawn lease, or a retired session. ``changed`` is only a
        reason to claim again, never evidence of a lease.
        """
        return self.connection.subscribe_session_events(lambda _event: changed(), disconnected=changed)

    def claim(self) -> ServiceLease | None:
        """Request or refresh the service lease for this profile connection."""
        reply = self.connection.service_access(
            ServiceConnect(request_id=uuid4(), profile_id=self.profile_id, service_id=self.service_id),
            deadline=time.monotonic() + 10,
        )
        if isinstance(reply, AccessRefusal):
            raise FrontendRefusedError(reply.code.value)
        self.connected, self.lease = reply, reply.lease
        return self.lease

    def _request(
        self,
        action: Literal[
            "extension_record_read",
            "extension_record_write",
            "extension_record_delete",
            "extension_record_generation",
        ],
        capability: str,
        **fields,
    ):
        if self.lease is None:
            raise FrontendRefusedError("authentication_required")
        return ExtensionRecordRequest(
            action=action,
            request_id=uuid4(),
            profile_id=self.profile_id,
            session_id=self.lease.session_id,
            lease_id=self.lease.lease_id,
            capability=capability,
            **fields,
        )

    def record_read(self, capability: str, object_key: str):
        """Read one extension record under the current service lease."""
        reply, material = self.connection.extension_record(
            self._request("extension_record_read", capability, object_key=object_key), deadline=time.monotonic() + 10
        )
        if isinstance(reply, AccessRefusal):
            raise FrontendRefusedError(reply.code.value)
        return reply, material

    def record_write(self, capability: str, object_key: str, payload: bytearray, *, expected_revision: str):
        """Write one extension record if its expected revision is current."""
        try:
            reply, _ = self.connection.extension_record(
                self._request(
                    "extension_record_write",
                    capability,
                    object_key=object_key,
                    expected_revision=expected_revision,
                    byte_count=len(payload),
                ),
                payload,
                deadline=time.monotonic() + 10,
            )
            if isinstance(reply, AccessRefusal):
                raise FrontendRefusedError(reply.code.value)
            return reply
        finally:
            payload[:] = bytes(len(payload))

    def record_delete(self, capability: str, object_key: str, *, expected_revision: str):
        """Delete one extension record if its expected revision is current."""
        reply, _ = self.connection.extension_record(
            self._request(
                "extension_record_delete", capability, object_key=object_key, expected_revision=expected_revision
            ),
            deadline=time.monotonic() + 10,
        )
        if isinstance(reply, AccessRefusal):
            raise FrontendRefusedError(reply.code.value)
        return reply

    def observe_generation(self, capability: str):
        """Read the current generation for one service-owned record namespace."""
        reply, _ = self.connection.extension_record(
            self._request("extension_record_generation", capability), deadline=time.monotonic() + 10
        )
        if isinstance(reply, AccessRefusal):
            raise FrontendRefusedError(reply.code.value)
        return reply

    def status(self):
        """Read the profile session currently held by this service lease."""
        self.claim()
        if self.lease is None:
            raise FrontendRefusedError("authentication_required")
        return self.connection.session(
            SessionRequest(
                action="session_status",
                request_id=uuid4(),
                profile_id=self.profile_id,
                session_id=self.lease.session_id,
            ),
            deadline=time.monotonic() + 10,
        )

    async def close(self) -> None:
        """Close the verified connection owned by this service client."""
        self.connection.close()
