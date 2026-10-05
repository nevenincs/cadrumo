"""Concurrent real native connections through the production transport host."""

from __future__ import annotations

import struct
import sys
import tempfile
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest

from cadrumo.application.runtime.contracts import RuntimeClientHello, RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.profile_access import RuntimeSessionRequest

from ..framing import VerifiedRuntimeConnection
from ..posix_endpoint import PosixRuntimeEndpoint
from ..windows import WindowsRuntimeEndpoint
from .process_support import runtime_namespace_base
from .retained_server import RetainedRuntimeTransportServer

pytestmark = [pytest.mark.integration, pytest.mark.hex_inbound_adapter]


@pytest.fixture
def server(
    tmp_path: Path,
) -> Iterator[tuple[RetainedRuntimeTransportServer, PosixRuntimeEndpoint | WindowsRuntimeEndpoint]]:
    with tempfile.TemporaryDirectory(prefix="s-", dir=runtime_namespace_base()) as folder:
        endpoint = (
            WindowsRuntimeEndpoint(storage_root=tmp_path)
            if sys.platform == "win32"
            else PosixRuntimeEndpoint(storage_root=tmp_path, namespace=Path(folder) / "ipc")
        )
        stop = Event()
        host = RetainedRuntimeTransportServer(endpoint, product_version="test-cohort", stop=stop)
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(host.serve)
            try:
                assert host.ready.wait(3)
                yield host, endpoint
            finally:
                stop.set()
                running.result(timeout=7)


def connect(endpoint: PosixRuntimeEndpoint | WindowsRuntimeEndpoint, *, version: str = "test-cohort"):
    return VerifiedRuntimeConnection(
        endpoint.connect(timeout=2),
        expected=RuntimeClientHello(product_version=version, storage_identity=endpoint.storage_identity),
        deadline=time.monotonic() + 2,
    )


def test_connection_identity_and_disconnect_are_independent(server) -> None:
    host, endpoint = server
    first, second = connect(endpoint), connect(endpoint)
    try:
        request = RuntimeSessionRequest(
            action="session_status", request_id=uuid4(), profile_id=uuid4(), session_id=uuid4()
        )
        a = first.session(request, deadline=time.monotonic() + 2)
        b = second.session(request, deadline=time.monotonic() + 2)
        assert a.connection_id != b.connection_id
        assert a.runtime_boot_id == b.runtime_boot_id == host.identity.boot_id
        first.close()
        again = second.session(
            RuntimeSessionRequest(action="session_status", request_id=uuid4(), profile_id=uuid4(), session_id=uuid4()),
            deadline=time.monotonic() + 2,
        )
        assert again.connection_id == b.connection_id
        assert set(again.model_dump()) == {
            "kind",
            "request_id",
            "runtime_boot_id",
            "connection_id",
            "code",
        }
    finally:
        first.close()
        second.close()


def test_wrong_cohort_ends_only_the_refused_connection(server) -> None:
    host, endpoint = server
    with pytest.raises(RuntimeRefusalError) as refusal:
        connect(endpoint, version="other-cohort")
    assert refusal.value.reason is RuntimeRefusalCode.VERSION_MISMATCH
    accepted = connect(endpoint)
    try:
        assert (
            accepted.session(
                RuntimeSessionRequest(
                    action="session_status", request_id=uuid4(), profile_id=uuid4(), session_id=uuid4()
                ),
                deadline=time.monotonic() + 2,
            ).runtime_boot_id
            == host.identity.boot_id
        )
    finally:
        accepted.close()


def test_idle_connection_survives_frame_deadline_and_stop_does_not_wait_for_input(server) -> None:
    host, endpoint = server
    client = connect(endpoint)
    try:
        original = client.session(
            RuntimeSessionRequest(action="session_status", request_id=uuid4(), profile_id=uuid4(), session_id=uuid4()),
            deadline=time.monotonic() + 2,
        )
        time.sleep(5.2)
        current = client.session(
            RuntimeSessionRequest(action="session_status", request_id=uuid4(), profile_id=uuid4(), session_id=uuid4()),
            deadline=time.monotonic() + 2,
        )
        assert current.connection_id == original.connection_id
        stopped = time.monotonic()
        host.stop.set()
        with pytest.raises(RuntimeRefusalError) as closed:
            client._channel.read_exact(1, deadline=stopped + 2)
        assert closed.value.reason is RuntimeRefusalCode.CONNECTION_CLOSED
        assert time.monotonic() - stopped < 2
    finally:
        client.close()


def test_partial_post_handshake_frame_still_has_a_total_deadline(server) -> None:
    _host, endpoint = server
    client = connect(endpoint)
    try:
        client._channel.write_all(b"J", deadline=time.monotonic() + 2)
        began = time.monotonic()
        with pytest.raises(RuntimeRefusalError) as closed:
            client._channel.read_exact(1, deadline=began + 7)
        assert closed.value.reason is RuntimeRefusalCode.CONNECTION_CLOSED
        assert 4 < time.monotonic() - began < 7
    finally:
        client.close()


@pytest.mark.parametrize("malformed", [b"S\x00\x00\x00\x08sentinel", b"J\x00\x01\x00\x01", b"J\x00\x00\x00\x01{"])
def test_secret_oversized_or_malformed_first_frame_never_reaches_application(server, malformed: bytes) -> None:
    _host, endpoint = server
    raw = endpoint.connect(timeout=2)
    try:
        raw.write_all(malformed, deadline=time.monotonic() + 2)
        with pytest.raises(RuntimeRefusalError) as refusal:
            raw.read_exact(1, deadline=time.monotonic() + 2)
        assert refusal.value.reason is RuntimeRefusalCode.CONNECTION_CLOSED
    finally:
        raw.close()
    accepted = connect(endpoint)
    accepted.close()


def test_duplicate_hello_keys_refuse_before_credential_frames(server) -> None:
    _host, endpoint = server
    payload = b'{"kind":"client_hello","kind":"client_hello"}'
    raw = endpoint.connect(timeout=2)
    try:
        raw.write_all(b"J" + struct.pack("!I", len(payload)) + payload, deadline=time.monotonic() + 2)
        with pytest.raises(RuntimeRefusalError):
            raw.read_exact(1, deadline=time.monotonic() + 2)
    finally:
        raw.close()


def test_accept_loop_tick_and_open_connections_are_observable(server) -> None:
    host, endpoint = server
    age = host.accept_tick_age()
    assert age is not None and age < 2
    assert host.open_connection_count() == 0
    client = connect(endpoint)
    try:
        client.session(
            RuntimeSessionRequest(action="session_status", request_id=uuid4(), profile_id=uuid4(), session_id=uuid4()),
            deadline=time.monotonic() + 2,
        )
        assert host.open_connection_count() == 1
    finally:
        client.close()
    deadline = time.monotonic() + 3
    while host.open_connection_count() and time.monotonic() < deadline:
        time.sleep(0.02)
    assert host.open_connection_count() == 0
    age = host.accept_tick_age()
    assert age is not None and age < 2


def test_accept_tick_is_absent_before_serving(tmp_path: Path) -> None:
    endpoint = (
        WindowsRuntimeEndpoint(storage_root=tmp_path)
        if sys.platform == "win32"
        else PosixRuntimeEndpoint(storage_root=tmp_path)
    )
    host = RetainedRuntimeTransportServer(endpoint, product_version="test-cohort", stop=Event())
    assert host.accept_tick_age() is None
    assert host.open_connection_count() == 0
