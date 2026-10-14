"""An external client connection follows a person's live sign-in only on that person's decision, and only while it lives.

A real installed transport server and real native profile workers carry every
exchange. Only the OS login observation and the native key store are synthetic.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import psutil
import pytest

from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    AccessScope,
    Availability,
    LoginEligibility,
    OsLockState,
    OsLoginContext,
)
from cadrumo_client.contracts.attendance import AttendancePending
from cadrumo_client.contracts.contracts import ClientHello, RefusalCode, RefusalError
from cadrumo_client.contracts.profile_access import ProfileStatus
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_client.transport.installation import installation
from cadrumo_client.transport.startup import LaunchDoor
from cadrumo_client.transport.windows import WindowsEndpoint

from ...adapters.tests.profile_worker_support import PROFILE_INPUT, owner_id, worker_profiles
from ...adapters.tests.retained_server import RetainedRuntimeTransportServer
from .. import profile_connection_attendance
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
def _runtime(tmp_path: Path) -> Generator[tuple[UUID, UUID, LaunchDoor]]:
    with worker_profiles(tmp_path) as (root, targets):
        endpoint = WindowsEndpoint(storage_root=root)
        installation(storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity)
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
        launch = LaunchDoor(
            endpoint, expected=ClientHello(product_version="test", storage_identity=endpoint.storage_identity)
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
    launch: LaunchDoor, profile_id: UUID, frontend: OperationFrontendProjection, *, scope: AccessScope | None = None
) -> FrontendClient:
    return asyncio.run(
        FrontendClient.open(
            launch,
            profile_id=profile_id,
            frontend=frontend,
            scope=scope if scope is not None else (
                _ATTENDANCE_SCOPE if frontend is OperationFrontendProjection.EXTERNAL_CLIENT else None
            ),
        )
    )


def _refusal(call: object) -> str:
    assert callable(call)
    with pytest.raises(FrontendRefusedError) as refused:
        call()
    return refused.value.reason


def _eventually_refused(call: object, *, seconds: float = 15) -> str:
    """Return the refusal ``call`` meets once the runtime has handled a connection it saw close."""
    assert callable(call)
    deadline = time.monotonic() + seconds
    while True:
        try:
            call()
        except FrontendRefusedError as refused:
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

_ATTENDANCE_SCOPE = AccessScope(
    operations=frozenset({"user-profile.field-mutation"}),
    actions=frozenset({AccessAction.SUBMIT}),
    disclosures=frozenset(),
    periods=frozenset(),
    allow_period_independent=False,
    allow_delegation=False,
    allow_changes_records=False,
    allow_network=False,
)


def _session_over(client: FrontendClient, *, seconds: float = 15) -> str:
    """Return how the runtime says ``client``'s session ended: refused outright, or reported denied.

    Until the retirement notice reaches the client, the runtime answers its
    status with the denial; after it, the client refuses without asking.
    """
    deadline = time.monotonic() + seconds
    while True:
        try:
            denial = client.status().status.denial
        except FrontendRefusedError as refused:
            return refused.reason
        if denial is not None:
            return denial.value
        assert time.monotonic() < deadline, "the attended session outlived the person's session"
        time.sleep(0.1)


def _pending(reply: AttendancePending | ProfileStatus) -> AttendancePending:
    assert isinstance(reply, AttendancePending)
    return reply


def test_an_ask_is_admitted_only_by_the_persons_approval_and_ends_with_their_session(tmp_path: Path) -> None:
    external_client, cli = OperationFrontendProjection.EXTERNAL_CLIENT, OperationFrontendProjection.CLI
    with _runtime(tmp_path) as (profile_id, _other, launch):
        with _client(launch, profile_id, external_client) as early:
            # Nobody holds a sign-in that could attend it.
            assert _refusal(early.request_attendance) == AccessDenialCode.AUTHENTICATION_REQUIRED.value

        with _client(launch, profile_id, cli) as holder, _client(launch, profile_id, external_client) as automation:
            holder.login_password(bytearray(PROFILE_INPUT.encode()), timeout=120)
            assert holder.attendance_inventory().candidates == ()

            ask = _pending(automation.request_attendance())
            # The ask admits nothing while it waits.
            assert _pending(automation.attendance_status(ask.attendance_id)).attendance_id == ask.attendance_id
            assert _refusal(lambda: automation.session_id) == AccessDenialCode.AUTHENTICATION_REQUIRED.value

            (candidate,) = holder.attendance_inventory().candidates
            assert candidate.attendance_id == ask.attendance_id
            assert candidate.process_id == os.getpid()
            # The program is read from the asking process itself, never from anything it sent.
            assert candidate.image_path is not None
            assert Path(candidate.image_path) == Path(psutil.Process(os.getpid()).exe()).resolve()
            assert candidate.frontend is external_client

            # The automation cannot decide asks: that is the person's act.
            assert _refusal(lambda: automation.decide_attendance(ask.attendance_id, approve=True)) in {
                AccessDenialCode.AUTHENTICATION_REQUIRED.value,
                "conflict",
            }

            assert holder.decide_attendance(ask.attendance_id, approve=True).approved
            admitted = automation.attendance_status(ask.attendance_id)
            assert isinstance(admitted, ProfileStatus)
            assert admitted.status.denial is None
            assert admitted.status.profile_id == profile_id
            assert automation.session_id == admitted.status.session_id != holder.session_id
            assert automation.status().status.denial is None
            # Asking again on the approved connection is answered under the same approval, with no new decision.
            again = automation.request_attendance()
            assert isinstance(again, ProfileStatus)
            assert again.status.denial is None
            assert holder.attendance_inventory().candidates == ()

            # Ending the person's session ends the attended one, and the approval with it.
            holder.lock()
            assert _session_over(automation) in _SESSION_OVER
            with _client(launch, profile_id, external_client) as later:
                # A new ask, on a fresh connection as the external client server makes it, finds no held sign-in.
                assert _refusal(later.request_attendance) == AccessDenialCode.AUTHENTICATION_REQUIRED.value


def test_a_declined_ask_admits_nothing_and_closing_the_holder_ends_attendance(tmp_path: Path) -> None:
    external_client, cli = OperationFrontendProjection.EXTERNAL_CLIENT, OperationFrontendProjection.CLI
    with _runtime(tmp_path) as (profile_id, other_profile_id, launch):
        holder = _client(launch, profile_id, cli)
        try:
            holder.login_password(bytearray(PROFILE_INPUT.encode()), timeout=120)
            holder.attendance_inventory()
            with _client(launch, profile_id, external_client) as declined:
                ask = _pending(declined.request_attendance())
                assert not holder.decide_attendance(ask.attendance_id, approve=False).approved
                assert _refusal(lambda: declined.attendance_status(ask.attendance_id)) == (
                    AccessDenialCode.AUTHENTICATION_REQUIRED.value
                )
                assert _refusal(lambda: declined.session_id) == AccessDenialCode.AUTHENTICATION_REQUIRED.value

            with _client(launch, other_profile_id, external_client) as elsewhere:
                # A sign-in held for one profile attends no connection to another.
                assert _refusal(elsewhere.request_attendance) == AccessDenialCode.AUTHENTICATION_REQUIRED.value

            with _client(launch, profile_id, external_client) as automation:
                ask = _pending(automation.request_attendance())
                holder.decide_attendance(ask.attendance_id, approve=True)
                assert isinstance(automation.attendance_status(ask.attendance_id), ProfileStatus)
                holder.close()
                assert _session_over(automation) in _SESSION_OVER
                with _client(launch, profile_id, external_client) as later:
                    assert _eventually_refused(later.request_attendance) == (
                        AccessDenialCode.AUTHENTICATION_REQUIRED.value
                    )
                with _client(launch, profile_id, cli) as successor:
                    successor.login_password(bytearray(PROFILE_INPUT.encode()), timeout=120)
                    successor.attendance_inventory()
                    # The approval ended with the person's session; this connection makes no ask that
                    # nobody would claim, even with a sign-in held again.
                    assert _refusal(automation.request_attendance) == AccessDenialCode.AUTHENTICATION_REQUIRED.value
                    assert successor.attendance_inventory().candidates == ()
        finally:
            holder.close()


def test_a_lapsed_attended_lease_is_issued_again_to_the_approved_connection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The short attended lease ends; the same approved connection is admitted again while the person's session lives."""
    from ...application import session_authority_admission

    monkeypatch.setattr(session_authority_admission, "ACCESS_LEASE_MAXIMUM", timedelta(seconds=3))
    external_client, cli = OperationFrontendProjection.EXTERNAL_CLIENT, OperationFrontendProjection.CLI
    with (
        _runtime(tmp_path) as (profile_id, _other, launch),
        _client(launch, profile_id, cli) as holder,
        _client(launch, profile_id, external_client) as automation,
    ):
        holder.login_password(bytearray(PROFILE_INPUT.encode()), timeout=120)
        holder.attendance_inventory()
        ask = _pending(automation.request_attendance())
        holder.decide_attendance(ask.attendance_id, approve=True)
        first = automation.attendance_status(ask.attendance_id)
        assert isinstance(first, ProfileStatus)
        time.sleep(4)
        assert _session_over(automation) in _SESSION_OVER | {AccessDenialCode.SESSION_EXPIRED.value}
        again = automation.request_attendance()
        assert isinstance(again, ProfileStatus), again
        assert again.status.denial is None
        assert again.status.session_id != first.status.session_id
        assert holder.attendance_inventory().candidates == ()


