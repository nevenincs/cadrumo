"""Isolated real user-systemd stop semantics for one synthetic runtime unit."""

from __future__ import annotations

import asyncio
import os
import stat
import sys
import tempfile
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

from cadrumo.application.runtime.management import RuntimeServiceBinding

from ..linux_manager import LinuxUserManager
from ..manager_commands import NativeManagerCommand, run_manager_command
from ..posix import posix_storage_identity
from ..service_definitions import linux_user_service, runtime_service_name

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_outbound_adapter,
    pytest.mark.serial,
    pytest.mark.skipif(sys.platform != "linux", reason="requires native Linux user systemd and procfs"),
]


def _binding(root: Path) -> RuntimeServiceBinding:
    if sys.platform != "linux":
        pytest.skip("requires native Linux user systemd and procfs")
    return RuntimeServiceBinding(
        executable=str(root / "synthetic-runtime"),
        storage_root=str(root),
        storage_identity=posix_storage_identity(root),
        os_owner_id=str(os.getuid()),
        product_version="synthetic-cohort",
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
    pairs = (line.partition("=") for line in raw.splitlines())
    values = {key: value for key, separator, value in pairs if separator}
    if set(values) != {"ActiveState", "SubState", "UnitFileState", "NRestarts", "MainPID"}:
        raise RuntimeError("isolated user-systemd inspection was incomplete")
    return values


async def _wait_file(path: Path, *, timeout: float = 8) -> None:
    deadline = time.monotonic() + timeout
    while not path.is_file():
        if time.monotonic() >= deadline:
            raise AssertionError(f"synthetic process did not publish {path.name}")
        await asyncio.sleep(0.02)


def _process_instance(pid: int) -> tuple[str, str] | None:
    """Keep a procfs start tick so PID reuse cannot impersonate the child."""
    try:
        record = (Path("/proc") / str(pid) / "stat").read_text(encoding="ascii")
    except FileNotFoundError:
        return None
    fields = record.rpartition(") ")[2].split()
    if len(fields) < 20:
        raise RuntimeError("synthetic child process observation is incomplete")
    return fields[0], fields[19]


async def _wait_child_gone(pid: int, start_tick: str, *, timeout: float = 5) -> None:
    deadline = time.monotonic() + timeout
    while True:
        observed = _process_instance(pid)
        if observed is None or observed[1] != start_tick or observed[0] in {"Z", "X"}:
            return
        if time.monotonic() >= deadline:
            raise AssertionError("synthetic child remained live after unit stop")
        await asyncio.sleep(0.02)


async def _wait_stopped(name: str, *, timeout: float = 27) -> dict[str, str]:
    deadline = time.monotonic() + timeout
    while True:
        values = await _properties(name)
        if values["ActiveState"] in {"inactive", "failed"} and values["SubState"] != "auto-restart":
            return values
        if time.monotonic() >= deadline:
            raise AssertionError("isolated user unit did not stop within its 25-second bound")
        await asyncio.sleep(0.05)


@asynccontextmanager
async def _installed_unit(root: Path, *, mode: str) -> AsyncIterator[tuple[LinuxUserManager, str]]:
    if sys.platform != "linux":
        pytest.skip("requires native Linux user systemd and procfs")
    if not root.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()) or root.stat().st_uid != os.getuid():
        raise RuntimeError("synthetic unit root must be an owner-controlled /tmp directory")
    if not Path("/usr/bin/systemctl").is_file() or not Path("/proc/self/stat").is_file():
        pytest.skip("native user-systemd or procfs unavailable")
    binding = _binding(root)
    manager = LinuxUserManager(binding)
    inspection = await manager.inspect()
    if not inspection.available:
        pytest.skip("native user systemd unavailable")
    if inspection.provisioned:
        raise RuntimeError("unique synthetic unit name was already provisioned")
    name = runtime_service_name(binding) + ".service"
    unit_path = _unit_directory() / name
    if os.path.lexists(unit_path):
        raise RuntimeError("synthetic unit path already exists")

    source = Path(__file__).with_name("linux_manager_stop_fixture.py")
    executable = root / "synthetic-runtime"
    descriptor = os.open(executable, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC, 0o700)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(source.read_bytes())
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        executable.unlink(missing_ok=True)
        raise
    executable.chmod(0o700)
    (root / "mode").write_text(mode, encoding="ascii")

    definition = linux_user_service(binding)
    unit_descriptor = os.open(unit_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(unit_descriptor, "wb") as stream:
            stream.write(definition.encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        unit_path.unlink(missing_ok=True)
        raise
    published = unit_path.stat()
    try:
        await _systemctl("daemon-reload")
        current = await manager.inspect()
        assert current.available and current.provisioned and current.binding_matches
        assert not current.login_autostart
        assert (await _properties(name))["UnitFileState"] == "disabled"
        yield manager, name
    finally:
        (root / "release").touch(exist_ok=True)
        current = await manager.inspect()
        if not current.available:
            raise RuntimeError("user systemd unavailable during synthetic unit cleanup")
        if current.provisioned:
            if not current.binding_matches:
                raise RuntimeError("synthetic unit binding changed before cleanup")
            await manager.stop()
            await _wait_stopped(name)
        present = unit_path.lstat()
        if (
            not stat.S_ISREG(present.st_mode)
            or (present.st_dev, present.st_ino) != (published.st_dev, published.st_ino)
            or unit_path.read_text(encoding="utf-8") != definition
        ):
            raise RuntimeError("synthetic unit path changed before cleanup")
        unit_path.unlink()
        await _systemctl("daemon-reload")
        assert not (await manager.inspect()).provisioned


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["graceful", "crash"])
async def test_manager_stop_survives_helper_exit_and_suppresses_restart(tmp_path: Path, mode: str) -> None:
    async with _installed_unit(tmp_path, mode=mode) as (manager, name):
        await manager.start()
        await _wait_file(tmp_path / "boot")
        main_pid, child_pid = (int(value) for value in (tmp_path / "boot").read_text(encoding="ascii").split())
        assert main_pid > 0 and child_pid > 0
        child = _process_instance(child_pid)
        assert child is not None and child[0] not in {"Z", "X"}
        helper = await asyncio.create_subprocess_exec(
            sys.executable,
            str(Path(__file__).with_name("linux_manager_stop_fixture.py")),
            "queue-stop",
            str(tmp_path),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        output, error = await asyncio.wait_for(helper.communicate(), timeout=8)
        assert helper.returncode == 0, (helper.returncode, output, error)
        await _wait_file(tmp_path / "term")
        assert _process_instance(child_pid) == child
        assert not (tmp_path / "child-term").exists()
        (tmp_path / "release").touch()
        stopped = await _wait_stopped(name)
        assert stopped["UnitFileState"] == "disabled"
        assert stopped["NRestarts"] == "0"
        assert (tmp_path / "boot-count").read_text(encoding="ascii") == "1"
        assert (tmp_path / "main-only-term").read_text(encoding="ascii") == "True"
        if mode == "graceful":
            assert (tmp_path / "settled").read_text(encoding="ascii") == "yes"
        else:
            assert not (tmp_path / "settled").exists()
        await _wait_child_gone(child_pid, child[1])
        assert not (await manager.inspect()).login_autostart
