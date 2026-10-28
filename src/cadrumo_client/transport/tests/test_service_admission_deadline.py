"""Service admission preserves the runtime's exchange budget and never replays."""

from __future__ import annotations

from time import monotonic
from typing import cast
from uuid import UUID, uuid4

import pytest

from cadrumo.application.operations.registry import OperationFrontendProjection

from ...contracts.contracts import RefusalCode, RefusalError
from ...contracts.service_access import ServiceAdmission, ServiceConnected
from ..framing import VerifiedConnection
from ..frontend_client import FrontendClient

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


class _Admission:
    """Refuse a wire budget too short for eleven seconds of simulated work."""

    def __init__(self) -> None:
        self.requests: list[ServiceAdmission] = []

    def service_access(self, request: ServiceAdmission, *, deadline: float) -> ServiceConnected:
        self.requests.append(request)
        if deadline - monotonic() < 11:
            raise RefusalError(RefusalCode.DEADLINE_EXCEEDED)
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
    assert refused.value.reason is RefusalCode.DEADLINE_EXCEEDED
    assert len(connection.requests) == 1
