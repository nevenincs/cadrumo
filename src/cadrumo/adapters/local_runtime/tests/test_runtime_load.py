"""Repeatable native IPC latency and hostile-client recovery checks.

Run with pytest -s to retain RUNTIME_BENCHMARK_JSON records. These measure real
kernel transport and framing, without profile work or interpreter startup.
"""

from __future__ import annotations

import json
import math
import statistics
import struct
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from threading import Barrier
from uuid import UUID, uuid4

import pytest

from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.profile_access import RuntimeSessionRequest

from ..framing import VerifiedRuntimeConnection
from ..posix_endpoint import PosixRuntimeEndpoint
from ..windows import WindowsRuntimeEndpoint
from .retained_server import RetainedRuntimeTransportServer
from .test_server import connect
from .test_server import server as server

pytestmark = [pytest.mark.integration, pytest.mark.hex_inbound_adapter]
type Host = tuple[RetainedRuntimeTransportServer, PosixRuntimeEndpoint | WindowsRuntimeEndpoint]


def exchange(client: VerifiedRuntimeConnection, boot_id: UUID) -> UUID:
    request = RuntimeSessionRequest(action="session_status", request_id=uuid4(), profile_id=uuid4(), session_id=uuid4())
    reply = client.session(request, deadline=time.monotonic() + 3)
    assert reply.request_id == request.request_id
    assert reply.runtime_boot_id == boot_id
    return reply.connection_id


@pytest.mark.parametrize("connections", [1, 8, 24])
def test_concurrent_native_round_trip_benchmark(server: Host, connections: int) -> None:
    host, endpoint = server
    with ExitStack() as cleanup:
        clients = []
        for _ in range(connections):
            client = connect(endpoint)
            cleanup.callback(client.close)
            clients.append(client)
        barrier = Barrier(connections)

        def exercise(client: VerifiedRuntimeConnection) -> tuple[UUID, list[float]]:
            barrier.wait(timeout=5)
            samples = []
            identity = exchange(client, host.identity.boot_id)
            for _ in range(24):
                began = time.perf_counter()
                assert exchange(client, host.identity.boot_id) == identity
                samples.append((time.perf_counter() - began) * 1000)
            return identity, samples

        began = time.perf_counter()
        with ThreadPoolExecutor(max_workers=connections) as pool:
            results = list(pool.map(exercise, clients))
        wall = time.perf_counter() - began
        assert len({identity for identity, _ in results}) == connections
        samples = sorted(sample for _, values in results for sample in values)
        # Warm-to-idle transition included; process CPU includes client threads.
        idle_started = time.process_time()
        time.sleep(0.5)
        idle_cpu = time.process_time() - idle_started
        print(
            "RUNTIME_BENCHMARK_JSON="
            + json.dumps(
                {
                    "connections": connections,
                    "requests": len(samples),
                    "p50_ms": statistics.median(samples),
                    "p95_ms": samples[math.ceil(len(samples) * 0.95) - 1],
                    "p99_ms": samples[math.ceil(len(samples) * 0.99) - 1],
                    "requests_per_second": (len(samples) + connections) / wall,
                    "idle_cpu_ms_over_500ms": idle_cpu * 1000,
                },
                sort_keys=True,
            )
        )
        assert not host.stop.is_set()


def test_malformed_and_stalled_clients_leave_healthy_connections_usable(server: Host) -> None:
    host, endpoint = server
    with ExitStack() as cleanup:
        healthy = connect(endpoint)
        cleanup.callback(healthy.close)
        identity = exchange(healthy, host.identity.boot_id)
        for _ in range(8):
            stalled = endpoint.connect(timeout=2)
            cleanup.callback(stalled.close)
            stalled.write_all(b"J", deadline=time.monotonic() + 2)
        payloads = [
            b"S\x00\x00\x00\x01x",
            b"J\xff\xff\xff\xff",
            b"J\x00\x00\x00\x01\xff",
            b"J\x00\x00\x00\x01{",
            b"J\x00\x00\x00\x00",
        ]
        nested = b"[" * 2000 + b"0" + b"]" * 2000
        payloads.append(b"J" + struct.pack("!I", len(nested)) + nested)
        for payload in payloads * 3:
            raw = endpoint.connect(timeout=2)
            try:
                raw.write_all(payload, deadline=time.monotonic() + 2)
                with pytest.raises(RuntimeRefusalError) as refused:
                    raw.read_exact(1, deadline=time.monotonic() + 2)
                assert refused.value.reason is RuntimeRefusalCode.CONNECTION_CLOSED
            finally:
                raw.close()
            assert exchange(healthy, host.identity.boot_id) == identity
        assert not host.stop.is_set()


def test_capacity_exhaustion_refuses_extra_peer_then_recovers(server: Host) -> None:
    host, endpoint = server
    with ExitStack() as cleanup:
        for _ in range(32):
            raw = endpoint.connect(timeout=2)
            cleanup.callback(raw.close)
        deadline = time.monotonic() + 2
        while host.open_connection_count() < 32 and time.monotonic() < deadline:
            time.sleep(0.005)
        assert host.open_connection_count() == 32
        with pytest.raises(RuntimeRefusalError):
            extra = connect(endpoint)
            extra.close()
        assert not host.stop.is_set()
    deadline = time.monotonic() + 3
    while host.open_connection_count() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert host.open_connection_count() == 0
    healthy = connect(endpoint)
    try:
        exchange(healthy, host.identity.boot_id)
    finally:
        healthy.close()


def test_abrupt_connection_churn_does_not_stop_the_listener(server: Host) -> None:
    host, endpoint = server
    for _ in range(512):
        raw = endpoint.connect(timeout=2)
        raw.close()
    healthy = connect(endpoint)
    try:
        exchange(healthy, host.identity.boot_id)
        assert not host.stop.is_set()
    finally:
        healthy.close()


def test_shutdown_cancels_stalled_frames_before_handshake_deadlines(server: Host) -> None:
    host, endpoint = server
    with ExitStack() as cleanup:
        stalled = []
        for index in range(16):
            raw = endpoint.connect(timeout=2)
            cleanup.callback(raw.close)
            stalled.append(raw)
            if index % 2:
                raw.write_all(b"J", deadline=time.monotonic() + 2)
        deadline = time.monotonic() + 2
        while host.open_connection_count() < 16 and time.monotonic() < deadline:
            time.sleep(0.005)
        assert host.open_connection_count() == 16
        began = time.monotonic()
        host.stop.set()
        for raw in stalled:
            with pytest.raises(RuntimeRefusalError) as closed:
                raw.read_exact(1, deadline=began + 3)
            assert closed.value.reason is RuntimeRefusalCode.CONNECTION_CLOSED
        while host.open_connection_count() and time.monotonic() < began + 3:
            time.sleep(0.005)
        assert host.open_connection_count() == 0
        assert time.monotonic() - began < 3
