"""One verified connection owns one complete wire exchange at a time."""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event, Lock
from uuid import uuid4

import pytest

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import (
    RuntimeByteChannel,
    RuntimeClientHello,
    RuntimePeer,
    RuntimeRefusalCode,
    RuntimeRefusalError,
    RuntimeServerHello,
)
from cadrumo.application.runtime.profile_access import (
    RuntimeAccessRefusal,
    RuntimeProfileLogin,
    RuntimeSecretReady,
    RuntimeSessionRequest,
)

from ..framing import VerifiedRuntimeConnection, accept_runtime_handshake
from ..runtime_frame_io import read_document, read_secret, write_document
from ..server import RuntimeTransportServer
from ..windows import WindowsRuntimeEndpoint

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_inbound_adapter,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows endpoint"),
]


class PausingChannel:
    """Pause one real request write after its native channel sends the frame."""

    def __init__(self, channel: RuntimeByteChannel) -> None:
        self.channel = channel
        self.armed = False
        self.sent = Event()
        self.release = Event()
        self._lock = Lock()
        self.writes = 0

    @property
    def peer(self) -> RuntimePeer:
        return self.channel.peer

    def read_exact(self, count: int, *, deadline: float) -> bytes:
        return self.channel.read_exact(count, deadline=deadline)

    def read_ready(self) -> bool:
        return self.channel.read_ready()

    def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:
        self.channel.write_all(payload, deadline=deadline)
        if self.armed and payload[:1] == b"J":
            with self._lock:
                self.writes += 1
                first = self.writes == 1
            if first:
                self.sent.set()
                if not self.release.wait(5):
                    raise TimeoutError("first exchange was not released")

    def close(self) -> None:
        self.channel.close()


def test_concurrent_status_exchanges_share_only_their_own_native_connection(tmp_path: Path) -> None:
    endpoint = WindowsRuntimeEndpoint(storage_root=tmp_path)
    stop = Event()
    host = RuntimeTransportServer(endpoint, product_version="serial-test", stop=stop)
    with ThreadPoolExecutor(max_workers=1) as server_pool:
        serving = server_pool.submit(host.serve)
        try:
            assert host.ready.wait(5)
            pausing = PausingChannel(endpoint.connect(timeout=3))
            expected = RuntimeClientHello(product_version="serial-test", storage_identity=endpoint.storage_identity)
            shared = VerifiedRuntimeConnection(pausing, expected=expected, deadline=time.monotonic() + 5)
            independent = VerifiedRuntimeConnection(
                endpoint.connect(timeout=3), expected=expected, deadline=time.monotonic() + 5
            )
            try:
                pausing.armed = True
                first_request = RuntimeSessionRequest(
                    action="session_status", request_id=uuid4(), profile_id=uuid4(), session_id=uuid4()
                )
                second_request = RuntimeSessionRequest(
                    action="session_status", request_id=uuid4(), profile_id=uuid4(), session_id=uuid4()
                )
                other_request = RuntimeSessionRequest(
                    action="session_status", request_id=uuid4(), profile_id=uuid4(), session_id=uuid4()
                )
                with ThreadPoolExecutor(max_workers=3) as callers:
                    first = callers.submit(shared.session, first_request, deadline=time.monotonic() + 5)
                    assert pausing.sent.wait(3)
                    queued_secret = bytearray(b"synthetic-never-transmitted-credential")
                    with pytest.raises(RuntimeRefusalError) as timed_out:
                        shared.login(
                            RuntimeProfileLogin(
                                request_id=uuid4(),
                                profile_id=uuid4(),
                                method="password",
                                frontend=OperationFrontendProjection.CLI,
                            ),
                            queued_secret,
                            deadline=time.monotonic() + 0.1,
                        )
                    assert timed_out.value.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED
                    assert not any(queued_secret)
                    assert pausing.writes == 1 and not first.done()
                    second_started = Event()

                    def second_status():
                        second_started.set()
                        return shared.session(second_request, deadline=time.monotonic() + 5)

                    second = callers.submit(second_status)
                    assert second_started.wait(2)
                    other = callers.submit(independent.session, other_request, deadline=time.monotonic() + 5)
                    other_result = other.result(timeout=3)
                    assert other_result.request_id == other_request.request_id
                    assert pausing.writes == 1
                    assert not second.done()
                    pausing.release.set()
                    first_result = first.result(timeout=5)
                    second_result = second.result(timeout=5)
                assert first_result.request_id == first_request.request_id
                assert second_result.request_id == second_request.request_id
                assert first_result.connection_id == second_result.connection_id
                assert first_result.connection_id != other_result.connection_id
            finally:
                pausing.release.set()
                shared.close()
                independent.close()
        finally:
            stop.set()
            serving.result(timeout=10)


