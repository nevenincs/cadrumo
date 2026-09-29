"""Receive Task Scheduler's close request while an owned task drains."""

from __future__ import annotations

import time
from threading import Event, Lock, Thread
from types import TracebackType
from typing import Self

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.management import RuntimeServiceBinding
from .windows_manager import WindowsTaskManager


class WindowsManagedRuntimeStop:
    """Prepare an exact-task Stop without changing persistent logon autostart.

    Task Scheduler sends WM_CLOSE to a window in the task process. Its Stop
    call may block until that process exits, so the COM call runs separately.
    The server begins its bounded drain once the close request is observed.
    """

    def __init__(self, binding: RuntimeServiceBinding, stop: Event) -> None:
        """Bind the process window and exact per-user task."""
        self._manager = WindowsTaskManager(binding)
        self._stop = stop
        self._ready = Event()
        self._closed = Event()
        self._closing = Event()
        self._finished = Event()
        self._requested = False
        self._guard = Lock()
        self._hwnd = 0
        self._thread = Thread(target=self._window_loop, name="runtime-task-close-window", daemon=True)

    def _window_loop(self) -> None:
        import win32con
        import win32gui

        def window_proc(hwnd: int, message: int, wparam: int, lparam: int) -> int:
            if message == win32con.WM_CLOSE:
                self._closed.set()
                self._stop.set()
                return 0
            if message == win32con.WM_DESTROY:
                win32gui.PostQuitMessage(0)
                return 0
            return win32gui.DefWindowProc(hwnd, message, wparam, lparam)

        try:
            window_class = win32gui.WNDCLASS()
            class_name_attribute = "lpszClassName"
            window_proc_attribute = "lpfnWndProc"
            setattr(window_class, class_name_attribute, f"CadrumoRuntimeStop-{id(self)}")
            setattr(window_class, window_proc_attribute, window_proc)
            atom = win32gui.RegisterClass(window_class)
            self._hwnd = win32gui.CreateWindow(
                atom, window_class.lpszClassName, 0, 0, 0, 0, 0, 0, 0, window_class.hInstance, None
            )
        except Exception:
            self._ready.set()
            self._finished.set()
            return
        self._ready.set()
        try:
            while not win32gui.PumpWaitingMessages():
                if self._closing.is_set():
                    win32gui.DestroyWindow(self._hwnd)
                    break
                self._closing.wait(0.02)
        finally:
            self._finished.set()

    def __enter__(self) -> Self:
        """Start the native message loop before accepting stop requests."""
        self._thread.start()
        if not self._ready.wait(5) or not self._hwnd:
            self._closing.set()
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, traceback: TracebackType | None
    ) -> None:
        """Close only this process's stop window."""
        self._closing.set()
        self._thread.join(timeout=1)

    def __call__(self) -> None:
        """Return only after this process observes native close or a refusal."""
        with self._guard:
            if self._requested or self._finished.is_set():
                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
            self._requested = True
        completed = Event()
        submitted = Event()
        failures: list[BaseException] = []

        def request_stop() -> None:
            try:
                self._manager.stop_current_process(submitted)
            except BaseException as error:
                failures.append(error)
            finally:
                completed.set()

        Thread(target=request_stop, name="runtime-task-stop", daemon=True).start()
        deadline = time.monotonic() + 5
        while not (self._closed.is_set() and submitted.is_set()):
            if completed.is_set() and (failures or not submitted.is_set()):
                if not submitted.is_set():
                    with self._guard:
                        self._requested = False
                error = failures[0] if failures else None
                if isinstance(error, RuntimeRefusalError):
                    raise error
                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
            if time.monotonic() >= deadline:
                # The native request may have been accepted despite the lost
                # close acknowledgement. Its eventual effects are uncertain.
                raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
            self._closed.wait(0.02)
        if completed.is_set() and failures:
            error = failures[0]
            if isinstance(error, RuntimeRefusalError):
                raise error
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
