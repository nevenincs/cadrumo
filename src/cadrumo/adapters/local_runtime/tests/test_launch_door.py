"""Real native endpoints with a test manager; no installed-service claims."""

from __future__ import annotations

import asyncio
import socket
import sys
import tempfile
import threading
import time
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
from cadrumo.application.runtime.management import (
    RuntimeManagerInspection,
    RuntimeManagerKind,
    RuntimeManagerProcessState,
)
from cadrumo.core.async_cleanup import AsyncResourceCleanupError, close_async_resources

from ..framing import RuntimeTransportCleanup
from ..posix import PosixRuntimeEndpoint
from ..startup import RuntimeLaunchDoor
from ..windows import WindowsRuntimeEndpoint
from .process_support import launch_fixture

pytestmark = [pytest.mark.integration, pytest.mark.hex_inbound_adapter]


class _FixtureManager:
    """An explicit manager double launching real, finite, test-owned processes."""

    def __init__(self, root: Path, namespace: Path) -> None:
        self.root, self.namespace = root, namespace
        self.process: asyncio.subprocess.Process | None = None
        self.version = "synthetic-cohort"
        self.mode = "normal"
        self.start_count = 0
        self.launch_enabled = True
        self.lock = asyncio.Lock()
        self.inspection = RuntimeManagerInspection(
            kind=RuntimeManagerKind.WINDOWS_TASK,
            available=True,
            provisioned=True,
            binding_matches=True,
            login_autostart=False,
            process_state=RuntimeManagerProcessState.STOPPED,
        )

    async def inspect(self) -> RuntimeManagerInspection:
        return self.inspection

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

    async def stop(self) -> None:
        raise AssertionError("a client launch door must never stop the shared runtime")

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
async def _fixture(root: Path) -> AsyncIterator[tuple[_FixtureManager, PosixRuntimeEndpoint | WindowsRuntimeEndpoint]]:
    temporary_parent = None if sys.platform == "win32" else Path("/") / "tmp"
    with tempfile.TemporaryDirectory(prefix="cr-door-", dir=temporary_parent) as folder:
        namespace = Path(folder) / "ipc"
        manager = _FixtureManager(root, namespace)
        endpoint = (
            WindowsRuntimeEndpoint(storage_root=root)
            if sys.platform == "win32"
            else PosixRuntimeEndpoint(storage_root=root, namespace=namespace)
        )
        try:
            yield manager, endpoint
        finally:
            await manager.cleanup()
            endpoint.close()


def _expected(endpoint: PosixRuntimeEndpoint | WindowsRuntimeEndpoint) -> RuntimeClientHello:
    return RuntimeClientHello(product_version="synthetic-cohort", storage_identity=endpoint.storage_identity)


@pytest.mark.asyncio
async def test_concurrent_clients_converge_with_autostart_disabled_and_disconnect_does_not_stop(tmp_path: Path) -> None:
    async with _fixture(tmp_path) as (manager, endpoint):
        door = RuntimeLaunchDoor(endpoint, expected=_expected(endpoint), manager=manager)
        connections = await asyncio.gather(door.open(timeout=20), door.open(timeout=20))
        try:
            assert connections[0].hello.boot_id == connections[1].hello.boot_id
            connections[0].close()
            subsequent = await door.open()
            try:
                assert subsequent.hello.boot_id == connections[1].hello.boot_id
                assert not manager.inspection.login_autostart
            finally:
                subsequent.close()
        finally:
            for connection in connections:
                connection.close()


@pytest.mark.asyncio
async def test_existing_ready_owner_needs_no_manager(tmp_path: Path) -> None:
    async with _fixture(tmp_path) as (manager, endpoint):
        await manager.start()

        def unexpected_manager() -> _FixtureManager:
            raise AssertionError("a verified ready owner must not construct a manager")

        connection = await RuntimeLaunchDoor(
            endpoint, expected=_expected(endpoint), manager_factory=unexpected_manager
        ).open()
        connection.close()
        assert manager.process is not None and manager.process.returncode is None


@pytest.mark.asyncio
async def test_missing_manager_refuses_without_direct_launch(tmp_path: Path) -> None:
    async with _fixture(tmp_path) as (_manager, endpoint):
        with pytest.raises(RuntimeRefusalError) as caught:
            await RuntimeLaunchDoor(endpoint, expected=_expected(endpoint)).open()
        assert caught.value.reason is RuntimeRefusalCode.UNAVAILABLE


@pytest.mark.asyncio
async def test_missing_endpoint_constructs_manager_once_for_existing_provisioning(tmp_path: Path) -> None:
    async with _fixture(tmp_path) as (manager, endpoint):
        factory_calls = 0

        def manager_factory() -> _FixtureManager:
            nonlocal factory_calls
            factory_calls += 1
            return manager

        connection = await RuntimeLaunchDoor(
            endpoint, expected=_expected(endpoint), manager_factory=manager_factory
        ).open(timeout=20)
        try:
            assert factory_calls == 1
            assert manager.start_count == 1
        finally:
            connection.close()


