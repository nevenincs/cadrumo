"""Opt-in real LaunchAgent configuration/control for one disposable job.

Set ``CADRUMO_TEST_MACOS_MANAGER=1`` in the native Aqua user bootstrap domain.
Missing native capability then fails, rather than skipping acceptance. The
process is a synthetic sleeper, not the application runtime: this proves real
manager binding/control and process exit, not private admission, browser or
independent-descendant containment. No existing user job is replaced.
"""

from __future__ import annotations

import asyncio
import os
import plistlib
import stat
import sys
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import cast

import pytest

from cadrumo.application.runtime.management import (
    RuntimeManagerKind,
    RuntimeManagerProcessState,
    RuntimeServiceBinding,
)
from cadrumo.core.async_cleanup import await_cancellation_complete

from .. import macos_manager as native
from ..macos_manager import MacosUserManager
from ..macos_process import MacosProcessWatch, read_macos_process
from ..posix import posix_owner_uid, posix_storage_identity
from ..service_definitions import macos_agent_plist, runtime_service_name

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_outbound_adapter,
    pytest.mark.external_tool,
    pytest.mark.serial,
    pytest.mark.skipif(sys.platform != "darwin", reason="requires native macOS launchd"),
]


def _select() -> None:
    selected = os.environ.get("CADRUMO_TEST_MACOS_MANAGER")
    if selected is None:
        pytest.skip("requires explicit disposable native LaunchAgent acceptance selection")
    if selected != "1":
        pytest.fail("native LaunchAgent acceptance selector must be 1", pytrace=False)


async def _wait_running(
    manager: MacosUserManager,
    platform: native._NativeMacosLaunchd,
    binding: RuntimeServiceBinding,
    *,
    timeout: float = 10,
) -> int:
    deadline = time.monotonic() + timeout
    while True:
        facts = await manager.inspect()
        assert facts.available and facts.binding_matches and facts.provisioned
        if facts.process_state is RuntimeManagerProcessState.RUNNING:
            job = await platform.job(binding)
            assert job.process_id is not None
            return job.process_id
        if time.monotonic() >= deadline:
            pytest.fail("owned native LaunchAgent did not become running within its bound", pytrace=False)
        await asyncio.sleep(0.05)


def _remove_exact_definition(directory: int, name: str, binding: RuntimeServiceBinding) -> None:
    try:
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=directory)
    except FileNotFoundError:
        return
    try:
        metadata = os.fstat(descriptor)
        assert stat.S_ISREG(metadata.st_mode) and metadata.st_uid == posix_owner_uid()
        assert metadata.st_nlink == 1 and not metadata.st_mode & 0o077 and metadata.st_size <= 64 * 1024
        payload = os.read(descriptor, 64 * 1024 + 1)
        assert payload in (
            macos_agent_plist(binding, login_autostart=False),
            macos_agent_plist(binding, login_autostart=True),
        )
        current = os.stat(name, dir_fd=directory, follow_symlinks=False)
        assert (metadata.st_dev, metadata.st_ino) == (current.st_dev, current.st_ino)
        os.unlink(name, dir_fd=directory)
        os.fsync(directory)
    finally:
        os.close(descriptor)


async def _wait_unregistered(binding: RuntimeServiceBinding) -> None:
    deadline = time.monotonic() + 5
    while native._native_job_dictionary(runtime_service_name(binding)) is not None:
        if time.monotonic() >= deadline:
            pytest.fail("owned native LaunchAgent remained registered after bootout", pytrace=False)
        await asyncio.sleep(0.05)


async def _cleanup_owned_agent(
    platform: native._NativeMacosLaunchd, directory: int, binding: RuntimeServiceBinding
) -> None:
    label = runtime_service_name(binding)
    name = label + ".plist"
    lock_name = name + ".lock"
    document = native._native_job_dictionary(label)
    if document is not None:
        # Custody admission never uses this test-only cleanup proof. The
        # exact fresh label and complete argv identify our disposable job;
        # SMJobCopyDictionary may omit WorkingDirectory on supported macOS.
        payload = platform.definition(binding)
        assert payload in (
            macos_agent_plist(binding, login_autostart=False),
            macos_agent_plist(binding, login_autostart=True),
        )
        assert isinstance(document, dict)
        expected: object = plistlib.loads(macos_agent_plist(binding, login_autostart=False))
        assert isinstance(expected, dict)
        values = cast(dict[object, object], document)
        definition = cast(dict[object, object], expected)
        for key in ("Label", "Program", "ProgramArguments"):
            assert native._equal_plist(values.get(key), definition[key])
        if "WorkingDirectory" in values:
            assert native._equal_plist(values["WorkingDirectory"], definition["WorkingDirectory"])
        await platform.control(("bootout", f"gui/{binding.os_owner_id}/{label}"), timeout=25)
    await _wait_unregistered(binding)
    _remove_exact_definition(directory, name, binding)
    try:
        lock = os.stat(lock_name, dir_fd=directory, follow_symlinks=False)
    except FileNotFoundError:
        pass
    else:
        assert stat.S_ISREG(lock.st_mode) and lock.st_uid == posix_owner_uid()
        assert lock.st_nlink == 1 and not lock.st_mode & 0o077 and lock.st_size == 0
        os.unlink(lock_name, dir_fd=directory)
        os.fsync(directory)
    assert platform.definition(binding) is None


