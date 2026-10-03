"""Real creation-time Job containment, nested descendants and abrupt owner loss."""

from __future__ import annotations

import asyncio
import json
import math
import os
import sys
import time
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.core.async_cleanup import close_async_resources

from ..windows_process import WindowsProcessScope
from .process_support import fixture_arguments, fixture_environment, launch_fixture, native_python

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_outbound_adapter,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native creation-time Windows Job assignment"),
]

_FIXTURE = "cadrumo.adapters.local_runtime.tests.job_fixture"


class _ProcessFacts(BaseModel):
    parent: int
    child: int
    breakaway_refused: bool


async def _record(path: Path) -> _ProcessFacts:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            return _ProcessFacts.model_validate_json(path.read_text())
        except (FileNotFoundError, ValidationError):
            await asyncio.sleep(0.02)
    pytest.fail("synthetic child did not publish process facts within the deadline")


def test_crash_status_exit_is_reported_as_the_unsigned_native_code(tmp_path: Path) -> None:
    scope = WindowsProcessScope()
    try:
        process = scope.launch(
            executable=native_python(),
            arguments=("-c", "import ctypes; ctypes.windll.kernel32.ExitProcess(0xC0000005)"),
            directory=tmp_path,
            environment={"SYSTEMROOT": os.environ["SYSTEMROOT"]},
        )
        assert process.wait(timeout=5) == 0xC0000005
    finally:
        scope.terminate()


def test_normal_exit_and_environment_are_preserved(tmp_path: Path) -> None:
    scope = WindowsProcessScope()
    try:
        process = scope.launch(
            executable=native_python(),
            arguments=("-c", "import os,sys; sys.exit(23 if os.environ.get('SYNTHETIC_VALUE') == 'present' else 99)"),
            directory=tmp_path,
            environment={"SYSTEMROOT": os.environ["SYSTEMROOT"], "SYNTHETIC_VALUE": "present"},
        )
        assert process.wait(timeout=5) == 23
    finally:
        scope.terminate()
    with pytest.raises(RuntimeRefusalError) as caught:
        scope.launch(executable=native_python(), arguments=(), directory=tmp_path, environment={})
    assert caught.value.reason is RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE


def test_launch_does_not_inherit_ambient_inheritable_handles(tmp_path: Path) -> None:
    import pywintypes
    import win32api
    import win32event

    attributes = pywintypes.SECURITY_ATTRIBUTES()
    attributes.bInheritHandle = True
    canary = win32event.CreateEvent(attributes, True, False, None)
    scope = WindowsProcessScope()
    try:
        process = scope.launch(
            executable=native_python(),
            arguments=(
                "-c",
                "import ctypes,sys; from ctypes import wintypes; k=ctypes.WinDLL('kernel32'); "
                "k.SetEvent.argtypes=(wintypes.HANDLE,); k.SetEvent.restype=wintypes.BOOL; "
                "sys.exit(1 if k.SetEvent(int(sys.argv[1])) else 0)",
                str(int(canary)),
            ),
            directory=tmp_path,
            environment={"SYSTEMROOT": os.environ["SYSTEMROOT"]},
        )
        assert process.wait(timeout=5) == 0
        assert win32event.WaitForSingleObject(canary, 0) == win32event.WAIT_TIMEOUT
    finally:
        scope.terminate()
        win32api.CloseHandle(canary)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["tree", "exited"])
async def test_close_terminates_grandchild_even_when_direct_child_exited(tmp_path: Path, mode: str) -> None:
    import win32api
    import win32event

    scope = WindowsProcessScope()
    handles: list[int] = []
    try:
        record_path = tmp_path / "process-facts.json"
        process = scope.launch(
            executable=native_python(),
            arguments=fixture_arguments(_FIXTURE, mode, str(record_path)),
            directory=tmp_path,
            environment=fixture_environment(),
        )
        facts = await _record(record_path)
        assert facts.parent == process.pid
        assert facts.breakaway_refused is True
        child_handle = win32api.OpenProcess(0x100000, False, facts.child)
        handles.append(child_handle)
        assert win32event.WaitForSingleObject(child_handle, 0) == win32event.WAIT_TIMEOUT
        if mode == "exited":
            assert process.wait(timeout=2) == 0
        await scope.close()
        assert win32event.WaitForSingleObject(child_handle, 1000) == win32event.WAIT_OBJECT_0
    finally:
        scope.terminate()
        for handle in handles:
            win32api.CloseHandle(handle)


