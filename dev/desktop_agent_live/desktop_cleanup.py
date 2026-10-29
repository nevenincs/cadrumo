"""Track and settle the exact desktop lane process tree."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Iterable
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Final

import psutil

from cadrumo_client.transport.windows_owned_process import WindowsOwnedProcess

from .scans import ProcessRecord, ScanResult, descendants, process_table, scan_command_lines, survivors

_WATCH_SECONDS: Final = 1.0
_CLOSE_SECONDS: Final = 60.0


@dataclass(slots=True)
class Watch:
    """Every process the run started, recorded as it appears, and the key findings on their command lines."""

    roots: list[int]
    members: Callable[[], tuple[int, ...]] = tuple
    started: set[ProcessRecord] = field(default_factory=set)
    command_lines: list[ScanResult] = field(default_factory=list)
    _stop: threading.Event = field(default_factory=threading.Event)
    _thread: threading.Thread | None = None

    def observe(self) -> None:
        """Record the run's processes now and scan the command lines of the new ones."""
        members = self.members()
        table = process_table()
        current = descendants(table, self.roots) | {table[pid] for pid in members if pid in table}
        new = current - self.started
        if new:
            self.command_lines.append(scan_command_lines(new))
            self.started |= new

    def start(self) -> None:
        """Observe in the background until :meth:`stop`."""

        def loop() -> None:
            while not self._stop.wait(_WATCH_SECONDS):
                with suppress(Exception):
                    self.observe()

        self._thread = threading.Thread(target=loop, name="desktop-agent-live-watch", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop observing, after one last observation."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=30)
        self.observe()


def desktop_exit_code(process: WindowsOwnedProcess) -> int | None:
    """The desktop's exit code, or ``None`` while it runs."""
    from cadrumo_client.contracts.contracts import RefusalCode, RefusalError

    try:
        return int(process.wait(timeout=0))
    except RefusalError as error:
        if error.reason is RefusalCode.TIMEOUT:
            return None
        raise


def close_windows(pid: int) -> int:
    """Ask every application window of ``pid`` to close, as the title bar's close does; return how many.

    Tool windows are not the person's to close: the window toolkit's own event
    target is one, and closing it would end the event loop that exits the desktop.
    """
    import win32con
    import win32gui
    import win32process

    windows: list[int] = []

    def collect(handle: int, _extra: object) -> bool:
        if (
            win32process.GetWindowThreadProcessId(handle)[1] == pid
            and win32gui.IsWindowVisible(handle)
            and not win32gui.GetWindowLong(handle, win32con.GWL_EXSTYLE) & win32con.WS_EX_TOOLWINDOW
            and not win32gui.GetWindow(handle, win32con.GW_OWNER)
        ):
            windows.append(handle)
        return True

    win32gui.EnumWindows(collect, None)
    for handle in windows:
        win32gui.PostMessage(handle, win32con.WM_CLOSE, 0, 0)
    return len(windows)


def _wait_for_exit(started: Iterable[ProcessRecord]) -> None:
    """Wait on the started processes that still run until they end or the close bound passes."""
    running: list[psutil.Process] = []
    for record in started:
        with suppress(psutil.Error):
            process = psutil.Process(record.pid)
            if process.ppid() == record.parent:
                running.append(process)
    psutil.wait_procs(running, timeout=_CLOSE_SECONDS)


def settle_desktop(desktop: WindowsOwnedProcess, watch: Watch) -> list[str]:
    """Close the window, and return what the run left behind."""
    failures: list[str] = []
    with suppress(Exception):
        watch.observe()
    if desktop_exit_code(desktop) is None:
        close_windows(desktop.pid)
        with suppress(Exception):
            desktop.wait(timeout=_CLOSE_SECONDS)
    if desktop_exit_code(desktop) is None:
        failures.append(f"the desktop did not close within {_CLOSE_SECONDS:.0f}s of its close request")
    watch.stop()
    _wait_for_exit(watch.started)
    left = survivors(watch.started, process_table())
    if left:
        failures.append("processes the run started survive it: " + ", ".join(f"{p.pid}:{p.name}" for p in left))
    else:
        print(json.dumps({"step": "no_surviving_processes", "started": len(watch.started)}), flush=True)
    return failures
