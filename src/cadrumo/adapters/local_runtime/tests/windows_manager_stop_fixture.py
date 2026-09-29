"""Bounded hidden-window child used only by the native Task Scheduler probe."""

from __future__ import annotations

import ctypes
import json
import os
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import cast

_WINDOWS_DLL_LOADER = "WinDLL"


def _win_library(name: str) -> ctypes.CDLL:
    loader = cast(Callable[..., ctypes.CDLL], getattr(ctypes, _WINDOWS_DLL_LOADER))
    return loader(name, use_last_error=True)


def _process_start_identity() -> str:
    """Return this process's kernel creation time for PID-reuse checks."""
    from ctypes import wintypes

    kernel = _win_library("kernel32")
    current = kernel.GetCurrentProcess
    current.argtypes = ()
    current.restype = wintypes.HANDLE
    get_times = kernel.GetProcessTimes
    get_times.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
    )
    get_times.restype = wintypes.BOOL
    created = wintypes.FILETIME()
    exited = wintypes.FILETIME()
    kernel_time = wintypes.FILETIME()
    user_time = wintypes.FILETIME()
    if not get_times(
        current(), ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel_time), ctypes.byref(user_time)
    ):
        raise OSError("process identity unavailable")
    return str((created.dwHighDateTime << 32) | created.dwLowDateTime)


def _record(path: Path, *, kind: str, start_identity: str) -> None:
    """Append only timestamp, event kind and process identity."""
    data = (
        json.dumps(
            {"at_ns": time.time_ns(), "kind": kind, "pid": os.getpid(), "start": start_identity},
            separators=(",", ":"),
        ).encode("ascii")
        + b"\n"
    )
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        remaining = memoryview(data)
        while remaining:
            written = os.write(descriptor, remaining)
            if written <= 0:
                raise OSError("event record write made no progress")
            remaining = remaining[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _run(root: Path, scenario: str) -> int:
    import win32con
    import win32gui

    event_path = root / "events.jsonl"
    process_start = _process_start_identity()
    _record(event_path, kind="started", start_identity=process_start)
    if scenario == "fail_start":
        time.sleep(0.2)
        return 71

    drain_release_path = root / f"release-drain-{os.getpid()}-{process_start}.request"
    draining = False
    drain_deadline: float | None = None

    def window_proc(hwnd: int, message: int, wparam: int, lparam: int) -> int:
        nonlocal drain_deadline, draining
        if message == win32con.WM_CLOSE:
            _record(event_path, kind="wm_close", start_identity=process_start)
            if scenario == "fail_on_close":
                _record(event_path, kind="failure_during_stop", start_identity=process_start)
                os._exit(72)
            if draining:
                return 0
            _record(event_path, kind="drain_started", start_identity=process_start)
            draining = True
            drain_deadline = time.monotonic() + 4
            return 0
        if message == win32con.WM_DESTROY:
            _record(event_path, kind="exited_successfully", start_identity=process_start)
            win32gui.PostQuitMessage(0)
            return 0
        return win32gui.DefWindowProc(hwnd, message, wparam, lparam)

    class_name = f"CadrumoManagedStopProbe-{os.getpid()}"
    window_class = win32gui.WNDCLASS()
    class_name_attribute = "lpszClassName"
    window_proc_attribute = "lpfnWndProc"
    setattr(window_class, class_name_attribute, class_name)
    setattr(window_class, window_proc_attribute, window_proc)
    atom = win32gui.RegisterClass(window_class)
    hwnd = win32gui.CreateWindow(atom, class_name, 0, 0, 0, 0, 0, 0, 0, window_class.hInstance, None)
    if not hwnd:
        raise OSError("hidden probe window could not be created")
    _record(event_path, kind="window_ready", start_identity=process_start)
    cleanup_path = root / f"cleanup-{os.getpid()}-{process_start}.request"
    self_termination_deadline = time.monotonic() + 75
    self_termination_requested = False
    while True:
        if win32gui.PumpWaitingMessages():
            return 0
        try:
            request = cleanup_path.read_text(encoding="ascii").strip()
        except FileNotFoundError:
            request = ""
        if request == f"{os.getpid()}:{process_start}":
            _record(event_path, kind="cleanup_requested", start_identity=process_start)
            win32gui.SendMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        if draining and drain_deadline is not None:
            try:
                drain_request = drain_release_path.read_text(encoding="ascii").strip()
            except FileNotFoundError:
                drain_request = ""
            if drain_request == f"{os.getpid()}:{process_start}":
                _record(event_path, kind="drain_release_observed", start_identity=process_start)
                _record(event_path, kind="drain_completed", start_identity=process_start)
                win32gui.DestroyWindow(hwnd)
            elif time.monotonic() >= drain_deadline:
                _record(event_path, kind="drain_timed_out", start_identity=process_start)
                win32gui.DestroyWindow(hwnd)
        if time.monotonic() >= self_termination_deadline and not self_termination_requested:
            _record(event_path, kind="self_termination_deadline", start_identity=process_start)
            self_termination_requested = True
            win32gui.SendMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        time.sleep(0.02)


def main() -> int:
    if len(sys.argv) != 5 or sys.argv[1] != "--root" or sys.argv[3] != "--scenario":
        return 64
    root = Path(sys.argv[2])
    scenario = sys.argv[4]
    if not root.is_absolute() or scenario not in {"graceful", "fail_on_close", "fail_start"}:
        return 64
    resolved = root.resolve(strict=True)
    if resolved != root or root.is_symlink() or not root.is_dir():
        return 64
    return _run(root, scenario)


if __name__ == "__main__":
    raise SystemExit(main())
