"""Separate native HRESULT crash control for the bound scheduler restart policy."""

from __future__ import annotations

import ctypes
import json
import sys
import time
from collections.abc import Generator
from contextlib import contextmanager
from ctypes import wintypes
from pathlib import Path
from typing import Protocol, cast
from uuid import uuid4

import pytest

from . import test_windows_manager_stop_native as fixture

_E_FAIL = 0x80004005
pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_outbound_adapter,
    pytest.mark.serial,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Task Scheduler and an interactive token"),
]


class _TaskResult(Protocol):
    LastTaskResult: int


def _last_result(task_name: str, identity: fixture._XmlShape) -> int:
    def sample(folder: fixture._TaskFolder) -> int:
        task = cast(_TaskResult, fixture._require_owned_task(folder, task_name, identity))
        return task.LastTaskResult & 0xFFFFFFFF

    return fixture._scheduler_call(sample)


@contextmanager
def _retained_process(first: fixture._Event) -> Generator[tuple[ctypes.CDLL, int]]:
    kernel = fixture._win_library("kernel32")
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = cast(int, kernel.OpenProcess(0x1000 | 0x100000, False, first["pid"]))
    assert handle, "first native crash process handle was unavailable"
    try:
        kernel.GetProcessTimes.argtypes = (
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
        )
        kernel.GetProcessTimes.restype = wintypes.BOOL
        created, exited, kernel_time, user_time = (wintypes.FILETIME() for _ in range(4))
        assert kernel.GetProcessTimes(
            handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel_time), ctypes.byref(user_time)
        ), "retained crash process birth was unavailable"
        birth = str((created.dwHighDateTime << 32) | created.dwLowDateTime)
        assert birth == first["start"], "first native crash process incarnation changed"
        kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        kernel.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        kernel.GetExitCodeProcess.restype = wintypes.BOOL
        yield kernel, handle
    finally:
        kernel.CloseHandle(handle)


def test_task_restarts_after_unrequested_native_hresult_failure(tmp_path: Path, request: pytest.FixtureRequest) -> None:
    """Observe native E_FAIL and a distinct scheduler restart without requesting Stop."""
    pythonw, owner_sid = fixture._native_prerequisites()
    root = fixture._make_temp_root(tmp_path)
    artifact = request.config.rootpath / ".tmp" / f"windows-task-hresult-restart-{uuid4().hex}.json"
    record: dict[str, object] = {"native_exit_expected": _E_FAIL, "intentional_stop_before_observation": False}
    try:
        with fixture._registered_probe_task(
            root=root, scenario="fail_start_hresult", pythonw=pythonw, owner_sid=owner_sid
        ) as (task_name, identity, events_path):
            fixture._start_task(task_name, identity)
            events = fixture._wait_for_event(events_path, "started", timeout=12)
            starts = tuple(event for event in events if event["kind"] == "started")
            assert len(starts) == 1
            first = starts[0]
            restart_deadline = time.monotonic() + 90
            record["first_process"] = first
            artifact.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            with _retained_process(first) as (kernel, handle):
                waited = kernel.WaitForSingleObject(handle, 12_000)
                assert waited == 0, "first native HRESULT crash did not exit within twelve seconds"
                exit_code = wintypes.DWORD()
                assert kernel.GetExitCodeProcess(handle, ctypes.byref(exit_code))
                record["first_native_exit"] = exit_code.value
                assert exit_code.value == _E_FAIL
            deadline = time.monotonic() + 5
            result = _last_result(task_name, identity)
            while result != _E_FAIL and time.monotonic() < deadline:
                time.sleep(0.05)
                result = _last_result(task_name, identity)
            record["task_last_result_after_first_exit"] = result
            assert result == _E_FAIL, "scheduler did not expose the actual first native HRESULT exit"
            artifact.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            while time.monotonic() < restart_deadline:
                starts = tuple(event for event in fixture._read_events(events_path) if event["kind"] == "started")
                if len(starts) >= 2:
                    break
                time.sleep(0.25)
            record["observed_starts"] = starts
            assert len(starts) >= 2, "Task Scheduler did not restart an unrequested native HRESULT failure"
            assert starts[1]["at_ns"] - first["at_ns"] >= 55_000_000_000
            assert (starts[1]["pid"], starts[1]["start"]) != (first["pid"], first["start"])
        record["exact_fixture_cleanup_completed"] = True
    except BaseException as error:
        error.add_note(json.dumps(record, sort_keys=True))
        raise
    finally:
        artifact.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
