"""A verified owner stop queues systemd before the real runtime drains."""

from __future__ import annotations

import asyncio
import os
import shlex
import stat
import sys
import tempfile
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

import pytest

from cadrumo.application.runtime.contracts import RuntimeClientHello, RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.management import RuntimeServiceBinding
from cadrumo.application.runtime.owner_control import (
    RuntimeStopAccepted,
    RuntimeStopConfirm,
    RuntimeStopPreview,
    RuntimeStopPreviewRequest,
)

from ..framing import VerifiedRuntimeConnection
from ..linux_manager import LinuxUserManager
from ..manager_commands import NativeManagerCommand, run_manager_command
from ..posix import PosixRuntimeEndpoint, posix_storage_identity
from ..service_definitions import linux_user_service, runtime_service_name

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_outbound_adapter,
    pytest.mark.serial,
    pytest.mark.skipif(sys.platform != "linux", reason="requires native Linux user systemd and procfs"),
]

_VERSION = "synthetic-cohort"
_TEST_MODULE = Path(__file__).resolve(strict=True)
_SOURCE_ROOT = _TEST_MODULE.parents[4]
# Preserve the current virtualenv launcher path; resolving its symlink would
# select the system interpreter instead of this test's dependency environment.
_VENV_PYTHON = Path(sys.executable)


def _binding(root: Path) -> RuntimeServiceBinding:
    if sys.platform != "linux":
        pytest.skip("requires native Linux user systemd and procfs")
    return RuntimeServiceBinding(
        executable=str(root / "synthetic-runtime"),
        storage_root=str(root),
        storage_identity=posix_storage_identity(root),
        os_owner_id=str(os.getuid()),
        product_version=_VERSION,
    )


def _unit_directory() -> Path:
    if sys.platform != "linux":
        pytest.skip("requires native Linux user systemd and procfs")
    home = Path.home()
    directory = home / ".config" / "systemd" / "user"
    for part in (home, home / ".config", home / ".config" / "systemd", directory):
        metadata = part.lstat()
        if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.getuid() or metadata.st_mode & 0o022:
            raise RuntimeError("user unit directory is not an exact owner-controlled directory")
    if directory.resolve(strict=True) != directory:
        raise RuntimeError("user unit directory has an alias")
    return directory


async def _systemctl(*arguments: str) -> str:
    response = await run_manager_command(
        NativeManagerCommand.SYSTEMCTL,
        ("--user", "--no-pager", "--no-ask-password", *arguments),
    )
    if response.returncode != 0:
        raise RuntimeError("isolated user-systemd operation refused")
    return response.output


async def _properties(name: str) -> dict[str, str]:
    raw = await _systemctl("show", name, "--property=ActiveState,SubState,UnitFileState,NRestarts,MainPID")
    values = {key: value for line in raw.splitlines() for key, separator, value in (line.partition("="),) if separator}
    if set(values) != {"ActiveState", "SubState", "UnitFileState", "NRestarts", "MainPID"}:
        raise RuntimeError("isolated user-systemd inspection was incomplete")
    return values


async def _wait_file(path: Path, *, timeout: float = 8) -> None:
    deadline = time.monotonic() + timeout
    while not path.is_file():
        if time.monotonic() >= deadline:
            raise AssertionError(f"synthetic runtime did not publish {path.name}")
        await asyncio.sleep(0.02)


async def _wait_stopped(name: str, *, timeout: float = 27) -> dict[str, str]:
    deadline = time.monotonic() + timeout
    while True:
        current = await _properties(name)
        if current["ActiveState"] in {"inactive", "failed"} and current["SubState"] != "auto-restart":
            return current
        if time.monotonic() >= deadline:
            raise AssertionError("isolated runtime unit did not stop within its bound")
        await asyncio.sleep(0.05)


def _fixture_source() -> Path:
    source = _TEST_MODULE.with_name("linux_managed_runtime_fixture.py")
    if (
        _TEST_MODULE.relative_to(_SOURCE_ROOT)
        != Path("cadrumo/adapters/local_runtime/tests/test_linux_managed_runtime_stop_native.py")
        or source.relative_to(_SOURCE_ROOT)
        != Path("cadrumo/adapters/local_runtime/tests/linux_managed_runtime_fixture.py")
        or source.resolve(strict=True) != source
    ):
        raise RuntimeError("synthetic installed launcher source is not this trusted checkout")
    if not _VENV_PYTHON.is_absolute() or not _VENV_PYTHON.is_file() or not os.access(_VENV_PYTHON, os.X_OK):
        pytest.skip("current Linux test interpreter is unavailable")
    return source


def _launcher(source: Path) -> str:
    return f'#!/bin/sh\nexec {shlex.quote(str(_VENV_PYTHON))} -I {shlex.quote(str(source))} "$@"\n'