@asynccontextmanager
async def _owned_agent(
    root: Path,
) -> AsyncIterator[tuple[MacosUserManager, native._NativeMacosLaunchd, RuntimeServiceBinding]]:
    _select()
    root = root.resolve(strict=True)
    root.chmod(0o700)
    assert root.stat().st_uid == posix_owner_uid()
    executable = root / "synthetic-runtime"
    interpreter = Path(sys.executable)
    assert interpreter.is_absolute() and not any(character.isspace() for character in str(interpreter))
    source = f"#!{interpreter}\nimport time\nwhile True:\n    time.sleep(1)\n".encode()
    descriptor = os.open(executable, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC, 0o700)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(source)
        stream.flush()
        os.fsync(stream.fileno())
    binding = RuntimeServiceBinding(
        executable=str(executable),
        storage_root=str(root),
        storage_identity=posix_storage_identity(root),
        os_owner_id=str(posix_owner_uid()),
        product_version="synthetic-native-manager",
    )
    # Use the native implementation without injecting metadata or control.
    platform = native._NativeMacosLaunchd(binding)
    manager = MacosUserManager(binding, native=platform)
    directory, _path = native._native_definition_directory(create=True)
    label = runtime_service_name(binding)
    name = label + ".plist"
    lock_name = name + ".lock"
    try:
        for candidate in (name, lock_name):
            with pytest.raises(FileNotFoundError):
                os.stat(candidate, dir_fd=directory, follow_symlinks=False)
        assert native._native_job_dictionary(label) is None
        before = await manager.inspect()
        assert before.kind is RuntimeManagerKind.MACOS_AGENT and before.available
        assert not before.provisioned and not before.binding_matches
        try:
            yield manager, platform, binding
        finally:
            primary_error = sys.exception()
            try:
                await await_cancellation_complete(
                    _cleanup_owned_agent(platform, directory, binding), task_name="native-macos-agent-cleanup"
                )
            except asyncio.CancelledError:
                raise
            except BaseException as cleanup_error:
                if primary_error is None:
                    raise
                primary_error.add_note("Owned native LaunchAgent cleanup failed: " + type(cleanup_error).__name__)
    finally:
        os.close(directory)


@pytest.mark.asyncio
async def test_native_launchagent_explicit_configuration_start_stop_and_policy_preservation(tmp_path: Path) -> None:
    async with _owned_agent(tmp_path) as (manager, platform, binding):
        configured = await manager.configure(login_autostart=False)
        assert configured.available and configured.provisioned and configured.binding_matches
        assert not configured.login_autostart and configured.process_state is RuntimeManagerProcessState.STOPPED
        disabled = platform.definition(binding)
        assert disabled is not None
        await manager.start()
        pid = await _wait_running(manager, platform, binding)
        assert pid != os.getpid()
        watch = MacosProcessWatch(read_macos_process(pid, expected_owner=str(posix_owner_uid())))
        try:
            assert not watch.exited
            assert not (await manager.inspect()).login_autostart
            await manager.start()
            assert await _wait_running(manager, platform, binding) == pid
            assert platform.definition(binding) == disabled
            await manager.stop()
            assert watch.exited
            await _wait_unregistered(binding)
        finally:
            watch.close()
        stopped = await manager.inspect()
        assert stopped.provisioned and not stopped.login_autostart
        assert stopped.process_state is RuntimeManagerProcessState.STOPPED
        enabled = await manager.configure(login_autostart=True)
        assert enabled.login_autostart and enabled.binding_matches
        enabled_pid = await _wait_running(manager, platform, binding)
        enabled_watch = MacosProcessWatch(read_macos_process(enabled_pid, expected_owner=str(posix_owner_uid())))
        try:
            await manager.stop()
            assert enabled_watch.exited
            await _wait_unregistered(binding)
        finally:
            enabled_watch.close()
        assert (await manager.inspect()).login_autostart
        final = await manager.configure(login_autostart=False)
        assert final.binding_matches and not final.login_autostart
        assert final.process_state is RuntimeManagerProcessState.STOPPED
        assert platform.definition(binding) == disabled
