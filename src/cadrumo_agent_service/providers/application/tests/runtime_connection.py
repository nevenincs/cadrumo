"""A runtime connection that answers the service client's frames the way the transport delivers them.

The service client and the provider store run for real over it. Every claim is
answered with a lease decoded from JSON, so it equals the lease the client held
but is never the same object, as a reply read off the wire is.
"""

from __future__ import annotations

from collections.abc import Callable
from threading import Lock
from typing import cast
from uuid import UUID, uuid4

from cadrumo_client.contracts.deadline_budget import TimeoutDeadline
from cadrumo_client.contracts.extension_records import ExtensionRecordReply, ExtensionRecordRequest
from cadrumo_client.contracts.service_access import ServiceConnect, ServiceConnected, ServiceLease
from cadrumo_client.transport.framing import VerifiedConnection
from cadrumo_client.transport.service_client import InstalledServiceClient

CUSTODY_GENERATION = "b" * 64
RECORDS_GENERATION = "c" * 64


def synthetic_lease(*, session_id: UUID | None = None) -> ServiceLease:
    """Return a lease for invented identities."""
    return ServiceLease(
        lease_id=uuid4(),
        session_id=uuid4() if session_id is None else session_id,
        profile_id=uuid4(),
        parent_session_id=uuid4(),
        descriptor_digest="a" * 64,
        service_id="cadrumo-agent-service",
        runtime_boot_id=uuid4(),
        connection_id=uuid4(),
    )


class RuntimeConnection:
    """Answer claims with an equal, newly decoded lease and every record read as absent."""

    def __init__(
        self,
        lease: ServiceLease,
        *,
        on_request: Callable[[float], None] | None = None,
        claimed_session: Callable[[], UUID | None] | None = None,
    ) -> None:
        """Bind the connection to the lease it issues.

        ``on_request`` sees each request's deadline before it is answered.
        ``claimed_session`` names the session a claim answers with; the lease's
        own session is kept while it returns ``None``.
        """
        self.lease = lease
        self._on_request = on_request
        self._claimed_session = claimed_session
        self._guard = Lock()
        self.claims = 0
        self.record_reads = 0

    def service_access(self, request: ServiceConnect, *, deadline: float) -> ServiceConnected:
        """Issue the lease, decoded from its JSON document."""
        if self._on_request is not None:
            self._on_request(deadline)
        session = None if self._claimed_session is None else self._claimed_session()
        with self._guard:
            self.claims += 1
            if session is not None:
                self.lease = self.lease.model_copy(update={"session_id": session})
            issued = ServiceLease.model_validate_json(self.lease.model_dump_json())
        return ServiceConnected(
            request_id=request.request_id,
            runtime_boot_id=issued.runtime_boot_id,
            connection_id=issued.connection_id,
            profile_id=issued.profile_id,
            service_id=issued.service_id,
            lease=issued,
        )

    def extension_record(
        self, request: ExtensionRecordRequest, *, deadline: float
    ) -> tuple[ExtensionRecordReply, bytearray]:
        """Report the generations for a generation request and no stored record for a read."""
        if self._on_request is not None:
            self._on_request(deadline)
        generation = request.action == "extension_record_generation"
        if request.action == "extension_record_read":
            with self._guard:
                self.record_reads += 1
        return ExtensionRecordReply(
            request_id=request.request_id,
            runtime_boot_id=self.lease.runtime_boot_id,
            connection_id=self.lease.connection_id,
            state="generation" if generation else "absent",
            custody_generation=CUSTODY_GENERATION,
            records_generation=RECORDS_GENERATION,
        ), bytearray()

    def close(self) -> None:
        """Release nothing: the connection holds no resource."""


def service_client(
    connection: RuntimeConnection, *, startup_deadline: TimeoutDeadline | None = None
) -> InstalledServiceClient:
    """Return the real service client over the connection, holding no lease until it claims one."""
    return InstalledServiceClient(
        cast(VerifiedConnection, connection),
        profile_id=connection.lease.profile_id,
        service_id=connection.lease.service_id,
        startup_deadline=startup_deadline,
    )
