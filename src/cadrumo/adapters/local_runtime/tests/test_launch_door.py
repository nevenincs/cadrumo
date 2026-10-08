"""Real native endpoints with explicitly owned test processes."""

from __future__ import annotations

import asyncio
import sys
import tempfile
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

from cadrumo.application.runtime.contracts import (
    RuntimeByteChannel,
    RuntimeClientHello,
    RuntimePeer,
    RuntimeRefusalCode,
    RuntimeRefusalError,
)
from cadrumo.core.async_cleanup import AsyncResourceCleanupError, close_async_resources

from ..posix_endpoint import PosixRuntimeEndpoint
from ..runtime_transport_cleanup import RuntimeTransportCleanup
from ..startup import RuntimeLaunchDoor
from ..windows import WindowsRuntimeEndpoint
from .process_support import launch_fixture, runtime_namespace_base

pytestmark = [pytest.mark.integration, pytest.mark.hex_inbound_adapter]


class _RuntimeProcess:
    """Explicit lifetime ownership for a real finite runtime fixture."""

    def __init__(self, root: Path, namespace: Path) -> None:
        self.root, self.namespace = root, namespace
        self.process: asyncio.subprocess.Process | None = None
        self.version = "synthetic-cohort"
        self.mode = "normal"
        self.start_count = 0
        self.launch_enabled = True
        self.lock = asyncio.Lock()

    async def start(self) -> None:
        self.start_count += 1
        async with self.lock:
            if self.process is None and self.launch_enabled:
                self.process = await launch_fixture(
                    "cadrumo.adapters.local_runtime.tests.readiness_fixture",
                    str(self.root),
                    str(self.namespace),
                    self.version,
                    self.mode,
                )
                assert await self.line() == b"ready\n"

    async def line(self) -> bytes:
        assert self.process is not None and self.process.stdout is not None
        return (await asyncio.wait_for(self.process.stdout.readline(), timeout=15)).replace(b"\r\n", b"\n")

    async def cleanup(self) -> None:
        if self.process is not None:
            if self.process.returncode is None:
                self.process.kill()
            _output, errors = await asyncio.wait_for(self.process.communicate(), timeout=5)
            assert not errors, errors.decode(errors="replace")


@asynccontextmanager
async def _fixture(root: Path) -> AsyncIterator[tuple[_RuntimeProcess, PosixRuntimeEndpoint | WindowsRuntimeEndpoint]]:
    with tempfile.TemporaryDirectory(prefix="s-", dir=runtime_namespace_base()) as folder:
        namespace = Path(folder) / "ipc"
        runtime = _RuntimeProcess(root, namespace)
        endpoint = (
            WindowsRuntimeEndpoint(storage_root=root)
            if sys.platform == "win32"
            else PosixRuntimeEndpoint(storage_root=root, namespace=namespace)
        )
        try:
            yield runtime, endpoint
        finally:
            try:
                await runtime.cleanup()
            finally:
                endpoint.close()


def _expected(endpoint: PosixRuntimeEndpoint | WindowsRuntimeEndpoint) -> RuntimeClientHello:
    return RuntimeClientHello(product_version="synthetic-cohort", storage_identity=endpoint.storage_identity)


@pytest.mark.asyncio
async def test_fixture_reaps_owned_runtime_after_assertion_failure(tmp_path: Path) -> None:
    runtime: _RuntimeProcess | None = None
    with pytest.raises(AssertionError, match="synthetic test failure"):
        async with _fixture(tmp_path) as (runtime, endpoint):
            await runtime.start()
            connection = await RuntimeLaunchDoor(endpoint, expected=_expected(endpoint)).open()
            connection.close()
            raise AssertionError("synthetic test failure")
    assert runtime is not None and runtime.process is not None
    assert runtime.process.returncode is not None


@pytest.mark.asyncio
async def test_concurrent_clients_share_existing_owner_and_disconnect_does_not_stop(tmp_path: Path) -> None:
    async with _fixture(tmp_path) as (runtime, endpoint):
        await runtime.start()
        door = RuntimeLaunchDoor(endpoint, expected=_expected(endpoint))
        connections = await asyncio.gather(door.open(timeout=20), door.open(timeout=20))
        try:
            assert connections[0].hello.boot_id == connections[1].hello.boot_id
            connections[0].close()
            subsequent = await door.open()
            try:
                assert subsequent.hello.boot_id == connections[1].hello.boot_id
            finally:
                subsequent.close()
        finally:
            for connection in connections:
                connection.close()


@pytest.mark.asyncio
async def test_existing_ready_owner_is_reused(tmp_path: Path) -> None:
    async with _fixture(tmp_path) as (runtime, endpoint):
        await runtime.start()

        connection = await RuntimeLaunchDoor(endpoint, expected=_expected(endpoint)).open()
        connection.close()
        assert runtime.process is not None and runtime.process.returncode is None


@pytest.mark.asyncio
async def test_missing_endpoint_refuses_without_direct_launch(tmp_path: Path) -> None:
    async with _fixture(tmp_path) as (_runtime, endpoint):
        with pytest.raises(RuntimeRefusalError) as caught:
            await RuntimeLaunchDoor(endpoint, expected=_expected(endpoint)).open()
        assert caught.value.reason is RuntimeRefusalCode.UNAVAILABLE


