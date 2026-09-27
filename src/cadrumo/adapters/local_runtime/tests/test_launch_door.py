"""Real native endpoints with a test manager; no installed-service claims."""

from __future__ import annotations

import asyncio
import socket
import sys
import tempfile
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

from cadrumo.application.runtime.contracts import RuntimeClientHello, RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.management import (
    RuntimeManagerInspection,
    RuntimeManagerKind,
    RuntimeManagerProcessState,
)

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
        connection = await RuntimeLaunchDoor(endpoint, expected=_expected(endpoint)).open()
        connection.close()
        assert manager.process is not None and manager.process.returncode is None


@pytest.mark.asyncio
async def test_missing_manager_refuses_without_direct_launch(tmp_path: Path) -> None:
    async with _fixture(tmp_path) as (_manager, endpoint):
        with pytest.raises(RuntimeRefusalError) as caught:
            await RuntimeLaunchDoor(endpoint, expected=_expected(endpoint)).open()
        assert caught.value.reason is RuntimeRefusalCode.UNAVAILABLE


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
        with pytest.raises(RuntimeRefusalError) as caught:
            await RuntimeLaunchDoor(endpoint, expected=_expected(endpoint), manager=manager).open()
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
            with pytest.raises(asyncio.CancelledError):
                await opening
            assert manager.process is not None and manager.process.stdin is not None
            manager.process.stdin.write(b"release\n")
            await manager.process.stdin.drain()
            assert await manager.line() == b"late_closed\n"
            assert manager.process.returncode is None
        finally:
            if not opening.done():
                opening.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await opening
