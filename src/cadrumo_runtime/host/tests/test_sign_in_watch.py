"""A sign-in watch rides the real native transport: the runtime pushes a cue, and only to its watcher."""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest

from cadrumo_client.contracts.session_events import ConnectionEvent, SignInChanged
from cadrumo_client.contracts.sign_in import SignInPresence, SignInStatusReply, SignInStatusRequest
from cadrumo_client.transport.framing import VerifiedConnection
from cadrumo_client.transport.windows import WindowsEndpoint

from ...adapters.tests.profile_worker_support import owner_id
from ...adapters.tests.retained_server import RetainedRuntimeTransportServer
from ..profile_connections import RuntimeProfileConnections
from .test_profile_connections import LoginObservation, connect

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires the native Windows transport"),
]


def test_a_watching_connection_is_cued_on_a_sign_in_change_and_a_plain_status_read_is_not(tmp_path: Path) -> None:
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsEndpoint(storage_root=root)
    stop, boot = Event(), uuid4()
    profiles = RuntimeProfileConnections(
        storage_root=root,
        storage_identity=endpoint.storage_identity,
        runtime_boot_id=boot,
        stop=stop,
        capture_login=lambda _channel: LoginObservation(owner_id()),
        service_descriptors=(),
    )
    server = RetainedRuntimeTransportServer(
        endpoint, product_version="test", stop=stop, profiles=profiles, boot_id=boot
    )
    with ThreadPoolExecutor(max_workers=1) as pool:
        running = pool.submit(server.serve)
        clients: list[VerifiedConnection] = []
        try:
            assert server.ready.wait(3)
            watcher, reader = connect(endpoint), connect(endpoint)
            clients.extend((watcher, reader))
            cued, unexpected = Event(), Event()
            watched: list[ConnectionEvent] = []

            def heard(event: ConnectionEvent) -> None:
                watched.append(event)
                cued.set()

            watcher.subscribe_session_events(heard)
            reader.subscribe_session_events(lambda _event: unexpected.set())
            profile_id = uuid4()
            for client, watch in ((watcher, True), (reader, False)):
                reply = client.sign_in_status(
                    SignInStatusRequest(request_id=uuid4(), profile_id=profile_id, watch=watch),
                    deadline=time.monotonic() + 5,
                )
                assert isinstance(reply, SignInStatusReply)
                assert reply.status.presence is SignInPresence.ABSENT

            profiles._retired((uuid4(),))

            assert cued.wait(5), "the watcher heard no cue"
            (event,) = watched
            assert isinstance(event, SignInChanged)
            assert event.runtime_boot_id == boot
            assert not unexpected.wait(0.5), "a plain status read must not subscribe its connection"
        finally:
            for client in clients:
                client.close()
            stop.set()
            running.result(timeout=12)
            endpoint.close()
