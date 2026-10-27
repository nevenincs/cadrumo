"""A lease the runtime keeps suspended after a worker loss is waited for, never claimed, torn down or reported as a sign-out."""

from __future__ import annotations

import json
import socket
from datetime import timedelta
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
from pydantic import JsonValue

from cadrumo.core.time.clock import now
from cadrumo_client.contracts.access_refusals import (
    AccessDenialCode,
    ProfileAccessStatus,
)
from cadrumo_client.contracts.access_vocabulary import AccessScope, AuthorityState, Availability, EffectiveScopeSummary
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.profile_access import AccessRefusal, ProfileStatus, SessionRequest
from cadrumo_client.contracts.service_access import ServiceLease
from cadrumo_client.transport.frontend_client_contracts import CustodyRecoveringError, FrontendRefusedError
from cadrumo_client.transport.service_client import InstalledServiceClient

from ...admin import AdminServer
from ...main import _wait_out_recovery
from ...service import AgentService
from .test_admin_authority import _read, _send

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


def _status(lease: ServiceLease, *, denial: AccessDenialCode | None, window: int | None = None) -> ProfileStatus:
    """The status the runtime reports for a lease, built through the real contracts."""
    return ProfileStatus(
        request_id=uuid4(),
        runtime_boot_id=lease.runtime_boot_id,
        connection_id=lease.connection_id,
        status=ProfileAccessStatus(
            connected=True,
            credential_authenticated=denial is None,
            profile_id=lease.profile_id,
            session_id=lease.session_id,
            session_expires_at=now() + timedelta(minutes=5),
            grant_state=AuthorityState.ACTIVE,
            grant_expires_at=now() + timedelta(minutes=5),
            grant_valid=True,
            profile_bound=True,
            storage=Availability.AVAILABLE,
            automation_custody=Availability.AVAILABLE,
            published_authority=Availability.AVAILABLE,
            provider=Availability.NOT_REQUIRED,
            effective_scope=EffectiveScopeSummary.summarize(
                AccessScope(
                    operations=frozenset(),
                    actions=frozenset(),
                    disclosures=frozenset(),
                    periods=None,
                    allow_period_independent=True,
                    allow_delegation=False,
                )
            ),
            denial=denial,
            recovery_remaining_seconds=window,
        ),
    )


def _refusal(lease: ServiceLease, code: AccessDenialCode, *, window: int | None = None) -> AccessRefusal:
    return AccessRefusal(
        request_id=uuid4(),
        runtime_boot_id=lease.runtime_boot_id,
        connection_id=lease.connection_id,
        code=code,
        recovery_remaining_seconds=window,
    )


class _Runtime:
    """The runtime's side of the service connection: it answers a lease's status read and counts claims."""

    def __init__(self) -> None:
        self.lease: ServiceLease | None = ServiceLease(
            lease_id=uuid4(),
            session_id=uuid4(),
            profile_id=uuid4(),
            parent_session_id=uuid4(),
            descriptor_digest="2" * 64,
            service_id="cadrumo-agent-service",
            runtime_boot_id=uuid4(),
            connection_id=uuid4(),
        )
        self.reply: ProfileStatus | AccessRefusal | RefusalError | None = None
        self.asked: list[SessionRequest] = []
        self.claims = 0
        self.connection = SimpleNamespace(session=self._session)

    def _session(self, request: SessionRequest, *, deadline: float) -> ProfileStatus | AccessRefusal:
        self.asked.append(request)
        if isinstance(self.reply, RefusalError):
            raise self.reply
        assert self.reply is not None
        return self.reply

    def claim(self) -> ServiceLease | None:
        self.claims += 1
        return self.lease

    def answers(self, *, denial: AccessDenialCode | None, window: int | None = None) -> None:
        assert self.lease is not None
        self.reply = _status(self.lease, denial=denial, window=window)

    def refuses(self, code: AccessDenialCode, *, window: int | None = None) -> None:
        assert self.lease is not None
        self.reply = _refusal(self.lease, code, window=window)


def _service(runtime: _Runtime, tmp_path: Path, emitted: list[dict[str, object]] | None = None) -> AgentService:
    return AgentService(
        client=cast(InstalledServiceClient, runtime),
        storage_root=tmp_path,
        gateway_bearer=bytearray(),
        emit=(emitted if emitted is not None else []).append,
    )


def test_a_suspended_lease_is_read_by_its_own_session_and_never_claimed(tmp_path: Path) -> None:
    runtime = _Runtime()
    service = _service(runtime, tmp_path)
    runtime.answers(denial=AccessDenialCode.CUSTODY_RECOVERING, window=87)
    assert service.hold_for_recovery() == 87
    assert runtime.claims == 0
    assert runtime.lease is not None
    # The read names exactly this lease's session and asks nothing of it.
    [asked] = runtime.asked
    assert asked.action == "session_status"
    assert (asked.profile_id, asked.session_id) == (runtime.lease.profile_id, runtime.lease.session_id)