@pytest.mark.asyncio
@pytest.mark.skipif(sys.platform == "win32", reason="requires native Unix endpoint substitution")
@pytest.mark.parametrize("kind", ["regular_file", "symlink", "stale_socket"])
async def test_only_missing_or_stale_endpoint_can_trigger_launch(tmp_path: Path, kind: str) -> None:
    if sys.platform == "win32":
        pytest.skip("requires native Unix endpoint substitution")
    async with _fixture(tmp_path) as (manager, endpoint):
        path = manager.namespace / (endpoint.storage_identity[:32] + ".sock")
        target = tmp_path / "untouched"
        target.write_bytes(b"synthetic unrelated content")
        if kind == "symlink":
            path.symlink_to(target)
        elif kind == "regular_file":
            path.write_bytes(b"untrusted endpoint")
        else:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as stale:
                stale.bind(str(path))
        door = RuntimeLaunchDoor(endpoint, expected=_expected(endpoint), manager=manager)
        if kind == "stale_socket":
            connection = await door.open(timeout=20)
            connection.close()
            assert manager.start_count == 1
        else:
            original = path.lstat()
            with pytest.raises(RuntimeRefusalError) as caught:
                await door.open()
            assert caught.value.reason is RuntimeRefusalCode.ENDPOINT_UNTRUSTED
            assert manager.start_count == 0
            assert path.lstat().st_ino == original.st_ino
        assert target.read_bytes() == b"synthetic unrelated content"


@pytest.mark.asyncio
async def test_cross_root_composition_refuses_before_connecting_or_launching(tmp_path: Path) -> None:
    async with _fixture(tmp_path) as (manager, endpoint):
        expected = _expected(endpoint).model_copy(update={"storage_identity": "f" * 64})
        with pytest.raises(RuntimeRefusalError) as caught:
            RuntimeLaunchDoor(endpoint, expected=expected, manager=manager)
        assert caught.value.reason is RuntimeRefusalCode.ROOT_MISMATCH
        assert manager.start_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["available", "provisioned", "binding_matches"])
async def test_unavailable_or_changed_provisioning_never_launches(tmp_path: Path, field: str) -> None:
    async with _fixture(tmp_path) as (manager, endpoint):
        manager.inspection = manager.inspection.model_copy(update={field: False})
        with pytest.raises(RuntimeRefusalError) as caught:
            await RuntimeLaunchDoor(endpoint, expected=_expected(endpoint), manager=manager).open()
        expected = RuntimeRefusalCode.VERSION_MISMATCH if field == "binding_matches" else RuntimeRefusalCode.UNAVAILABLE
        assert caught.value.reason is expected
        assert manager.start_count == 0


@pytest.mark.asyncio
async def test_foreign_cohort_is_refused_without_restart_or_repair(tmp_path: Path) -> None:
    async with _fixture(tmp_path) as (manager, endpoint):
        manager.version = "different-cohort"
        await manager.start()

        def unexpected_manager() -> _FixtureManager:
            raise AssertionError("an incompatible peer must not invoke manager provisioning")

        with pytest.raises(RuntimeRefusalError) as caught:
            await RuntimeLaunchDoor(endpoint, expected=_expected(endpoint), manager_factory=unexpected_manager).open()
        assert caught.value.reason is RuntimeRefusalCode.VERSION_MISMATCH
        assert manager.start_count == 1
        assert manager.process is not None and manager.process.returncode is None


@pytest.mark.asyncio
async def test_accepted_start_without_readiness_times_out_without_repeated_start(tmp_path: Path) -> None:
    async with _fixture(tmp_path) as (manager, endpoint):
        manager.launch_enabled = False
        started = time.monotonic()
        with pytest.raises(RuntimeRefusalError) as caught:
            await RuntimeLaunchDoor(endpoint, expected=_expected(endpoint), manager=manager).open(timeout=0.2)
        assert caught.value.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED
        assert manager.start_count == 1
        assert time.monotonic() - started < 2


@pytest.mark.asyncio
async def test_cancelled_handshake_closes_late_connection_without_stopping_owner(tmp_path: Path) -> None:
    async with _fixture(tmp_path) as (manager, endpoint):
        manager.mode = "blocked"
        await manager.start()
        opening = asyncio.create_task(RuntimeLaunchDoor(endpoint, expected=_expected(endpoint), manager=manager).open())
        try:
            assert await manager.line() == b"handshake\n"
            opening.cancel()
            await asyncio.sleep(0)
            assert not opening.done(), "cancellation must retain native handshake cleanup"
            assert manager.process is not None and manager.process.stdin is not None
            manager.process.stdin.write(b"release\n")
            await manager.process.stdin.drain()
            with pytest.raises(asyncio.CancelledError):
                await opening
            assert await manager.line() == b"late_closed\n"
            assert manager.process.returncode is None
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
    async with _fixture(tmp_path) as (manager, endpoint):
        manager.mode = "blocked"
        await manager.start()
        fault = _FaultEndpoint(endpoint)
        opening = asyncio.create_task(RuntimeLaunchDoor(fault, expected=_expected(endpoint), manager=manager).open())
        try:
            assert await manager.line() == b"handshake\n"
            opening.cancel("native handshake cancellation")
            assert manager.process is not None and manager.process.stdin is not None
            manager.process.stdin.write(b"release\n")
            await manager.process.stdin.drain()
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
            assert await manager.line() == b"late_closed\n"
            assert manager.process.returncode is None
        finally:
            if not opening.done():
                opening.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await opening
            if fault.channel is not None:
                await close_async_resources(
                    RuntimeTransportCleanup(fault.channel), task_name="native-launch-test-close"
                )