def test_login_secret_exchange_precedes_queued_status_on_same_native_connection(tmp_path: Path) -> None:
    endpoint = WindowsRuntimeEndpoint(storage_root=tmp_path)
    identity = RuntimeServerHello(
        product_version="serial-login", storage_identity=endpoint.storage_identity, boot_id=uuid4()
    )
    connection_id = uuid4()
    expected_secret = b"synthetic-credential"
    login_request = RuntimeProfileLogin(
        request_id=uuid4(), profile_id=uuid4(), method="password", frontend=OperationFrontendProjection.MCP
    )
    status_request = RuntimeSessionRequest(
        action="session_status", request_id=uuid4(), profile_id=uuid4(), session_id=uuid4()
    )

    def serve() -> None:
        channel = endpoint.accept(timeout=5)
        try:
            accept_runtime_handshake(channel, identity=identity, deadline=time.monotonic() + 7)
            login = read_document(channel, RuntimeProfileLogin, deadline=time.monotonic() + 7)
            assert login.request_id == login_request.request_id
            write_document(
                channel,
                RuntimeSecretReady(
                    request_id=login.request_id, runtime_boot_id=identity.boot_id, connection_id=connection_id
                ),
                deadline=time.monotonic() + 7,
            )
            with read_secret(channel, deadline=time.monotonic() + 7) as received:
                assert received == expected_secret
            write_document(
                channel,
                RuntimeAccessRefusal(
                    request_id=login.request_id,
                    runtime_boot_id=identity.boot_id,
                    connection_id=connection_id,
                    code=RuntimeRefusalCode.UNAVAILABLE,
                ),
                deadline=time.monotonic() + 7,
            )
            status = read_document(channel, RuntimeSessionRequest, deadline=time.monotonic() + 7)
            assert status.request_id == status_request.request_id
            write_document(
                channel,
                RuntimeAccessRefusal(
                    request_id=status.request_id,
                    runtime_boot_id=identity.boot_id,
                    connection_id=connection_id,
                    code=RuntimeRefusalCode.UNAVAILABLE,
                ),
                deadline=time.monotonic() + 7,
            )
        finally:
            channel.close()

    endpoint.listen()
    try:
        with ThreadPoolExecutor(max_workers=1) as server_pool:
            serving = server_pool.submit(serve)
            pausing = PausingChannel(endpoint.connect(timeout=3))
            client = VerifiedRuntimeConnection(
                pausing,
                expected=RuntimeClientHello(
                    product_version=identity.product_version, storage_identity=identity.storage_identity
                ),
                deadline=time.monotonic() + 5,
            )
            try:
                pausing.armed = True
                secret = bytearray(expected_secret)
                with ThreadPoolExecutor(max_workers=2) as callers:
                    login = callers.submit(client.login, login_request, secret, deadline=time.monotonic() + 7)
                    assert pausing.sent.wait(3)
                    status = callers.submit(client.session, status_request, deadline=time.monotonic() + 7)
                    assert pausing.writes == 1
                    assert not status.done()
                    pausing.release.set()
                    login_result = login.result(timeout=7)
                    status_result = status.result(timeout=7)
                assert isinstance(login_result, RuntimeAccessRefusal)
                assert login_result.request_id == login_request.request_id
                assert status_result.request_id == status_request.request_id
                assert not any(secret)
                assert pausing.writes == 2
            finally:
                pausing.release.set()
                client.close()
            serving.result(timeout=7)
    finally:
        endpoint.close()
