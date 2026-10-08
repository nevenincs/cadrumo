"""Whole-runtime headless timing and connection interference in an isolated root."""

from __future__ import annotations

import json
import re
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from importlib.metadata import version
from pathlib import Path

import pytest

from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.application.runtime.contracts import (
    RuntimeClientHello,
    RuntimeExitReason,
    RuntimeRefusalCode,
    RuntimeRefusalError,
)

from ..supervised_protocol import RuntimeHeartbeat, RuntimeStopping
from .test_supervised_runtime import (
    _announcement,
    _boot_of,
    _connect,
    _endpoint,
    _exit_code,
    _log_text,
    _ready,
    _send,
    _supervised,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.mark.asyncio
async def test_headless_runtime_load_and_foreign_interference(tmp_path: Path) -> None:
    endpoint = _endpoint(tmp_path)
    began = time.perf_counter()
    try:
        async with _supervised(tmp_path, endpoint.storage_identity) as process:
            ready = await _ready(process)
            startup_ms = (time.perf_counter() - began) * 1000
            with ExitStack() as cleanup:
                clients = []
                for _ in range(8):
                    client = _connect(endpoint)
                    cleanup.callback(client.close)
                    clients.append(client)

                def requests(client: VerifiedRuntimeConnection) -> list[float]:
                    samples = []
                    for _ in range(16):
                        started = time.perf_counter()
                        assert _boot_of(client) == ready.boot_id
                        samples.append((time.perf_counter() - started) * 1000)
                    return samples

                with ThreadPoolExecutor(max_workers=8) as pool:
                    samples = sorted(sample for batch in pool.map(requests, clients) for sample in batch)

                # A different process must not take the existing owner's endpoint.
                with pytest.raises(RuntimeRefusalError) as foreign:
                    endpoint.listen()
                assert foreign.value.reason is RuntimeRefusalCode.OWNER_BUSY
                for expected, reason in [
                    (
                        RuntimeClientHello(product_version="other-version", storage_identity=endpoint.storage_identity),
                        RuntimeRefusalCode.VERSION_MISMATCH,
                    ),
                    (
                        RuntimeClientHello(product_version=version("cadrumo"), storage_identity="f" * 64),
                        RuntimeRefusalCode.ROOT_MISMATCH,
                    ),
                ]:
                    with pytest.raises(RuntimeRefusalError) as refused:
                        VerifiedRuntimeConnection(
                            endpoint.connect(timeout=2), expected=expected, deadline=time.monotonic() + 3
                        )
                    assert refused.value.reason is reason
                for _ in range(32):
                    abandoned = endpoint.connect(timeout=2)
                    abandoned.close()
                assert _boot_of(clients[0]) == ready.boot_id
                await _send(process, b'{"type":"ping","seq":1}\n')
                heartbeat = await _announcement(process)
                assert isinstance(heartbeat, RuntimeHeartbeat)
                assert heartbeat.in_flight_operations == 0
                assert process.returncode is None
            stopping = time.perf_counter()
            await _send(process, b'{"type":"session-end"}\n')
            assert await _announcement(process) == RuntimeStopping(reason=RuntimeExitReason.SESSION_END_SETTLE)
            assert await _exit_code(process) == RuntimeExitReason.SESSION_END_SETTLE
            print(
                "HEADLESS_BENCHMARK_JSON="
                + json.dumps(
                    {
                        "startup_ms": startup_ms,
                        "startup_phases_ms": {
                            phase: float(seconds) * 1000
                            for phase, seconds in re.findall(
                                r"runtime_startup phase=(\w+) transition=leave elapsed_seconds=([\d.]+)",
                                _log_text(tmp_path),
                            )
                        },
                        "shutdown_ms": (time.perf_counter() - stopping) * 1000,
                        "connections": 8,
                        "requests": len(samples),
                        "p50_ms": statistics.median(samples),
                        "p95_ms": samples[121],
                        "p99_ms": samples[126],
                        "foreign_endpoint_refused": True,
                        "wrong_root_and_version_refused": True,
                        "abrupt_connections": 32,
                    },
                    sort_keys=True,
                )
            )
    finally:
        endpoint.close()