@pytest.mark.asyncio
async def test_abrupt_owner_death_closes_job_without_graceful_callbacks(tmp_path: Path) -> None:
    import win32api
    import win32event

    record_path = tmp_path / "process-facts.json"
    owner = await launch_fixture(_FIXTURE, "owner", str(record_path))
    handles: list[int] = []
    try:
        assert owner.stdout is not None
        assert (await asyncio.wait_for(owner.stdout.readline(), timeout=5)).strip() == b"ready"
        facts = await _record(record_path)
        assert facts.breakaway_refused is True
        for pid in (facts.parent, facts.child):
            handle = win32api.OpenProcess(0x100000, False, pid)
            handles.append(handle)
            assert win32event.WaitForSingleObject(handle, 0) == win32event.WAIT_TIMEOUT
        owner.kill()
        await asyncio.wait_for(owner.wait(), timeout=5)
        for handle in handles:
            assert win32event.WaitForSingleObject(handle, 2000) == win32event.WAIT_OBJECT_0
    finally:
        if owner.returncode is None:
            owner.kill()
        _output, errors = await asyncio.wait_for(owner.communicate(), timeout=5)
        for handle in handles:
            win32api.CloseHandle(handle)
        assert not errors, errors.decode(errors="replace")


@pytest.mark.asyncio
async def test_actual_chromium_descendants_end_on_abrupt_owner_death(tmp_path: Path) -> None:
    import win32api
    import win32event
    from playwright.async_api import async_playwright

    async with async_playwright() as playwright:
        if not Path(playwright.chromium.executable_path).is_file():
            pytest.skip("native Chromium is not installed; no browser containment evidence")
    record = tmp_path / "browser-ready.txt"
    owner = await launch_fixture(_FIXTURE, "browser-owner", str(record))
    handles: list[int] = []
    try:
        assert owner.stdout is not None
        assert (await asyncio.wait_for(owner.stdout.readline(), timeout=5)).strip() == b"ready"
        deadline = time.monotonic() + 8
        while not record.exists() and time.monotonic() < deadline:
            await asyncio.sleep(0.05)
        assert record.read_text() == "browser-ready"
        assert owner.stdin is not None
        owner.stdin.write(b"members\n")
        await owner.stdin.drain()
        members = json.loads(await asyncio.wait_for(owner.stdout.readline(), timeout=2))
        assert isinstance(members, list) and len(members) >= 4
        for pid in members:
            assert isinstance(pid, int) and pid > 0
            handle = win32api.OpenProcess(0x100000, False, pid)
            handles.append(handle)
            assert win32event.WaitForSingleObject(handle, 0) == win32event.WAIT_TIMEOUT
        owner.kill()
        await asyncio.wait_for(owner.wait(), timeout=5)
        for handle in handles:
            assert win32event.WaitForSingleObject(handle, 2000) == win32event.WAIT_OBJECT_0
    finally:
        if owner.returncode is None:
            owner.kill()
        _output, errors = await asyncio.wait_for(owner.communicate(), timeout=5)
        for handle in handles:
            win32api.CloseHandle(handle)
        assert not errors, errors.decode(errors="replace")


