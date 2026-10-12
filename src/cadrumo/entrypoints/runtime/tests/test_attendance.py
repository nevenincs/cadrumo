"""An MCP connection follows a person's live sign-in only on that person's decision, and only while it lives.

A real installed transport server and real native profile workers carry every
exchange. Only the OS login observation and the native key store are synthetic.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.startup import RuntimeLaunchDoor
from cadrumo.adapters.local_runtime.tests.profile_worker_support import PROFILE_INPUT, owner_id, worker_profiles
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.attendance import RuntimeAttendancePending
from cadrumo.application.runtime.contracts import RuntimeClientHello
from cadrumo.application.runtime.profile_access import RuntimeProfileStatus
from cadrumo.application.user_profile.access_contracts import (
    AccessDenialCode,
    Availability,
    LoginEligibility,
    OsLockState,
    OsLoginContext,
)

from ....adapters.local_runtime.tests.retained_server import RetainedRuntimeTransportServer
from ..profile_connections import RuntimeProfileConnections

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


class _LoginObservation:
    login_id = "attendance-native-login"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        """Supply synthetic OS facts while transport, custody and authority stay real."""
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=owner_id(),
            active=True,
            lock_state=OsLockState.UNLOCKED,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


@contextmanager
def _runtime(tmp_path: Path) -> Iterator[tuple[UUID, UUID, RuntimeLaunchDoor]]:
    with worker_profiles(tmp_path) as (root, targets):
        endpoint = WindowsRuntimeEndpoint(storage_root=root)
        runtime_installation(storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity)
        stop, native, boot = Event(), MemoryNativePort(), uuid4()
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: _LoginObservation(),
            secret_store=lambda: native,
        )
        profiles.prepare_registry()
        server = RetainedRuntimeTransportServer(
            endpoint, product_version="test", stop=stop, profiles=profiles, boot_id=boot
        )
        launch = RuntimeLaunchDoor(
            endpoint, expected=RuntimeClientHello(product_version="test", storage_identity=endpoint.storage_identity)
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(30), "the runtime transport did not start listening"
                yield targets[0][0].binding.profile_id, targets[1][0].binding.profile_id, launch
            finally:
                stop.set()
                running.result(timeout=20)
                endpoint.close()


def _client(
    launch: RuntimeLaunchDoor, profile_id: UUID, frontend: OperationFrontendProjection
) -> RuntimeFrontendClient:
    return asyncio.run(RuntimeFrontendClient.open(launch, profile_id=profile_id, frontend=frontend))


def _refusal(call: object) -> str:
    assert callable(call)
    with pytest.raises(RuntimeFrontendRefusedError) as refused:
        call()
    return refused.value.reason


def _eventually_refused(call: object, *, seconds: float = 15) -> str:
    """Return the refusal ``call`` meets once the runtime has handled a connection it saw close."""
    assert callable(call)
    deadline = time.monotonic() + seconds
    while True:
        try:
            call()
        except RuntimeFrontendRefusedError as refused:
            return refused.reason
        assert time.monotonic() < deadline, "the attended session outlived the person's closed connection"
        time.sleep(0.1)


_SESSION_OVER = frozenset(
    {
        AccessDenialCode.AUTHENTICATION_REQUIRED.value,
        AccessDenialCode.SESSION_INACTIVE.value,
        # The runtime's answer once the connection no longer holds the session it names.
        AccessDenialCode.CONNECTION_MISMATCH.value,
    }
)


def _session_over(client: RuntimeFrontendClient, *, seconds: float = 15) -> str:
    """Return how the runtime says ``client``'s session ended: refused outright, or reported denied.

    Until the retirement notice reaches the client, the runtime answers its
    status with the denial; after it, the client refuses without asking.
    """
    deadline = time.monotonic() + seconds
    while True:
        try:
            denial = client.status().status.denial
        except RuntimeFrontendRefusedError as refused:
            return refused.reason
        if denial is not None:
            return denial.value
        assert time.monotonic() < deadline, "the attended session outlived the person's session"
        time.sleep(0.1)


def _pending(reply: RuntimeAttendancePending | RuntimeProfileStatus) -> RuntimeAttendancePending:
    assert isinstance(reply, RuntimeAttendancePending)
    return reply


def test_an_ask_is_admitted_only_by_the_persons_approval_and_ends_with_their_session(tmp_path: Path) -> None:
    mcp, cli = OperationFrontendProjection.MCP, OperationFrontendProjection.CLI
    with _runtime(tmp_path) as (profile_id, _other, launch):
        with _client(launch, profile_id, mcp) as early:
            # Nobody holds a sign-in that could attend it.
            assert _refusal(early.request_attendance) == AccessDenialCode.AUTHENTICATION_REQUIRED.value

        with _client(launch, profile_id, cli) as holder, _client(launch, profile_id, mcp) as agent:
            holder.login_password(bytearray(PROFILE_INPUT.encode()), timeout=120)
            assert holder.attendance_inventory().candidates == ()

            ask = _pending(agent.request_attendance())
            # The ask admits nothing while it waits.
            assert _pending(agent.attendance_status(ask.attendance_id)).attendance_id == ask.attendance_id
            assert _refusal(lambda: agent.session_id) == AccessDenialCode.AUTHENTICATION_REQUIRED.value

            (candidate,) = holder.attendance_inventory().candidates
            assert candidate.attendance_id == ask.attendance_id
            assert candidate.process_id == os.getpid()
            assert candidate.frontend is mcp

            # The agent cannot decide asks: that is the person's act.
            assert _refusal(lambda: agent.decide_attendance(ask.attendance_id, approve=True)) in {
                AccessDenialCode.AUTHENTICATION_REQUIRED.value,
                "conflict",
            }

            assert holder.decide_attendance(ask.attendance_id, approve=True).approved
            admitted = agent.attendance_status(ask.attendance_id)
            assert isinstance(admitted, RuntimeProfileStatus)
            assert admitted.status.denial is None
            assert admitted.status.profile_id == profile_id
            assert agent.session_id == admitted.status.session_id != holder.session_id
            assert agent.status().status.denial is None
            # Asking again on the approved connection is answered under the same approval, with no new decision.
            again = agent.request_attendance()
            assert isinstance(again, RuntimeProfileStatus)
            assert again.status.denial is None
            assert holder.attendance_inventory().candidates == ()

            # Ending the person's session ends the attended one, and the approval with it.
            holder.lock()
            assert _session_over(agent) in _SESSION_OVER
            with _client(launch, profile_id, mcp) as later:
                # A new ask, on a fresh connection as the MCP server makes it, finds no held sign-in.
                assert _refusal(later.request_attendance) == AccessDenialCode.AUTHENTICATION_REQUIRED.value


def test_a_declined_ask_admits_nothing_and_closing_the_holder_ends_attendance(tmp_path: Path) -> None:
    mcp, cli = OperationFrontendProjection.MCP, OperationFrontendProjection.CLI
    with _runtime(tmp_path) as (profile_id, other_profile_id, launch):
        holder = _client(launch, profile_id, cli)
        try:
            holder.login_password(bytearray(PROFILE_INPUT.encode()), timeout=120)
            holder.attendance_inventory()
            with _client(launch, profile_id, mcp) as declined:
                ask = _pending(declined.request_attendance())
                assert not holder.decide_attendance(ask.attendance_id, approve=False).approved
                assert _refusal(lambda: declined.attendance_status(ask.attendance_id)) == (
                    AccessDenialCode.AUTHENTICATION_REQUIRED.value
                )
                assert _refusal(lambda: declined.session_id) == AccessDenialCode.AUTHENTICATION_REQUIRED.value

            with _client(launch, other_profile_id, mcp) as elsewhere:
                # A sign-in held for one profile attends no connection to another.
                assert _refusal(elsewhere.request_attendance) == AccessDenialCode.AUTHENTICATION_REQUIRED.value

            with _client(launch, profile_id, mcp) as agent:
                ask = _pending(agent.request_attendance())
                holder.decide_attendance(ask.attendance_id, approve=True)
                assert isinstance(agent.attendance_status(ask.attendance_id), RuntimeProfileStatus)
                holder.close()
                assert _session_over(agent) in _SESSION_OVER
                with _client(launch, profile_id, mcp) as later:
                    assert _eventually_refused(later.request_attendance) == (
                        AccessDenialCode.AUTHENTICATION_REQUIRED.value
                    )
        finally:
            holder.close()


def test_a_lapsed_attended_lease_is_issued_again_to_the_approved_connection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The short attended lease ends; the same approved connection is admitted again while the person's session lives."""
    from cadrumo.application.user_profile import session_authority_admission

    monkeypatch.setattr(session_authority_admission, "ACCESS_LEASE_MAXIMUM", timedelta(seconds=3))
    mcp, cli = OperationFrontendProjection.MCP, OperationFrontendProjection.CLI
    with (
        _runtime(tmp_path) as (profile_id, _other, launch),
        _client(launch, profile_id, cli) as holder,
        _client(launch, profile_id, mcp) as agent,
    ):
        holder.login_password(bytearray(PROFILE_INPUT.encode()), timeout=120)
        holder.attendance_inventory()
        ask = _pending(agent.request_attendance())
        holder.decide_attendance(ask.attendance_id, approve=True)
        first = agent.attendance_status(ask.attendance_id)
        assert isinstance(first, RuntimeProfileStatus)
        time.sleep(4)
        assert _session_over(agent) in _SESSION_OVER | {AccessDenialCode.SESSION_EXPIRED.value}
        again = agent.request_attendance()
        assert isinstance(again, RuntimeProfileStatus), again
        assert again.status.denial is None
        assert again.status.session_id != first.status.session_id
        assert holder.attendance_inventory().candidates == ()