@pytest.mark.asyncio
async def test_cross_root_composition_refuses_before_connecting_or_launching(tmp_path: Path) -> None:
    async with _fixture(tmp_path) as (runtime, endpoint):
        expected = _expected(endpoint).model_copy(update={"storage_identity": "f" * 64})
        with pytest.raises(RuntimeRefusalError) as caught:
            RuntimeLaunchDoor(endpoint, expected=expected)
        assert caught.value.reason is RuntimeRefusalCode.ROOT_MISMATCH
        assert runtime.start_count == 0


@pytest.mark.asyncio
async def test_foreign_cohort_is_refused_without_restart_or_repair(tmp_path: Path) -> None:
    async with _fixture(tmp_path) as (runtime, endpoint):
        runtime.version = "different-cohort"
        await runtime.start()

        with pytest.raises(RuntimeRefusalError) as caught:
            await RuntimeLaunchDoor(endpoint, expected=_expected(endpoint)).open()
        assert caught.value.reason is RuntimeRefusalCode.VERSION_MISMATCH
        assert runtime.start_count == 1
        assert runtime.process is not None and runtime.process.returncode is None


@pytest.mark.asyncio
async def test_cancelled_handshake_closes_late_connection_without_stopping_owner(tmp_path: Path) -> None:
    async with _fixture(tmp_path) as (runtime, endpoint):
        runtime.mode = "blocked"
        await runtime.start()
        opening = asyncio.create_task(RuntimeLaunchDoor(endpoint, expected=_expected(endpoint)).open())
        try:
            assert await runtime.line() == b"handshake\n"
            opening.cancel()
            await asyncio.sleep(0)
            assert not opening.done(), "cancellation must retain native handshake cleanup"
            assert runtime.process is not None and runtime.process.stdin is not None
            runtime.process.stdin.write(b"release\n")
            await runtime.process.stdin.drain()
            with pytest.raises(asyncio.CancelledError):
                await opening
            assert await runtime.line() == b"late_closed\n"
            assert runtime.process.returncode is None
        finally:
            if not opening.done():
                opening.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await opening


class _FailOnceNativeChannel:
    """Preserve real native I/O while refusing the first owned release."""

    def __init__(self, channel: RuntimeByteChannel) -> None:
        self.channel = channel
        self.close_calls = 0
        self.close_threads: list[int] = []
        self.released = False

    @property
    def peer(self) -> RuntimePeer:
        return self.channel.peer

    def read_exact(self, count: int, *, deadline: float) -> bytes:
        return self.channel.read_exact(count, deadline=deadline)

    def read_ready(self) -> bool:
        return self.channel.read_ready()

    def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:
        self.channel.write_all(payload, deadline=deadline)

    def close(self) -> None:
        if self.released:
            return
        self.close_threads.append(threading.get_ident())
        self.close_calls += 1
        if self.close_calls == 1:
            raise OSError("synthetic native close failure")
        self.channel.close()
        self.released = True


class _FaultEndpoint:
    def __init__(self, endpoint: PosixRuntimeEndpoint | WindowsRuntimeEndpoint) -> None:
        self.endpoint = endpoint
        self.channel: _FailOnceNativeChannel | None = None

    @property
    def storage_identity(self) -> str:
        return self.endpoint.storage_identity

    def connect(self, *, timeout: float) -> _FailOnceNativeChannel:
        self.channel = _FailOnceNativeChannel(self.endpoint.connect(timeout=timeout))
        return self.channel


@pytest.mark.asyncio
async def test_cancelled_native_handshake_failed_close_retains_owner_until_retry(tmp_path: Path) -> None:
    async with _fixture(tmp_path) as (runtime, endpoint):
        runtime.mode = "blocked"
        await runtime.start()
        fault = _FaultEndpoint(endpoint)
        opening = asyncio.create_task(RuntimeLaunchDoor(fault, expected=_expected(endpoint)).open())
        try:
            assert await runtime.line() == b"handshake\n"
            opening.cancel("native handshake cancellation")
            assert runtime.process is not None and runtime.process.stdin is not None
            runtime.process.stdin.write(b"release\n")
            await runtime.process.stdin.drain()
            with pytest.raises(asyncio.CancelledError) as caught:
                await opening
            assert caught.value.args == ("native handshake cancellation",)
            cleanup = caught.value.__dict__.get("async_cleanup_error")
            assert isinstance(cleanup, AsyncResourceCleanupError)
            assert fault.channel is not None
            assert fault.channel.close_calls == 1
            assert not fault.channel.released
            assert all(identity != threading.get_ident() for identity in fault.channel.close_threads)
            await cleanup.retry_cleanup()
            await cleanup.retry_cleanup()
            assert fault.channel.close_calls == 2
            assert fault.channel.released
            assert await runtime.line() == b"late_closed\n"
            assert runtime.process.returncode is None
        finally:
            if not opening.done():
                opening.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await opening
            if fault.channel is not None:
                await close_async_resources(
                    RuntimeTransportCleanup(fault.channel), task_name="native-launch-test-close"
                )
