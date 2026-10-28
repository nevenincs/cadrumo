"""Service admission preserves the runtime's exchange budget and never replays."""

from __future__ import annotations

from collections.abc import Callable
from time import monotonic
from typing import cast
from uuid import UUID, uuid4

import pytest

from cadrumo.application.operations.registry import OperationFrontendProjection

from ...contracts.contracts import RefusalCode, RefusalError
from ...contracts.deadline_budget import TimeoutDeadline
from ...contracts.service_access import ServiceAdmission, ServiceConnect, ServiceConnected
from ...contracts.session_events import ConnectionEvent
from ..framing import VerifiedConnection
from ..frontend_client import FrontendClient
from ..service_client import InstalledServiceClient

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


class _Admission:
    """Refuse a wire budget shorter than the former two-minute phase cap."""

    def __init__(self) -> None:
        self.requests: list[ServiceAdmission] = []

    def subscribe_session_events(
        self, receive: Callable[[ConnectionEvent], None], *, disconnected: Callable[[], None] | None = None
    ) -> Callable[[], None]:
        return lambda: None

    def service_access(self, request: ServiceAdmission, *, deadline: float) -> ServiceConnected:
        self.requests.append(request)
        if deadline - monotonic() < 121:
            raise RefusalError(RefusalCode.TIMEOUT)
        return ServiceConnected(
            request_id=request.request_id,
            runtime_boot_id=uuid4(),
            connection_id=uuid4(),
            profile_id=request.profile_id,
            service_id=request.service_id,
        )


def _client(connection: _Admission, profile: UUID, session: UUID) -> FrontendClient:
    client = FrontendClient(
        cast(VerifiedConnection, connection), profile_id=profile, frontend=OperationFrontendProjection.DESKTOP
    )
    client._session_id = session
    return client


def test_service_admission_allows_slow_verification_under_the_exact_session() -> None:
    connection = _Admission()
    profile, session, recipient, request_id = (uuid4() for _ in range(4))
    reply = _client(connection, profile, session).service_admission(
        recipient, "cadrumo-agent-service", request_id=request_id
    )
    assert reply.kind == "service_connected"
    assert connection.requests == [
        ServiceAdmission(
            request_id=request_id,
            profile_id=profile,
            session_id=session,
            recipient_connection_id=recipient,
            service_id="cadrumo-agent-service",
        )
    ]


def test_service_admission_honors_a_short_explicit_budget_without_replay() -> None:
    connection = _Admission()
    with pytest.raises(RefusalError) as refused:
        _client(connection, uuid4(), uuid4()).service_admission(uuid4(), "cadrumo-agent-service", timeout=1)
    assert refused.value.reason is RefusalCode.TIMEOUT
    assert len(connection.requests) == 1


class _ServiceRegistration:
    def __init__(self, *, fail: bool = False) -> None:
        self.deadlines: list[float] = []
        self.fail = fail

    def service_access(self, request: ServiceConnect, *, deadline: float) -> ServiceConnected:
        self.deadlines.append(deadline)
        if self.fail:
            raise RefusalError(RefusalCode.TIMEOUT)
        return ServiceConnected(
            request_id=request.request_id,
            runtime_boot_id=uuid4(),
            connection_id=uuid4(),
            profile_id=request.profile_id,
            service_id=request.service_id,
        )


def test_service_registration_can_outlast_the_former_exchange_cap() -> None:
    connection = _ServiceRegistration()
    client = InstalledServiceClient(cast(VerifiedConnection, connection), profile_id=uuid4(), service_id="service")
    client.claim()
    assert connection.deadlines[0] - monotonic() > 121
    assert len(connection.deadlines) == 1


def test_service_registration_retains_the_opening_owners_absolute_timeout() -> None:
    connection = _ServiceRegistration()
    timeout = TimeoutDeadline(monotonic() + 7)
    client = InstalledServiceClient(
        cast(VerifiedConnection, connection), profile_id=uuid4(), service_id="service", startup_deadline=timeout
    )
    client.claim()
    assert connection.deadlines == [timeout.instant]
    client.claim()
    assert connection.deadlines[1] > timeout.instant


def test_service_timeout_is_distinct_and_never_replays_the_request() -> None:
    connection = _ServiceRegistration(fail=True)
    client = InstalledServiceClient(cast(VerifiedConnection, connection), profile_id=uuid4(), service_id="service")
    with pytest.raises(RefusalError) as refused:
        client.claim()
    assert refused.value.reason is RefusalCode.TIMEOUT
    assert len(connection.deadlines) == 1