@pytest.mark.parametrize("window", [0, 3, 120])
def test_a_refusal_in_place_of_a_status_names_the_same_window(tmp_path: Path, window: int) -> None:
    runtime = _Runtime()
    service = _service(runtime, tmp_path)
    runtime.refuses(AccessDenialCode.CUSTODY_RECOVERING, window=window)
    assert service.hold_for_recovery() == window


def test_a_window_the_runtime_does_not_name_is_zero_seconds_not_a_live_lease(tmp_path: Path) -> None:
    runtime = _Runtime()
    service = _service(runtime, tmp_path)
    runtime.answers(denial=AccessDenialCode.CUSTODY_RECOVERING)
    assert service.hold_for_recovery() == 0


@pytest.mark.parametrize(
    "code",
    [AccessDenialCode.CUSTODY_UNAVAILABLE, AccessDenialCode.AUTHENTICATION_REQUIRED, AccessDenialCode.SESSION_EXPIRED],
)
def test_a_lease_that_ended_is_not_waited_for(tmp_path: Path, code: AccessDenialCode) -> None:
    runtime = _Runtime()
    service = _service(runtime, tmp_path)
    runtime.refuses(code)
    assert service.hold_for_recovery() is None
    runtime.answers(denial=code)
    assert service.hold_for_recovery() is None


def test_a_live_lease_and_a_missing_one_are_not_waited_for(tmp_path: Path) -> None:
    runtime = _Runtime()
    service = _service(runtime, tmp_path)
    runtime.answers(denial=None)
    assert service.hold_for_recovery() is None
    runtime.lease = None
    runtime.asked.clear()
    assert service.hold_for_recovery() is None
    assert runtime.asked == []


def test_a_lost_connection_is_left_to_the_claim_that_follows(tmp_path: Path) -> None:
    runtime = _Runtime()
    service = _service(runtime, tmp_path)
    runtime.reply = RefusalError(RefusalCode.CONNECTION_CLOSED)
    assert service.hold_for_recovery() is None


def test_a_start_while_the_lease_waits_is_busy_and_never_a_sign_out(tmp_path: Path) -> None:
    runtime = _Runtime()
    emitted: list[dict[str, object]] = []
    service = _service(runtime, tmp_path, emitted)
    runtime.answers(denial=AccessDenialCode.CUSTODY_RECOVERING, window=60)
    assert service.hold_for_recovery() == 60
    assert service.start() == {"event": "refused", "code": "busy"}
    # Nothing was stopped or announced: the tree and its conversations are as they were.
    assert emitted == []
    assert service._controller is None
    # Back, the service is no longer holding off a start.
    runtime.answers(denial=None)
    assert service.hold_for_recovery() is None
    assert not service._reconnecting.is_set()


def test_the_main_loop_waits_out_a_suspension_and_reads_its_lease_again_at_the_next_cue(tmp_path: Path) -> None:
    runtime = _Runtime()
    service = _service(runtime, tmp_path)
    wake = Event()
    wake.set()
    runtime.answers(denial=AccessDenialCode.CUSTODY_RECOVERING, window=30)
    assert _wait_out_recovery(service, wake) is True
    assert runtime.claims == 0
    runtime.answers(denial=None)
    assert _wait_out_recovery(service, wake) is False
    assert runtime.claims == 0


def _ask(server: AdminServer, bearer: bytearray) -> dict[str, JsonValue]:
    request = {"version": 1, "request_id": str(uuid4()), "action": "status"}
    with socket.create_connection(("127.0.0.1", server.port), timeout=5) as stream:
        _send(stream, bearer)
        _send(stream, json.dumps(request).encode())
        reply = _read(stream)
    assert reply["request_id"] == request["request_id"]
    result = reply["result"]
    assert isinstance(result, dict)
    return cast(dict[str, JsonValue], result)


class _Target:
    def __init__(self, failure: Exception) -> None:
        self._failure = failure

    def admin(self, action: str, **_metadata: object) -> JsonValue:
        raise self._failure


@pytest.mark.parametrize(
    ("failure", "code"),
    [
        (FrontendRefusedError("custody_recovering"), "busy"),
        (CustodyRecoveringError(remaining_seconds=42), "busy"),
        (FrontendRefusedError("custody_unavailable"), "service_failed"),
        (FrontendRefusedError("authentication_required"), "service_failed"),
        (RuntimeError("synthetic"), "service_failed"),
    ],
)
def test_a_request_refused_while_the_lease_waits_is_busy_and_other_failures_stay_failures(
    failure: Exception, code: str
) -> None:
    bearer = bytearray(b"a" * 64)
    server = AdminServer(_Target(failure), bearer=bearer)
    try:
        assert _ask(server, bearer) == {"kind": "refused", "code": code}
    finally:
        server.close()
