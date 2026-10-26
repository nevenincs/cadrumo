"""Verified installed-service access without profile keys or repository handles."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Literal
from uuid import UUID, uuid4

from ..contracts.deadline_budget import MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS
from ..contracts.extension_records import ExtensionRecordRequest
from ..contracts.model_runs import (
    ModelRunCompleted,
    ModelRunCompleteRequest,
    ModelRunFetched,
    ModelRunFetchRequest,
    ModelRunOutcome,
    ModelRunRequested,
)
from ..contracts.profile_access import AccessRefusal, SessionRequest
from ..contracts.service_access import ServiceConnect, ServiceConnected, ServiceLease
from .framing import VerifiedConnection
from .frontend_client_contracts import FrontendRefusedError

SERVICE_EXCHANGE_TIMEOUT_SECONDS = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS
"""How long one exchange on the service connection waits for the runtime.

An exchange that overruns closes the connection, and with it the admission the
person granted, which no later request can recover. A slow runtime is not a lost
one: its supervisor judges that and ends the service. So the service waits as
long as a person's frontend connection would."""


def _deadline() -> float:
    return time.monotonic() + SERVICE_EXCHANGE_TIMEOUT_SECONDS


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
        return self.connection.subscribe_session_events(
            lambda event: None if isinstance(event, ModelRunRequested) else changed(), disconnected=changed
        )

    def subscribe_model_runs(self, requested: Callable[[ModelRunRequested], None]) -> Callable[[], None]:
        """Call ``requested`` for every model run the runtime announces on this connection.

        It runs on the connection's event reader and must only hand the run on:
        fetching or answering it from there would wait on the reader itself.
        """

        def receive(event: object) -> None:
            if isinstance(event, ModelRunRequested) and event.profile_id == self.profile_id:
                requested(event)

        return self.connection.subscribe_session_events(receive)

    def model_run_fetch(self, run_id: UUID) -> tuple[ModelRunFetched, bytearray] | None:
        """Fetch an announced model run under the current lease, or ``None`` when it is no longer waiting."""
        lease = self._lease()
        reply, body = self.connection.model_run_fetch(
            ModelRunFetchRequest(
                request_id=uuid4(),
                profile_id=self.profile_id,
                session_id=lease.session_id,
                lease_id=lease.lease_id,
                run_id=run_id,
            ),
            deadline=_deadline(),
        )
        if isinstance(reply, AccessRefusal):
            return None
        return reply, body

    def model_run_complete(self, run_id: UUID, outcome: ModelRunOutcome, text: bytearray) -> bool:
        """Answer a fetched model run; false when the runtime no longer waits for it."""
        lease = self._lease()
        reply = self.connection.model_run_complete(
            ModelRunCompleteRequest(
                request_id=uuid4(),
                profile_id=self.profile_id,
                session_id=lease.session_id,
                lease_id=lease.lease_id,
                run_id=run_id,
                outcome=outcome,
            ),
            text,
            deadline=_deadline(),
        )
        return isinstance(reply, ModelRunCompleted) and reply.accepted

    def _lease(self) -> ServiceLease:
        if self.lease is None:
            raise FrontendRefusedError("authentication_required")
        return self.lease

    def claim(self) -> ServiceLease | None:
        """Request or refresh the service lease for this profile connection."""
        reply = self.connection.service_access(
            ServiceConnect(request_id=uuid4(), profile_id=self.profile_id, service_id=self.service_id),
            deadline=_deadline(),
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
            self._request("extension_record_read", capability, object_key=object_key), deadline=_deadline()
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
                deadline=_deadline(),
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
            deadline=_deadline(),
        )
        if isinstance(reply, AccessRefusal):
            raise FrontendRefusedError(reply.code.value)
        return reply

    def observe_generation(self, capability: str):
        """Read the current generation for one service-owned record namespace."""
        reply, _ = self.connection.extension_record(
            self._request("extension_record_generation", capability), deadline=_deadline()
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
            deadline=_deadline(),
        )

    async def close(self) -> None:
        """Close the verified connection owned by this service client."""
        self.connection.close()
