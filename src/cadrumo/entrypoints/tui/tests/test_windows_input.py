"""On Windows a Cadrumo app's console input loop sleeps until input arrives or the app stops."""

from __future__ import annotations

import ctypes
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import pytest

from .windows_input_apps import close_event, open_event, set_event, wait_event

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="the console input loop under test is Windows only"),
]

_SYSTEM_PROCESS_INFORMATION = 5
_STATUS_INFO_LENGTH_MISMATCH = ctypes.c_long(0xC0000004).value
_THREAD_WAITING = 5


class _UnicodeString(ctypes.Structure):
    _fields_ = [
        ("length", ctypes.c_uint16),
        ("maximum_length", ctypes.c_uint16),
        ("buffer", ctypes.c_void_p),
    ]


class _ProcessInformation(ctypes.Structure):
    """``SYSTEM_PROCESS_INFORMATION`` as ``winternl.h`` declares it; its threads follow it."""

    _fields_ = [
        ("next_entry_offset", ctypes.c_uint32),
        ("number_of_threads", ctypes.c_uint32),
        ("reserved1", ctypes.c_byte * 48),
        ("image_name", _UnicodeString),
        ("base_priority", ctypes.c_long),
        ("unique_process_id", ctypes.c_void_p),
        ("reserved2", ctypes.c_void_p),
        ("handle_count", ctypes.c_uint32),
        ("session_id", ctypes.c_uint32),
        ("reserved3", ctypes.c_void_p),
        ("peak_virtual_size", ctypes.c_size_t),
        ("virtual_size", ctypes.c_size_t),
        ("reserved4", ctypes.c_uint32),
        ("peak_working_set_size", ctypes.c_size_t),
        ("working_set_size", ctypes.c_size_t),
        ("reserved5", ctypes.c_void_p),
        ("quota_paged_pool_usage", ctypes.c_size_t),
        ("reserved6", ctypes.c_void_p),
        ("quota_non_paged_pool_usage", ctypes.c_size_t),
        ("pagefile_usage", ctypes.c_size_t),
        ("peak_pagefile_usage", ctypes.c_size_t),
        ("private_page_count", ctypes.c_size_t),
        ("reserved7", ctypes.c_int64 * 6),
    ]


class _ClientId(ctypes.Structure):
    _fields_ = [("process", ctypes.c_void_p), ("thread", ctypes.c_void_p)]


class _ThreadInformation(ctypes.Structure):
    """``SYSTEM_THREAD_INFORMATION``, the per-thread record the kernel counts switches in."""

    _fields_ = [
        ("kernel_time", ctypes.c_int64),
        ("user_time", ctypes.c_int64),
        ("create_time", ctypes.c_int64),
        ("wait_time", ctypes.c_uint32),
        ("start_address", ctypes.c_void_p),
        ("client_id", _ClientId),
        ("priority", ctypes.c_long),
        ("base_priority", ctypes.c_long),
        ("context_switches", ctypes.c_uint32),
        ("thread_state", ctypes.c_uint32),
        ("wait_reason", ctypes.c_uint32),
    ]


def _thread_activity(pid: int, tid: int) -> tuple[int, bool]:
    """Return how often the kernel has switched to the thread, and whether it is waiting now.

    A thread blocked in a wait is not runnable, so the scheduler never preempts
    it: its count grows only when something wakes it, however loaded the host is.
    """
    if sys.platform == "win32":
        query = ctypes.WinDLL("ntdll").NtQuerySystemInformation
        query.argtypes = (ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong))
        query.restype = ctypes.c_long
        size = 1 << 20
        while True:
            buffer = ctypes.create_string_buffer(size)
            needed = ctypes.c_ulong(0)
            status = query(_SYSTEM_PROCESS_INFORMATION, buffer, size, ctypes.byref(needed))
            if status != _STATUS_INFO_LENGTH_MISMATCH:
                break
            size = max(size * 2, needed.value + (1 << 16))
        assert status == 0, f"NtQuerySystemInformation failed with status {status:#x}"
        offset = 0
        while True:
            process = _ProcessInformation.from_buffer(buffer, offset)
            if process.unique_process_id == pid:
                threads = (_ThreadInformation * process.number_of_threads).from_buffer(
                    buffer, offset + ctypes.sizeof(_ProcessInformation)
                )
                for thread in threads:
                    if thread.client_id.thread == tid:
                        return int(thread.context_switches), int(thread.thread_state) == _THREAD_WAITING
                raise AssertionError("the input thread ended while the app sat idle")
            if process.next_entry_offset == 0:
                raise AssertionError("the app process ended while it sat idle")
            offset += process.next_entry_offset
    raise AssertionError("per-thread switch counts are a Windows test fixture")


