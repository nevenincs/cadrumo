"""Concurrent real owners converge and release identity after abrupt death."""

from __future__ import annotations

import asyncio
import sys
import tempfile
import time
from pathlib import Path

import pytest

from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError

from ..posix_endpoint import PosixRuntimeEndpoint
from ..windows import WindowsRuntimeEndpoint
from .process_support import launch_fixture, runtime_namespace_base

pytestmark = [pytest.mark.integration, pytest.mark.hex_inbound_adapter]


async def _line(process: asyncio.subprocess.Process, *, timeout: float = 5) -> bytes:
    assert process.stdout is not None
    return (await asyncio.wait_for(process.stdout.readline(), timeout=timeout)).replace(b"\r\n", b"\n")


async def _launch(root: Path, namespace: Path) -> asyncio.subprocess.Process:
    return await launch_fixture("cadrumo.adapters.local_runtime.tests.endpoint_fixture", str(root), str(namespace))


async def _start(process: asyncio.subprocess.Process) -> None:
    assert process.stdin is not None
    process.stdin.write(b"start\n")
    await process.stdin.drain()


@pytest.mark.asyncio
async def test_launch_race_converges_and_abrupt_owner_death_allows_replacement(tmp_path: Path) -> None:
    processes: list[asyncio.subprocess.Process] = []
    # Operators can refine the socket base when a checkout exceeds the Unix path limit.
    with tempfile.TemporaryDirectory(prefix="s-", dir=runtime_namespace_base()) as folder:
        namespace = Path(folder) / "ipc"
        try:
            first = await _launch(tmp_path, namespace)
            processes.append(first)
            second = await _launch(tmp_path, namespace)
            processes.append(second)
            # Cold interpreter/dependency loading is outside the launch race.
            # Keep its finite allowance separate from native ownership and
            # readiness deadlines below (including on a busy remote Mac).
            barriers = await asyncio.gather(_line(first, timeout=15), _line(second, timeout=15))
            assert barriers == [b"waiting\n", b"waiting\n"]
            await asyncio.gather(_start(first), _start(second))
            results = await asyncio.gather(_line(first), _line(second))
            assert sorted(results) == [b"busy\n", b"ready\n"]
            winner = processes[results.index(b"ready\n")]
            loser = processes[results.index(b"busy\n")]
            assert await asyncio.wait_for(loser.wait(), timeout=5) == 0
            endpoint = (
                WindowsRuntimeEndpoint(storage_root=tmp_path)
                if sys.platform == "win32"
                else PosixRuntimeEndpoint(storage_root=tmp_path, namespace=namespace)
            )
            try:
                channel = endpoint.connect(timeout=1)
                try:
                    assert channel.peer.process_id == winner.pid
                    # Keep the connection open across abrupt server loss.
                    # The client must observe loss and release its old pipe
                    # instance before attempting replacement startup.
                    winner.kill()
                    await asyncio.wait_for(winner.wait(), timeout=5)
                    with pytest.raises(RuntimeRefusalError) as caught:
                        channel.read_exact(1, deadline=time.monotonic() + 1)
                    assert caught.value.reason is RuntimeRefusalCode.CONNECTION_CLOSED
                finally:
                    channel.close()
            finally:
                endpoint.close()
            replacement = await _launch(tmp_path, namespace)
            processes.append(replacement)
            assert await _line(replacement, timeout=15) == b"waiting\n"
            await _start(replacement)
            assert await _line(replacement) == b"ready\n"
            assert replacement.stdin is not None
            replacement.stdin.close()
            assert await asyncio.wait_for(replacement.wait(), timeout=5) == 0
        finally:
            for process in processes:
                if process.returncode is None:
                    process.kill()
                _output, errors = await asyncio.wait_for(process.communicate(), timeout=5)
                assert not errors, errors.decode(errors="replace")