def test_asks_are_bounded_in_number_and_time_and_only_an_agent_may_ask(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(profile_connection_attendance, "ATTENDANCE_PENDING_LIMIT", 2)
    monkeypatch.setattr(profile_connection_attendance, "ATTENDANCE_PENDING_SECONDS", 3)
    external_client, cli = OperationFrontendProjection.EXTERNAL_CLIENT, OperationFrontendProjection.CLI
    with (
        _runtime(tmp_path) as (profile_id, _other, launch),
        _client(launch, profile_id, cli) as holder,
        _client(launch, profile_id, external_client) as first,
        _client(launch, profile_id, external_client) as second,
        _client(launch, profile_id, external_client) as third,
    ):
        holder.login_password(bytearray(PROFILE_INPUT.encode()), timeout=120)
        holder.attendance_inventory()
        # A person's frontend never asks to follow another sign-in: it signs in with its own proof.
        with _client(launch, profile_id, cli, scope=_ATTENDANCE_SCOPE) as person:
            with pytest.raises((FrontendRefusedError, RefusalError)) as refused:
                person.request_attendance()
            assert str(refused.value.reason) == RefusalCode.INVALID_FRAME.value
        assert holder.attendance_inventory().candidates == ()

        ask = _pending(first.request_attendance())
        # One connection keeps one ask; a second while it waits is a conflict, not a new ask.
        assert _refusal(first.request_attendance) == "conflict"
        _pending(second.request_attendance())
        # The profile's pending asks are capped; a further ask waits for none.
        assert _refusal(third.request_attendance) == AccessDenialCode.AUTHENTICATION_REQUIRED.value
        assert len(holder.attendance_inventory().candidates) == 2

        time.sleep(4)
        # Unanswered asks lapse: they leave the person's list and admit nothing.
        assert holder.attendance_inventory().candidates == ()
        assert _refusal(lambda: first.attendance_status(ask.attendance_id)) == (
            AccessDenialCode.AUTHENTICATION_REQUIRED.value
        )
        assert _refusal(lambda: holder.decide_attendance(ask.attendance_id, approve=True)) == (
            AccessDenialCode.OPERATION_UNAVAILABLE.value
        )
        # A lapsed ask frees its place.
        assert _pending(third.request_attendance()).attendance_id in {
            candidate.attendance_id for candidate in holder.attendance_inventory().candidates
        }