def _hidden_console() -> dict[str, Any]:
    """Run a child in a hidden console of its own, as a terminal pane hosts the TUI."""
    if sys.platform == "win32":
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
        return {"creationflags": subprocess.CREATE_NEW_CONSOLE, "startupinfo": startup}
    raise AssertionError("a console of its own is a Windows test fixture")


def _stopped(child: subprocess.Popen[Any]) -> None:
    if child.poll() is None:
        child.kill()
        child.wait(timeout=10)


def test_a_lone_escape_reaches_the_app_after_the_input_loop_sleeps(tmp_path: Path) -> None:
    # The key reaches the app only if the parser's escape timeout still fires
    # once the input loop has gone back to sleep.
    result = tmp_path / "result.txt"
    child = subprocess.Popen(
        [sys.executable, "-m", "cadrumo.entrypoints.tui.tests.windows_input_apps", "escape"],
        cwd=tmp_path,
        **_hidden_console(),
    )
    try:
        assert child.wait(timeout=20) == 0
    finally:
        _stopped(child)
    assert result.read_text(encoding="utf-8") == "escape"


def _awaited(child: subprocess.Popen[Any], ready: int) -> None:
    # Startup on a loaded host can take many seconds; nothing is counted until the app is idle.
    deadline = time.monotonic() + 120
    while not wait_event(ready, 200):
        assert child.poll() is None, f"the app exited with {child.returncode} before it sat idle"
        assert time.monotonic() < deadline, "the app did not reach its idle screen"


def _waiting_input_thread(pid: int, tid: int) -> int:
    # The input thread started before the first frame; count from the moment it is blocked.
    deadline = time.monotonic() + 10
    while True:
        switches, waiting = _thread_activity(pid, tid)
        if waiting:
            return switches
        assert time.monotonic() < deadline, "the idle app's input thread never blocked"
        time.sleep(0.05)


def _idle_child(resumed: bool, directory: Path) -> subprocess.Popen[Any]:
    if resumed:
        # Textual closes the driver on a suspend and starts it again on resume.
        return subprocess.Popen(
            [sys.executable, "-m", "cadrumo.entrypoints.tui.tests.windows_input_apps", "resumed"],
            cwd=directory,
            **_hidden_console(),
        )
    return subprocess.Popen(
        [sys.executable, "-m", "cadrumo.entrypoints.tui.tests.windows_input_apps", "idle"],
        cwd=directory,
        **_hidden_console(),
    )


@pytest.mark.parametrize("resumed", [False, True], ids=["started", "resumed"])
def test_an_idle_app_wakes_no_input_thread_and_its_stop_still_ends_input(resumed: bool, tmp_path: Path) -> None:
    name = f"Local\\cadrumo-idle-input-{uuid.uuid4().hex}"
    (tmp_path / "events.txt").write_text(name, encoding="utf-8")
    ready, stop = open_event(f"{name}-ready"), open_event(f"{name}-stop")
    child = _idle_child(resumed, tmp_path)
    try:
        _awaited(child, ready)
        # A virtual environment's interpreter can be a launcher that runs the
        # app in a child process, so the app names its own process.
        pid, tid = (int(part) for part in (tmp_path / "idle.txt").read_text(encoding="utf-8").split())
        before = _waiting_input_thread(pid, tid)
        time.sleep(1.5)
        switches = _thread_activity(pid, tid)[0] - before
        # Textual's own input loop wakes ten times a second, which alone is 15 switches here.
        assert switches < 8, f"{switches} context switches of the input thread while idle"
        # The stop must reach the sleeping input loop: the app exits on its own.
        set_event(stop)
        assert child.wait(timeout=15) == 0
    finally:
        _stopped(child)
        close_event(ready)
        close_event(stop)
    if resumed:
        # Quiet because the resumed loop sleeps on its stop event, not because no loop runs.
        assert (tmp_path / "result.txt").read_text(encoding="utf-8") == "waking"
