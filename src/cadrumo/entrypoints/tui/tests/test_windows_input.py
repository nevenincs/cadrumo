"""On Windows a Cadrumo app's console input loop sleeps until input arrives or the app stops."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="the console input loop under test is Windows only"),
]


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
        env={**os.environ, "CADRUMO_TEST_RESULT": str(result)},
        **_hidden_console(),
    )
    try:
        assert child.wait(timeout=20) == 0
    finally:
        _stopped(child)
    assert result.read_text(encoding="utf-8") == "escape"


def test_an_idle_app_wakes_no_input_thread_and_its_stop_still_ends_input() -> None:
    import psutil

    child = subprocess.Popen(
        [sys.executable, "-m", "cadrumo.entrypoints.tui.tests.windows_input_apps", "idle"],
        **_hidden_console(),
    )
    try:
        launched = psutil.Process(child.pid)
        # Past startup, inside the idle stretch before the app's own stop.
        time.sleep(1.5)
        # A virtual environment's interpreter can be a launcher that runs the
        # app in a child process, so the whole tree is counted.
        tree = [launched, *launched.children(recursive=True)]

        def counted() -> int:
            total = 0
            for process in tree:
                switches = process.num_ctx_switches()
                total += int(switches.voluntary) + int(switches.involuntary)
            return total

        before = counted()
        time.sleep(1.5)
        switches = counted() - before
        # Textual's own loop wakes ten times a second, which alone is 15 switches here.
        assert switches < 8, f"{switches} context switches while idle"
        # The stop must reach the sleeping input loop: the app exits on its own.
        assert child.wait(timeout=15) == 0
    finally:
        _stopped(child)