@asynccontextmanager
async def _installed_runtime(root: Path) -> AsyncIterator[tuple[LinuxUserManager, str, RuntimeServiceBinding, Path]]:
    if sys.platform != "linux":
        pytest.skip("requires native Linux user systemd and procfs")
    if not root.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()) or root.stat().st_uid != os.getuid():
        raise RuntimeError("synthetic runtime root must be an owner-controlled /tmp directory")
    if not Path("/usr/bin/systemctl").is_file() or not Path("/proc/self/stat").is_file():
        pytest.skip("native user-systemd or procfs unavailable")
    source = _fixture_source()
    binding = _binding(root)
    manager = LinuxUserManager(binding)
    inspection = await manager.inspect()
    if not inspection.available:
        pytest.skip("native user systemd unavailable")
    if inspection.provisioned:
        raise RuntimeError("unique synthetic runtime unit was already provisioned")
    name = runtime_service_name(binding) + ".service"
    unit_path = _unit_directory() / name
    if os.path.lexists(unit_path):
        raise RuntimeError("synthetic runtime unit path already exists")

    executable = root / "synthetic-runtime"
    launcher = _launcher(source)
    descriptor = os.open(executable, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW, 0o700)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(launcher.encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        executable.unlink(missing_ok=True)
        raise
    executable.chmod(0o700)
    launched = executable.stat()

    definition = linux_user_service(binding)
    unit_descriptor = os.open(unit_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(unit_descriptor, "wb") as stream:
            stream.write(definition.encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        executable.unlink(missing_ok=True)
        unit_path.unlink(missing_ok=True)
        raise
    published = unit_path.stat()
    try:
        await _systemctl("daemon-reload")
        current = await manager.inspect()
        assert current.available and current.provisioned and current.binding_matches
        assert not current.login_autostart
        assert (await _properties(name))["UnitFileState"] == "disabled"
        yield manager, name, binding, source
    finally:
        current = await manager.inspect()
        if not current.available:
            raise RuntimeError("user systemd unavailable during synthetic runtime cleanup")
        if current.provisioned:
            if not current.binding_matches:
                raise RuntimeError("synthetic runtime unit binding changed before cleanup")
            await manager.stop()
            await _wait_stopped(name)
        unit_present = unit_path.lstat()
        launched_present = executable.lstat()
        if (
            not stat.S_ISREG(unit_present.st_mode)
            or (unit_present.st_dev, unit_present.st_ino) != (published.st_dev, published.st_ino)
            or unit_path.read_text(encoding="utf-8") != definition
            or not stat.S_ISREG(launched_present.st_mode)
            or (launched_present.st_dev, launched_present.st_ino) != (launched.st_dev, launched.st_ino)
            or executable.read_text(encoding="utf-8") != launcher
        ):
            raise RuntimeError("synthetic runtime provisioning changed before cleanup")
        unit_path.unlink()
        executable.unlink()
        await _systemctl("daemon-reload")
        assert not (await manager.inspect()).provisioned


async def _connect(root: Path) -> VerifiedRuntimeConnection:
    deadline = time.monotonic() + 5
    while True:
        endpoint = PosixRuntimeEndpoint(storage_root=root, create_namespace=False)
        try:
            return VerifiedRuntimeConnection(
                endpoint.connect(timeout=1),
                expected=RuntimeClientHello(product_version=_VERSION, storage_identity=endpoint.storage_identity),
                deadline=deadline,
            )
        except RuntimeRefusalError as error:
            if error.reason is not RuntimeRefusalCode.ENDPOINT_NOT_READY or time.monotonic() >= deadline:
                raise
            await asyncio.sleep(0.02)
        finally:
            endpoint.close()


@pytest.mark.asyncio
async def test_native_owner_confirm_queues_manager_stop_before_runtime_drain(tmp_path: Path) -> None:
    async with _installed_runtime(tmp_path) as (manager, name, _binding, source):
        await manager.start()
        await _wait_file(tmp_path / "boot")
        main_pid = int((tmp_path / "boot").read_text(encoding="ascii"))
        assert main_pid != os.getpid()
        before = await _properties(name)
        assert before["ActiveState"] == "active" and int(before["MainPID"]) == main_pid
        assert before["UnitFileState"] == "disabled"

        foreign = await asyncio.create_subprocess_exec(
            str(_VENV_PYTHON),
            "-I",
            str(source),
            "foreign-stop",
            str(tmp_path),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        output, error = await asyncio.wait_for(foreign.communicate(), timeout=8)
        assert foreign.returncode == 0, (foreign.returncode, output, error)
        unchanged = await _properties(name)
        assert unchanged["ActiveState"] == "active" and int(unchanged["MainPID"]) == main_pid
        assert unchanged["UnitFileState"] == "disabled"
        assert not (tmp_path / "term").exists()

        client = await _connect(tmp_path)
        try:
            preview = await asyncio.to_thread(
                client.owner_control, RuntimeStopPreviewRequest(request_id=uuid4()), deadline=time.monotonic() + 5
            )
            assert isinstance(preview, RuntimeStopPreview), preview
            assert preview.scope == "all_profiles_and_work"
            accepted = await asyncio.to_thread(
                client.owner_control,
                RuntimeStopConfirm(
                    request_id=uuid4(),
                    runtime_boot_id=preview.runtime_boot_id,
                    preview_id=preview.preview_id,
                    acknowledge_all_profiles_and_work=True,
                ),
                deadline=time.monotonic() + 8,
            )
            assert isinstance(accepted, RuntimeStopAccepted), accepted
            assert accepted.runtime_boot_id == preview.runtime_boot_id
            assert accepted.connection_id == preview.connection_id
            assert accepted.scope == "all_profiles_and_work"
        finally:
            client.close()

        await _wait_file(tmp_path / "term")
        await _wait_file(tmp_path / "settled")
        stopped = await _wait_stopped(name)
        assert stopped["UnitFileState"] == "disabled"
        assert stopped["NRestarts"] == "0"
        assert (tmp_path / "boot-count").read_text(encoding="ascii") == "1"
        assert (tmp_path / "settled").read_text(encoding="ascii") == "yes"
        await asyncio.sleep(1)
        still_stopped = await _properties(name)
        assert still_stopped["ActiveState"] in {"inactive", "failed"}
        assert still_stopped["UnitFileState"] == "disabled"
        assert still_stopped["NRestarts"] == "0"
        assert (tmp_path / "boot-count").read_text(encoding="ascii") == "1"
        assert not (await manager.inspect()).login_autostart
