"""Real creation-time Job containment, nested descendants and abrupt owner loss."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError

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