class _UnpublishedLaunchFacts(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    owner_pid: int
    owner_created: str
    child_pid: int
    child_created: str
    job_handle: int
    published_children: int
    barrier_deadline: float


class _LaunchOwnerLossCleanup:
    """Keep the original subprocess and exact native objects through failed assertions."""

    def __init__(self, process: asyncio.subprocess.Process) -> None:
        self.process = process
        self.owner_handle: int | None = None
        self.child_handle: int | None = None
        self.job_handle: int | None = None
        self.member_handles: dict[int, int] = {}
        self.collected = False

    def release_job_observation(self) -> None:
        import win32api

        if self.job_handle is not None:
            win32api.CloseHandle(self.job_handle)
            self.job_handle = None

    async def close(self) -> None:
        import win32api
        import win32event
        import win32job

        failures: list[BaseException] = []
        if self.owner_handle is not None:
            try:
                if win32event.WaitForSingleObject(self.owner_handle, 0) == win32event.WAIT_TIMEOUT:
                    win32api.TerminateProcess(self.owner_handle, 124)
            except BaseException as error:
                failures.append(error)
        if self.job_handle is not None:
            try:
                win32job.TerminateJobObject(self.job_handle, 124)
                deadline = time.monotonic() + 2
                while win32job.QueryInformationJobObject(self.job_handle, win32job.JobObjectBasicAccountingInformation)[
                    "ActiveProcesses"
                ]:
                    if time.monotonic() >= deadline:
                        raise RuntimeError("owned launch job did not settle")
                    await asyncio.sleep(0.02)
                self.release_job_observation()
            except BaseException as error:
                failures.append(error)
        if not self.collected:
            try:
                if self.process.returncode is None:
                    self.process.kill()
                await asyncio.wait_for(self.process.communicate(), timeout=5)
            except BaseException as error:
                failures.append(error)
            else:
                self.collected = True
        for name in ("owner_handle", "child_handle"):
            handle = getattr(self, name)
            if handle is not None:
                try:
                    if win32event.WaitForSingleObject(handle, 5000) != win32event.WAIT_OBJECT_0:
                        raise RuntimeError("owned launch process did not settle")
                    win32api.CloseHandle(handle)
                except BaseException as error:
                    failures.append(error)
                else:
                    setattr(self, name, None)
        for pid, handle in tuple(self.member_handles.items()):
            try:
                if win32event.WaitForSingleObject(handle, 5000) != win32event.WAIT_OBJECT_0:
                    raise RuntimeError("owned launch member did not settle")
                win32api.CloseHandle(handle)
            except BaseException as error:
                failures.append(error)
            else:
                del self.member_handles[pid]
        if failures:
            raise BaseExceptionGroup("native launch fixture resources remain owned", failures)


@pytest.mark.asyncio
async def test_owner_loss_after_native_creation_before_process_publication(tmp_path: Path) -> None:
    """The kernel-contained child dies while its launch has not returned an owner."""
    import win32api
    import win32con
    import win32event
    import win32job
    import win32process

    record = tmp_path / "unpublished-native-launch.json"
    owner = _LaunchOwnerLossCleanup(await launch_fixture(_FIXTURE, "launch-owner-loss", str(record)))
    primary: BaseException | None = None
    try:
        assert owner.process.stdout is not None
        ready = await asyncio.wait_for(owner.process.stdout.readline(), timeout=5)
        assert ready.strip() == b"native-created-unpublished"
        encoded = record.read_bytes()
        assert 0 < len(encoded) <= 4096
        facts = _UnpublishedLaunchFacts.model_validate_json(encoded)
        assert facts.owner_pid == owner.process.pid
        assert facts.child_pid > 0 and facts.child_pid != facts.owner_pid
        assert facts.job_handle > 0 and facts.published_children == 0
        assert math.isfinite(facts.barrier_deadline)
        owner.owner_handle = win32api.OpenProcess(
            win32con.SYNCHRONIZE
            | win32con.PROCESS_QUERY_INFORMATION
            | win32con.PROCESS_TERMINATE
            | win32con.PROCESS_DUP_HANDLE,
            False,
            facts.owner_pid,
        )
        owner.child_handle = win32api.OpenProcess(
            win32con.SYNCHRONIZE | win32con.PROCESS_QUERY_INFORMATION, False, facts.child_pid
        )
        assert win32event.WaitForSingleObject(owner.owner_handle, 0) == win32event.WAIT_TIMEOUT
        assert win32event.WaitForSingleObject(owner.child_handle, 0) == win32event.WAIT_TIMEOUT
        assert win32process.GetProcessTimes(owner.owner_handle)["CreationTime"].isoformat() == facts.owner_created
        assert win32process.GetProcessTimes(owner.child_handle)["CreationTime"].isoformat() == facts.child_created
        owner.job_handle = win32api.DuplicateHandle(
            owner.owner_handle,
            facts.job_handle,
            win32api.GetCurrentProcess(),
            win32job.JOB_OBJECT_QUERY | win32job.JOB_OBJECT_TERMINATE,
            False,
            0,
        )
        assert win32job.IsProcessInJob(owner.child_handle, owner.job_handle)
        members = win32job.QueryInformationJobObject(owner.job_handle, win32job.JobObjectBasicProcessIdList)
        assert isinstance(members, tuple) and 0 < len(members) <= 4096
        assert all(type(pid) is int and pid > 0 for pid in members)
        assert len(set(members)) == len(members)
        assert facts.child_pid in members and facts.owner_pid not in members
        creations = {facts.child_pid: facts.child_created}
        for pid in members:
            if pid == facts.child_pid:
                handle = owner.child_handle
            else:
                handle = win32api.OpenProcess(win32con.SYNCHRONIZE | win32con.PROCESS_QUERY_INFORMATION, False, pid)
                owner.member_handles[pid] = handle
                creations[pid] = win32process.GetProcessTimes(handle)["CreationTime"].isoformat()
            assert win32event.WaitForSingleObject(handle, 0) == win32event.WAIT_TIMEOUT
            assert win32job.IsProcessInJob(handle, owner.job_handle)
        assert win32event.WaitForSingleObject(owner.owner_handle, 0) == win32event.WAIT_TIMEOUT
        assert win32process.GetProcessTimes(owner.owner_handle)["CreationTime"].isoformat() == facts.owner_created
        assert set(win32job.QueryInformationJobObject(owner.job_handle, win32job.JobObjectBasicProcessIdList)) == set(
            members
        )
        for pid in members:
            handle = owner.child_handle if pid == facts.child_pid else owner.member_handles[pid]
            assert win32event.WaitForSingleObject(handle, 0) == win32event.WAIT_TIMEOUT
            assert win32process.GetProcessTimes(handle)["CreationTime"].isoformat() == creations[pid]
            assert win32job.IsProcessInJob(handle, owner.job_handle)
        limits = win32job.QueryInformationJobObject(owner.job_handle, win32job.JobObjectExtendedLimitInformation)
        assert limits["BasicLimitInformation"]["LimitFlags"] == win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        assert sorted(
            win32job.QueryInformationJobObject(owner.job_handle, win32job.JobObjectBasicProcessIdList)
        ) == sorted(members)
        # A controller-held Job would keep the child alive after its owner dies.
        owner.release_job_observation()
        assert owner.job_handle is None
        assert win32event.WaitForSingleObject(owner.child_handle, 0) == win32event.WAIT_TIMEOUT
        for handle in owner.member_handles.values():
            assert win32event.WaitForSingleObject(handle, 0) == win32event.WAIT_TIMEOUT
        assert win32event.WaitForSingleObject(owner.owner_handle, 0) == win32event.WAIT_TIMEOUT
        assert facts.barrier_deadline - time.monotonic() >= 5
        win32api.TerminateProcess(owner.owner_handle, 23)
        assert time.monotonic() < facts.barrier_deadline
        assert win32event.WaitForSingleObject(owner.owner_handle, 5000) == win32event.WAIT_OBJECT_0
        assert win32event.WaitForSingleObject(owner.child_handle, 5000) == win32event.WAIT_OBJECT_0
        for handle in owner.member_handles.values():
            assert win32event.WaitForSingleObject(handle, 5000) == win32event.WAIT_OBJECT_0
        await asyncio.wait_for(owner.process.wait(), timeout=5)
    except BaseException as error:
        primary = error
        raise
    finally:
        await close_async_resources(owner, task_name="native-launch-owner-loss-cleanup", primary_error=primary)
