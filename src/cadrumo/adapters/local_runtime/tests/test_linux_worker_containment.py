"""Native parent and guardian death kill an independent worker process group."""

from __future__ import annotations

import asyncio
import ctypes
import json
import math
import os
import select
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest

from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.core.async_cleanup import close_async_resources

from .. import linux_worker_process
from ..linux_pidfd import open_linux_pidfd
from ..linux_worker_process import (
    LinuxProcessScope,
    _cgroup_empty,
    _cgroup_for,
    _unit_absent,
    _unit_properties,
    linux_process_start_identity,
)
from ..manager_commands import NativeManagerCommand, run_manager_command_sync

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_outbound_adapter,
    pytest.mark.skipif(sys.platform != "linux", reason="requires native Linux user-systemd cgroup containment"),
    pytest.mark.usefixtures("authority_operation"),
]


def test_unknown_linux_containment_refuses_before_private_worker_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unavailable(_tool: NativeManagerCommand, _arguments: tuple[str, ...]) -> None:
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)

    monkeypatch.setattr(linux_worker_process, "run_manager_command_sync", unavailable)
    scope = LinuxProcessScope(worker_id=uuid4())
    with pytest.raises(RuntimeRefusalError) as refused:
        scope.launch(
            executable=Path(sys.executable),
            arguments=("-I", "-m", "cadrumo.entrypoints.runtime.worker"),
            directory=tmp_path,
            environment={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C", "PYDANTIC_DISABLE_PLUGINS": "__all__"},
        )
    assert refused.value.reason is RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE
    assert scope._guardian is None and scope._worker_pid == 0


def _dead(pidfd: int) -> bool:
    if sys.platform != "linux":
        pytest.skip("requires native Linux PIDFD capability")
    poller = select.poll()
    poller.register(pidfd, select.POLLIN | select.POLLERR | select.POLLHUP)
    return bool(poller.poll(0))


@dataclass
class _ContainmentCleanup:
    """Retain this fixture's exact native resources until each release succeeds."""

    parent: subprocess.Popen[bytes]
    directory: Path
    worker_fd: int = -1
    guardian_fd: int = -1
    descendant_fds: list[int] = field(default_factory=list)
    unit: str | None = None
    cgroup: str | None = None
    parent_reaped: bool = False
    unit_retired: bool = False

    def record_scope(self, facts: dict[str, Any]) -> None:
        """Accept only the disposable parent's exact published scope identity."""
        unit, cgroup = facts.get("unit"), facts.get("cgroup")
        if (
            facts.get("runtime_pid") != self.parent.pid
            or not isinstance(unit, str)
            or not unit.startswith("cadrumo-worker-")
            or not unit.endswith(".service")
            or len(unit) != len("cadrumo-worker-") + 32 + len(".service")
            or any(character not in "0123456789abcdef" for character in unit[15:-8])
            or not isinstance(cgroup, str)
            or (cgroup and not cgroup.startswith("/"))
            or ".." in Path(cgroup).parts
            or (cgroup and not cgroup.endswith("/" + unit))
            or (self.unit is not None and (self.unit, self.cgroup) != (unit, cgroup))
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        self.unit, self.cgroup = unit, cgroup

    def _discover_scope(self) -> None:
        if self.unit is not None:
            return
        acquired = self.directory / "linux-worker-acquired.json"
        if acquired.exists():
            encoded = acquired.read_bytes()
            if len(encoded) > 4096:
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            facts = json.loads(encoded)
            if not isinstance(facts, dict):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            self.record_scope(facts)

    def _retire_unit(self) -> None:
        if self.unit is None or self.unit_retired:
            return
        assert self.cgroup is not None
        failure: BaseException | None = None
        try:
            stopped = run_manager_command_sync(
                NativeManagerCommand.SYSTEMCTL,
                ("--user", "--no-pager", "--no-ask-password", "stop", self.unit),
            )
            if stopped.returncode != 0:
                failure = RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        except BaseException as error:
            failure = error
        # Prove physical retirement even after the manager control call fails.
        deadline = time.monotonic() + 10
        try:
            if self.cgroup:
                while not _cgroup_empty(self.cgroup):
                    if time.monotonic() >= deadline:
                        raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
                    time.sleep(0.05)
            # An unknown cgroup from partial construction needs exact native absence.
            if (failure is not None or not self.cgroup) and not _unit_absent(self.unit):
                raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        except BaseException as observation_error:
            if failure is not None:
                raise BaseExceptionGroup("Linux fixture unit retirement failed", [failure, observation_error]) from None
            raise
        self.unit_retired = True

    def _release(self) -> None:
        failures: list[BaseException] = []
        if not self.parent_reaped:
            try:
                if self.parent.poll() is None:
                    self.parent.kill()
            except ProcessLookupError:
                pass
            except BaseException as error:
                failures.append(error)
            try:
                self.parent.wait(timeout=5)
                self.parent_reaped = True
            except BaseException as error:
                failures.append(error)
        # Reaping fences publication; recover metadata even after setup failed.
        try:
            self._discover_scope()
        except BaseException as error:
            failures.append(error)
        try:
            self._retire_unit()
        except BaseException as error:
            failures.append(error)
        for field_name in ("worker_fd", "guardian_fd"):
            descriptor = getattr(self, field_name)
            if descriptor >= 0:
                try:
                    os.close(descriptor)
                except BaseException as error:
                    failures.append(error)
                else:
                    setattr(self, field_name, -1)
        for descriptor in tuple(self.descendant_fds):
            try:
                os.close(descriptor)
            except BaseException as error:
                failures.append(error)
            else:
                self.descendant_fds.remove(descriptor)
        if failures:
            raise BaseExceptionGroup("Linux containment fixture cleanup failed", failures)

    async def close(self) -> None:
        """Settle all release attempts under canonical cancellation ownership."""
        await asyncio.to_thread(self._release)


def _assert_marker_absent(pid: int, *, device: int, inode: int) -> None:
    """Check native descriptor identity, allowing only descriptors closed mid-scan."""
    descriptors = tuple((Path("/proc") / str(pid) / "fd").iterdir())
    assert len(descriptors) <= 4096
    for descriptor in descriptors:
        try:
            metadata = descriptor.stat()
        except FileNotFoundError:
            continue
        assert (metadata.st_dev, metadata.st_ino) != (device, inode)


def _assert_browser_not_failed(directory: Path) -> None:
    """Enter exact-scope cleanup promptly on the child's safe failure witness."""
    failure = directory / "linux-worker-browser-failure.json"
    if failure.exists():
        encoded = failure.read_bytes()
        assert len(encoded) <= 4096
        document = json.loads(encoded)
        assert isinstance(document, dict) and set(document) == {"code"}
        code = document["code"]
        assert isinstance(code, str) and 0 < len(code) <= 128
        assert all(character.isascii() and (character.isalnum() or character == "_") for character in code)
        raise AssertionError("contained post-admission browser failed: " + code)


def _launch_parent(tmp_path: Path, *, mode: str | None = None) -> subprocess.Popen[bytes]:
    # The expendable parent is a development test module, excluded from the
    # installed wheel. Only this fixture interpreter gets the declared src path;
    # the production guardian and worker still launch with isolated Python.
    source_root = Path(__file__).resolve().parents[4]
    return subprocess.Popen(  # noqa: S603 - fixed expendable development test module
        (
            sys.executable,
            "-m",
            "cadrumo.entrypoints.runtime.tests.linux_worker_parent_fixture",
            str(tmp_path),
            *((mode,) if mode is not None else ()),
        ),
        cwd=tmp_path,
        env={
            "PATH": "/usr/bin:/bin",
            "LANG": "C",
            "LC_ALL": "C",
            "PYDANTIC_DISABLE_PLUGINS": "__all__",
            "PYTHONPATH": str(source_root),
            "CADRUMO_AUTHORITY_ROOT": os.environ["CADRUMO_AUTHORITY_ROOT"],
            "CADRUMO_LOCAL_STORAGE_ROOT": str(tmp_path / "cadrumo-storage"),
        },
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        start_new_session=True,
    )


@pytest.mark.parametrize(
    ("failed_owner", "resistant_descendants", "browser_descendants"),
    [
        pytest.param("runtime_parent", False, False, id="runtime_parent"),
        pytest.param("guardian", False, False, id="guardian"),
        pytest.param("runtime_parent", True, False, id="runtime_parent-resistant"),
        pytest.param("guardian", True, False, id="guardian-resistant"),
        pytest.param("runtime_parent", False, True, id="runtime_parent-browser"),
        pytest.param("guardian", False, True, id="guardian-browser"),
        pytest.param("worker", False, True, id="worker-browser"),
    ],
)
def test_linux_worker_service_kills_independent_group_on_owner_loss(
    tmp_path: Path, failed_owner: str, resistant_descendants: bool, browser_descendants: bool
) -> None:
    if sys.platform != "linux":
        pytest.skip("requires native Linux user-systemd cgroup containment")
    mode = "resistant-descendants" if resistant_descendants else "browser-descendants" if browser_descendants else None
    parent = _launch_parent(tmp_path, mode=mode)
    cleanup = _ContainmentCleanup(parent, tmp_path)
    primary: BaseException | None = None
    try:
        ready = tmp_path / "linux-worker-ready.json"
        failure = tmp_path / "linux-worker-failure.json"
        deadline = time.monotonic() + 90
        while not ready.exists():
            if browser_descendants:
                _assert_browser_not_failed(tmp_path)
            assert parent.poll() is None, "the real Linux profile owner exited before admission: " + (
                failure.read_text(encoding="ascii") if failure.exists() else "no safe diagnostic"
            )
            assert time.monotonic() < deadline, "the contained worker did not become ready"
            time.sleep(0.05)
        if browser_descendants:
            _assert_browser_not_failed(tmp_path)
        facts = cast(dict[str, Any], json.loads(ready.read_text(encoding="ascii")))
        acquired = json.loads((tmp_path / "linux-worker-acquired.json").read_text(encoding="ascii"))
        assert all(facts[name] == value for name, value in acquired.items())
        cleanup.record_scope(facts)
        worker_pid, guardian_pid = int(facts["worker_pid"]), int(facts["guardian_pid"])
        assert int(facts["runtime_pid"]) == parent.pid
        assert int(facts["worker_group"]) == worker_pid
        assert int(facts["guardian_group"]) != int(facts["worker_group"])
        cleanup.worker_fd = open_linux_pidfd(worker_pid)
        cleanup.guardian_fd = open_linux_pidfd(guardian_pid)
        worker_fd, guardian_fd = cleanup.worker_fd, cleanup.guardian_fd
        assert not _dead(worker_fd) and not _dead(guardian_fd)
        if resistant_descendants:
            records = json.loads((tmp_path / "linux-worker-descendants.json").read_text(encoding="ascii"))
            assert isinstance(records, list) and len(records) == 2
            assert {record["role"] for record in records} == {"child", "grandchild"}
            descendants = {record["role"]: record for record in records}
            assert descendants["child"]["parent_pid"] == worker_pid
            assert descendants["grandchild"]["parent_pid"] == descendants["child"]["pid"]
            assert len({record["pid"] for record in records}) == 2
            for record in records:
                pid = record["pid"]
                assert type(pid) is int and pid > 0 and pid not in {parent.pid, worker_pid, guardian_pid}
                descriptor = open_linux_pidfd(pid)
                cleanup.descendant_fds.append(descriptor)
                assert not _dead(descriptor)
                assert linux_process_start_identity(pid) == record["start_identity"]
                assert _cgroup_for(pid) == facts["cgroup"]
                assert os.getsid(pid) == pid and os.getpgid(pid) == pid
                assert pid != int(facts["worker_group"])
                status = (Path("/proc") / str(pid) / "status").read_text(encoding="ascii")
                ignored = next(line.split()[1] for line in status.splitlines() if line.startswith("SigIgn:"))
                assert int(ignored, 16) & (1 << (signal.SIGTERM - 1))
                assert linux_process_start_identity(pid) == record["start_identity"]
                assert not _dead(descriptor)
        if browser_descendants:
            browser_ready = tmp_path / "linux-worker-browser.json"
            deadline = time.monotonic() + 30
            while not browser_ready.exists():
                _assert_browser_not_failed(tmp_path)
                assert parent.poll() is None and not _dead(worker_fd) and not _dead(guardian_fd)
                assert time.monotonic() < deadline, "admitted worker did not launch its real local browser"
                time.sleep(0.05)
            _assert_browser_not_failed(tmp_path)
            browser = json.loads(browser_ready.read_text(encoding="ascii"))
            assert browser["title"] == "synthetic containment"
            assert browser["worker_pid"] == worker_pid
            assert browser["worker_start_identity"] == linux_process_start_identity(worker_pid)
            executable = Path(browser["executable"]).resolve(strict=True)
            assert executable.is_file()
            marker = json.loads((tmp_path / "linux-parent-marker.json").read_text(encoding="ascii"))
            device, inode = marker["device"], marker["inode"]
            assert type(device) is int and type(inode) is int and inode > 0
            parent_marker = (Path("/proc") / str(parent.pid) / "fd" / str(marker["fd"])).stat()
            assert (parent_marker.st_dev, parent_marker.st_ino) == (device, inode)
            parent_flags = (Path("/proc") / str(parent.pid) / "fdinfo" / str(marker["fd"])).read_text(encoding="ascii")
            flags = next(row.split()[1] for row in parent_flags.splitlines() if row.startswith("flags:"))
            assert not int(flags, 8) & os.O_CLOEXEC
            for pid in (worker_pid, guardian_pid):
                _assert_marker_absent(pid, device=device, inode=inode)
            worker_marker = json.loads((tmp_path / "linux-worker-marker.json").read_text(encoding="ascii"))
            assert isinstance(worker_marker, dict) and set(worker_marker) == {"pid", "fd", "device", "inode"}
            assert type(worker_marker["pid"]) is int and worker_marker["pid"] == worker_pid
            worker_device, worker_inode = worker_marker["device"], worker_marker["inode"]
            worker_marker_fd = worker_marker["fd"]
            assert type(worker_device) is int and type(worker_inode) is int and worker_inode > 0
            assert type(worker_marker_fd) is int and worker_marker_fd >= 0
            assert (worker_device, worker_inode) != (device, inode)
            native_marker = (Path("/proc") / str(worker_pid) / "fd" / str(worker_marker_fd)).stat()
            assert (native_marker.st_dev, native_marker.st_ino) == (worker_device, worker_inode)
            native_marker_flags = (Path("/proc") / str(worker_pid) / "fdinfo" / str(worker_marker_fd)).read_text(
                encoding="ascii"
            )
            worker_flags = next(row.split()[1] for row in native_marker_flags.splitlines() if row.startswith("flags:"))
            assert not int(worker_flags, 8) & os.O_CLOEXEC
            _assert_marker_absent(guardian_pid, device=worker_device, inode=worker_inode)
            group = Path("/sys/fs/cgroup") / str(facts["cgroup"]).lstrip("/")
            membership_files = tuple(group.rglob("cgroup.procs"))
            assert 1 <= len(membership_files) <= 64
            members = {
                int(pid)
                for membership in membership_files
                for pid in membership.read_text(encoding="ascii").splitlines()
            }
            assert 4 <= len(members) <= 4096
            browser_roles: set[str] = set()
            for pid in members - {worker_pid, guardian_pid}:
                native = Path("/proc") / str(pid)
                started = linux_process_start_identity(pid)
                descriptor = open_linux_pidfd(pid)
                cleanup.descendant_fds.append(descriptor)
                assert not _dead(descriptor)
                assert _cgroup_for(pid) == facts["cgroup"]
                _assert_marker_absent(pid, device=device, inode=inode)
                _assert_marker_absent(pid, device=worker_device, inode=worker_inode)
                selected = (native / "exe").resolve(strict=True)
                # Chromium setproctitle flattens zygote-child argv into one
                # space-separated title. Match exact switches in either native
                # representation; role classification also requires exact exe.
                arguments = (native / "cmdline").read_bytes().replace(b"\0", b" ").split()
                assert linux_process_start_identity(pid) == started
                assert not _dead(descriptor)
                if selected != executable:
                    continue
                if b"--type=renderer" in arguments:
                    role = "renderer"
                elif b"--remote-debugging-pipe" in arguments and not any(
                    argument.startswith(b"--type=") for argument in arguments
                ):
                    role = "browser"
                else:
                    continue
                browser_roles.add(role)
            assert browser_roles == {"browser", "renderer"}
            assert len(cleanup.descendant_fds) >= 2
            assert browser["worker_start_identity"] == linux_process_start_identity(worker_pid)
            assert not _dead(worker_fd) and not _dead(guardian_fd)
        if failed_owner == "runtime_parent":
            os.kill(parent.pid, signal.SIGKILL)
        elif failed_owner == "guardian":
            killed = run_manager_command_sync(
                NativeManagerCommand.SYSTEMCTL,
                (
                    "--user",
                    "--no-pager",
                    "--no-ask-password",
                    "kill",
                    "--kill-whom=main",
                    "--signal=SIGKILL",
                    str(facts["unit"]),
                ),
            )
            assert killed.returncode == 0
        elif failed_owner == "worker":
            assert browser_descendants and parent.poll() is None
            assert all(not _dead(descriptor) for descriptor in cleanup.descendant_fds)
            if sys.platform == "linux":
                library = ctypes.CDLL(None, use_errno=True)
                native_signal = library.pidfd_send_signal
                native_signal.argtypes = (ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint)
                native_signal.restype = ctypes.c_int
                ctypes.set_errno(0)
                result = int(native_signal(worker_fd, signal.SIGKILL, None, 0))
                native_errno = ctypes.get_errno()
                assert result == 0, f"native PIDFD signal failed (errno={native_errno})"
            else:
                raise AssertionError("worker PIDFD signaling requires Linux")
        else:
            raise AssertionError("unknown failed containment owner")
        deadline = time.monotonic() + 10
        while not (
            _dead(worker_fd)
            and _dead(guardian_fd)
            and _cgroup_empty(str(facts["cgroup"]))
            and all(_dead(descriptor) for descriptor in cleanup.descendant_fds)
        ):
            assert time.monotonic() < deadline, "systemd retained the private worker cgroup after owner loss"
            time.sleep(0.05)
        assert all(_dead(descriptor) for descriptor in cleanup.descendant_fds)
        assert _cgroup_empty(str(facts["cgroup"]))
        if failed_owner == "worker":
            assert parent.poll() is None
    except BaseException as error:
        primary = error
        raise
    finally:
        asyncio.run(close_async_resources(cleanup, task_name="linux-containment-fixture-close", primary_error=primary))


def test_linux_worker_owner_loss_during_registration(tmp_path: Path) -> None:
    """Lose the owner after native registration, before launch receives its ACK."""
    if sys.platform != "linux":
        pytest.skip("requires native Linux user-systemd cgroup containment")
    parent = _launch_parent(tmp_path, mode="registration-loss")
    cleanup = _ContainmentCleanup(parent, tmp_path)
    primary: BaseException | None = None
    try:
        registered = tmp_path / "linux-worker-registered.json"
        deadline = time.monotonic() + 90
        while not registered.exists():
            assert parent.poll() is None, "runtime owner exited before real registration acknowledgment"
            assert time.monotonic() < deadline, "real systemd registration did not reach the barrier"
            time.sleep(0.05)
        assert parent.poll() is None
        record = json.loads(registered.read_text(encoding="ascii"))
        reservation = json.loads((tmp_path / "linux-worker-acquired.json").read_text(encoding="ascii"))
        assert set(record) == {"runtime_pid", "unit", "cgroup", "barrier_deadline"}
        assert {name: record[name] for name in reservation} == reservation
        barrier_deadline = record["barrier_deadline"]
        assert type(barrier_deadline) is float and math.isfinite(barrier_deadline)
        assert set(reservation) == {"runtime_pid", "unit", "cgroup"}
        assert reservation["runtime_pid"] == parent.pid and reservation["cgroup"] == ""
        assert not (tmp_path / "linux-worker-ready.json").exists()
        assert not (tmp_path / "linux-registration-release").exists()
        # Resolve the native cgroup once before committing scope ownership.
        # On failure, cleanup alone recovers the unknown reserved cgroup.
        unit = reservation["unit"]
        deadline = time.monotonic() + 10
        while True:
            properties = _unit_properties(unit)
            if properties["ActiveState"] == "active" and int(properties["MainPID"]) > 0:
                break
            assert parent.poll() is None
            assert time.monotonic() < deadline, "registered guardian did not become active"
            time.sleep(0.05)
        assert properties["KillMode"] == "control-group" and properties["ExitType"] == "main"
        assert properties["SendSIGKILL"] == "yes" and properties["TimeoutStopUSec"] == "1s"
        guardian_pid = int(properties["MainPID"])
        cgroup = properties["ControlGroup"]
        cleanup.record_scope({"runtime_pid": parent.pid, "unit": unit, "cgroup": cgroup})
        guardian_start = linux_process_start_identity(guardian_pid)
        cleanup.guardian_fd = open_linux_pidfd(guardian_pid)
        guardian_fd = cleanup.guardian_fd
        assert not _dead(guardian_fd) and _cgroup_for(guardian_pid) == cgroup
        guardian_native = Path("/proc") / str(guardian_pid)
        interpreter = Path(sys.executable).resolve(strict=True)
        assert (guardian_native / "exe").resolve(strict=True) == interpreter
        guardian_args = (guardian_native / "cmdline").read_bytes().split(b"\0")
        assert guardian_args[1:4] == [b"-I", b"-m", b"cadrumo.entrypoints.runtime.linux_worker_guardian"]
        assert guardian_args[guardian_args.index(b"--parent-pid") + 1] == str(parent.pid).encode("ascii")
        assert guardian_args[guardian_args.index(b"--parent-start") + 1] == linux_process_start_identity(
            parent.pid
        ).encode("ascii")
        assert linux_process_start_identity(guardian_pid) == guardian_start and not _dead(guardian_fd)
        deadline = time.monotonic() + 10
        while True:
            membership = (Path("/sys/fs/cgroup") / cgroup.lstrip("/") / "cgroup.procs").read_text(encoding="ascii")
            members = {int(pid) for pid in membership.splitlines()}
            assert 1 <= len(members) <= 4096
            workers: list[int] = []
            for pid in members - {guardian_pid}:
                arguments = (Path("/proc") / str(pid) / "cmdline").read_bytes().split(b"\0")
                if arguments[1:4] == [b"-I", b"-m", b"cadrumo.entrypoints.runtime.worker"]:
                    workers.append(pid)
            if workers:
                assert len(workers) == 1
                worker_pid = workers[0]
                break
            assert parent.poll() is None and not _dead(guardian_fd)
            assert time.monotonic() < deadline, "registered guardian did not launch the real installed worker"
            time.sleep(0.05)
        worker_start = linux_process_start_identity(worker_pid)
        cleanup.worker_fd = open_linux_pidfd(worker_pid)
        worker_fd = cleanup.worker_fd
        assert not _dead(worker_fd) and _cgroup_for(worker_pid) == cgroup
        worker_native = Path("/proc") / str(worker_pid)
        assert (worker_native / "exe").resolve(strict=True) == interpreter
        worker_args = (worker_native / "cmdline").read_bytes().split(b"\0")
        assert worker_args[1:4] == [b"-I", b"-m", b"cadrumo.entrypoints.runtime.worker"]
        stat_fields = (worker_native / "stat").read_text(encoding="ascii").rsplit(") ", 1)[1].split()
        assert int(stat_fields[1]) == guardian_pid
        assert os.getpgid(worker_pid) == worker_pid and os.getsid(worker_pid) == worker_pid
        assert linux_process_start_identity(worker_pid) == worker_start and not _dead(worker_fd)
        assert linux_process_start_identity(guardian_pid) == guardian_start and not _dead(guardian_fd)
        assert _unit_properties(unit)["MainPID"] == str(guardian_pid)
        assert parent.poll() is None and not (tmp_path / "linux-worker-ready.json").exists()
        assert json.loads((tmp_path / "linux-worker-acquired.json").read_text(encoding="ascii")) == reservation
        assert barrier_deadline - time.monotonic() >= 5, "registration barrier expired before owner loss"
        os.kill(parent.pid, signal.SIGKILL)
        assert time.monotonic() < barrier_deadline, "owner-loss signal was issued after barrier expiry"
        deadline = time.monotonic() + 10
        while not (_dead(worker_fd) and _dead(guardian_fd) and _cgroup_empty(cgroup) and _unit_absent(unit)):
            assert time.monotonic() < deadline, "registered unit survived owner loss before acknowledgment transfer"
            time.sleep(0.05)
        assert _dead(worker_fd) and _dead(guardian_fd)
        assert _cgroup_empty(cgroup) and _unit_absent(unit)
    except BaseException as error:
        primary = error
        raise
    finally:
        asyncio.run(close_async_resources(cleanup, task_name="linux-registration-fixture-close", primary_error=primary))
