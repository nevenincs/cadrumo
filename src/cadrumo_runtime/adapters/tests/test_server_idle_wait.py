"""An idle runtime connection is one blocked wait, and stopping the runtime ends it at once."""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import cast
from uuid import uuid4

import pytest

from cadrumo.application.user_profile.access_contracts import (
    Availability,
    LoginEligibility,
    OsLockState,
    OsLoginContext,
)
from cadrumo_client.contracts.contracts import ByteChannel, ChannelWake, ClientHello, Peer, RefusalCode, RefusalError
from cadrumo_client.contracts.login import LoginEvidence, LoginInventory
from cadrumo_client.transport.framing import VerifiedConnection
from cadrumo_client.transport.windows import WindowsEndpoint

from ...host.profile_connections import RuntimeProfileConnections
from .retained_server import RetainedRuntimeTransportServer

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_inbound_adapter,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires the native Windows transport"),
]


class _Counted:
    """An accepted channel, recording each readiness wait its connection loop starts and how it ended."""

    def __init__(self, channel: ByteChannel) -> None:
        self.channel = channel
        self.waits = 0
        self.endings: list[bool | RefusalCode] = []

    @property
    def peer(self) -> Peer:
        return self.channel.peer

    def read_exact(self, count: int, *, deadline: float) -> bytes:
        return self.channel.read_exact(count, deadline=deadline)

    def read_ready(self) -> bool:
        return self.channel.read_ready()

    def wait_readable(self, *wakes: ChannelWake) -> bool:
        self.waits += 1
        try:
            ready = self.channel.wait_readable(*wakes)
        except RefusalError as error:
            self.endings.append(error.reason)
            raise
        self.endings.append(ready)
        return ready

    def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:
        self.channel.write_all(payload, deadline=deadline)

    def close(self) -> None:
        self.channel.close()


class _Listener:
    """The real endpoint, keeping each accepted channel it hands the server and counting its waits."""

    def __init__(self, endpoint: WindowsEndpoint) -> None:
        self.endpoint = endpoint
        self.accepted: list[_Counted] = []
        self.waits = 0

    @property
    def storage_identity(self) -> str:
        return self.endpoint.storage_identity

    def listen(self) -> None:
        self.endpoint.listen()

    def accept(self, *, timeout: float | None, wakes: tuple[ChannelWake, ...] = ()) -> ByteChannel:
        self.waits += 1
        channel = _Counted(self.endpoint.accept(timeout=timeout, wakes=wakes))
        self.accepted.append(channel)
        return channel

    def close(self) -> None:
        self.endpoint.close()


def test_an_idle_connection_waits_once_and_stop_ends_it_promptly(tmp_path: Path) -> None:
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsEndpoint(storage_root=root)
    listener = _Listener(endpoint)
    stop = Event()
    server = RetainedRuntimeTransportServer(listener, product_version="test", stop=stop)
    with ThreadPoolExecutor(max_workers=1) as pool:
        serving = pool.submit(server.serve)
        try:
            assert server.ready.wait(3)
            client = VerifiedConnection(
                endpoint.connect(timeout=5),
                expected=ClientHello(product_version="test", storage_identity=endpoint.storage_identity),
                deadline=time.monotonic() + 5,
            )
            try:
                deadline = time.monotonic() + 5
                while not (listener.accepted and listener.accepted[0].waits):
                    assert time.monotonic() < deadline, "the connection never reached its idle wait"
                    time.sleep(0.01)
                time.sleep(0.3)
                assert listener.accepted[0].waits == 1, "an idle connection is one blocked wait, not a timer"
                stopping = time.monotonic()
                stop.set()
                serving.result(timeout=10)
                assert time.monotonic() - stopping < server.DRAIN_SECONDS / 3
                # The stop itself ended the wait; it was not left to the drain's close.
                assert listener.accepted[0].endings == [False]
            finally:
                client.close()
        finally:
            stop.set()


@dataclass
class _Login:
    login_id: str = "synthetic-native-login"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id="synthetic-owner",
            active=True,
            lock_state=OsLockState.UNLOCKED,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


def test_an_idle_accept_loop_parks_until_a_lifecycle_wake_and_reports_no_tick_age(tmp_path: Path) -> None:
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsEndpoint(storage_root=root)
    listener = _Listener(endpoint)
    stop, boot = Event(), uuid4()
    login = _Login()
    profiles = RuntimeProfileConnections(
        storage_root=root,
        storage_identity=endpoint.storage_identity,
        runtime_boot_id=boot,
        stop=stop,
        service_descriptors=(),
        login_inventory=lambda: LoginInventory(logins=(cast(LoginEvidence, login),), complete=True),
    )
    # As if Windows reports this desktop login's changes: nothing is observed on a timer.
    profiles.session_changes_pushed(True)
    server = RetainedRuntimeTransportServer(
        listener, product_version="test", stop=stop, profiles=profiles, boot_id=boot
    )
    with ThreadPoolExecutor(max_workers=1) as pool:
        serving = pool.submit(server.serve)
        try:
            assert server.ready.wait(3)
            # The first passes may owe one more within an interval; then the loop rests.
            time.sleep(1.2)
            resting = listener.waits
            time.sleep(0.6)
            assert listener.waits == resting, "an idle accept loop waits; it does not turn on a timer"
            assert server.accept_tick_age() == 0.0, "a loop at rest is not reported as stuck"
            profiles.lifecycle_changed()
            deadline = time.monotonic() + 2
            while listener.waits == resting:
                assert time.monotonic() < deadline, "the lifecycle wake did not turn the loop"
                time.sleep(0.01)
            stopping = time.monotonic()
            stop.set()
            serving.result(timeout=10)
            assert time.monotonic() - stopping < server.DRAIN_SECONDS / 3
        finally:
            stop.set()
