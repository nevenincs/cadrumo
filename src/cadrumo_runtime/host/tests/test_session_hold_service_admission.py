"""Service polling preserves the parent holder command's correlation and lease."""

from __future__ import annotations

import json
from threading import Event
from typing import override
from uuid import UUID, uuid4

import pytest

from cadrumo_client.contracts.access_refusals import AccessDenialCode, ProfileAccessStatus
from cadrumo_client.contracts.access_vocabulary import Availability, EffectiveScopeSummary, disclosure_digest
from cadrumo_client.contracts.deadline_budget import MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS
from cadrumo_client.contracts.profile_access import ProfileStatus
from cadrumo_client.contracts.service_access import ServiceConnected, ServiceLease
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_runtime.host.session_hold import HoldActionState, process_hold_request
from cadrumo_runtime.host.session_hold_operations import OperationRelay

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class _Client(FrontendClient):
    """Supply validated session/lease replies at this serialization boundary."""

    def __init__(self, snapshot: ProfileStatus) -> None:
        self.snapshot = snapshot
        self.connected_reply: ServiceConnected | None = None
        self.requests: list[tuple[UUID, str, UUID | None]] = []

    @override
    def status(self, *, timeout: float = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS) -> ProfileStatus:
        return self.snapshot

    @override
    def service_admission(
        self,
        recipient_connection_id: UUID,
        service_id: str,
        *,
        request_id: UUID | None = None,
        timeout: float | None = None,
    ) -> ServiceConnected:
        self.requests.append((recipient_connection_id, service_id, request_id))
        assert self.connected_reply is not None
        return self.connected_reply


def _held_session(
    *, denial: AccessDenialCode | None = None, live_session: bool = True
) -> tuple[HoldActionState, _Client]:
    profile_id = uuid4()
    status = ProfileStatus(
        request_id=uuid4(),
        runtime_boot_id=uuid4(),
        connection_id=uuid4(),
        status=ProfileAccessStatus(
            connected=True,
            credential_authenticated=True,
            profile_id=profile_id,
            session_id=uuid4() if live_session else None,
            session_expires_at=None,
            grant_state=None,
            grant_expires_at=None,
            grant_valid=False,
            profile_bound=True,
            storage=Availability.AVAILABLE,
            automation_custody=Availability.NOT_REQUIRED,
            published_authority=Availability.AVAILABLE,
            provider=Availability.NOT_REQUIRED,
            effective_scope=EffectiveScopeSummary(
                operations=frozenset(),
                actions=frozenset(),
                disclosure_count=0,
                disclosure_summary=(),
                disclosure_digest=disclosure_digest(()),
                periods=None,
                allow_period_independent=True,
                allow_delegation=False,
            ),
            denial=denial,
        ),
    )
    client = _Client(status)
    state = HoldActionState(
        client=client,
        status=status,
        profile_id=profile_id,
        relay=OperationRelay(client),
        language_dirty=Event(),
    )
    return state, client


@pytest.mark.parametrize("polled", (False, True))
def test_service_admission_keeps_parent_correlation_after_wire_polling(
    capsys: pytest.CaptureFixture[str], polled: bool
) -> None:
    state, client = _held_session()
    parent_request_id = uuid4()
    wire_request_id = uuid4() if polled else parent_request_id
    recipient = uuid4()
    parent_session = client.snapshot.status.session_id
    assert parent_session is not None
    lease = ServiceLease(
        lease_id=uuid4(),
        session_id=uuid4(),
        profile_id=state.profile_id,
        parent_session_id=parent_session,
        descriptor_digest="e" * 64,
        service_id="cadrumo-agent-service",
        runtime_boot_id=client.snapshot.runtime_boot_id,
        connection_id=recipient,
    )
    connected = ServiceConnected(
        request_id=wire_request_id,
        runtime_boot_id=lease.runtime_boot_id,
        connection_id=client.snapshot.connection_id,
        profile_id=state.profile_id,
        service_id=lease.service_id,
        lease=lease,
    )
    client.connected_reply = connected

    assert (
        process_hold_request(
            state,
            parent_request_id,
            "service_admission",
            {"recipient_connection_id": str(recipient), "service_id": lease.service_id},
        )
        is None
    )

    emitted = json.loads(capsys.readouterr().out)
    assert emitted == {**connected.model_dump(mode="json"), "request_id": str(parent_request_id)}
    assert connected.request_id == wire_request_id
    assert client.requests == [(recipient, lease.service_id, parent_request_id)]


@pytest.mark.parametrize(
    ("denial", "live_session", "expected_exit", "code"),
    (
        (AccessDenialCode.OS_SESSION_UNAVAILABLE, True, None, "unavailable"),
        (AccessDenialCode.AUTHENTICATION_REQUIRED, False, 1, "inactive"),
    ),
)
def test_service_admission_does_not_bypass_an_inactive_holder(
    capsys: pytest.CaptureFixture[str],
    denial: AccessDenialCode,
    live_session: bool,
    expected_exit: int | None,
    code: str,
) -> None:
    state, client = _held_session(denial=denial, live_session=live_session)
    request_id = uuid4()

    assert (
        process_hold_request(
            state,
            request_id,
            "service_admission",
            {"recipient_connection_id": str(uuid4()), "service_id": "cadrumo-agent-service"},
        )
        == expected_exit
    )

    assert json.loads(capsys.readouterr().out) == {
        "kind": "session_refused",
        "code": code,
        "request_id": str(request_id),
    }
    assert client.requests == []
