"""The runtime server and every console program it starts stay without a visible window."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

from ..process_control import spawn_runtime_server

pytestmark = [pytest.mark.unit, pytest.mark.windows_only, pytest.mark.hex_outbound_adapter]

_CONSOLE_REPORT = """
import ctypes, json, sys
kernel32, user32 = ctypes.windll.kernel32, ctypes.windll.user32
kernel32.GetConsoleWindow.restype = ctypes.c_void_p
window = kernel32.GetConsoleWindow()
attached = kernel32.GetConsoleProcessList((ctypes.c_uint32 * 1)(), 1)
report = {"console": attached > 0, "visible": bool(window) and bool(user32.IsWindowVisible(ctypes.c_void_p(window)))}
"""

# Run as ``<python> serve``: the server's own console, then that of a console
# program it starts with default flags, as the model runtime starts its runners.
_SERVER = (
    _CONSOLE_REPORT
    + """
import os, subprocess
grandchild = subprocess.run(
    [sys.executable, "-c", {probe!r} + "print(json.dumps(report))"],
    capture_output=True, text=True, check=True,
)
report["started"] = json.loads(grandchild.stdout)
with open(os.environ["CONSOLE_REPORT_PATH"], "w", encoding="utf-8") as stream:
    json.dump(report, stream)
"""
)


def _await_report(path: Path) -> object:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if path.exists() and path.stat().st_size:
            return json.loads(path.read_text(encoding="utf-8"))
        time.sleep(0.1)
    raise AssertionError("the spawned server never reported its console")


def test_server_and_its_console_children_get_a_hidden_console(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "serve").write_text(_SERVER.replace("{probe!r}", repr(_CONSOLE_REPORT)), encoding="utf-8")
    report_path = tmp_path / "report.json"
    monkeypatch.chdir(tmp_path)

    # The base interpreter, because a virtual environment's launcher would itself
    # stand between the spawn and the reporting server.
    server = Path(sys.base_prefix) / "python.exe"
    spawn_runtime_server(server, {**os.environ, "CONSOLE_REPORT_PATH": str(report_path)})

    hidden = {"console": True, "visible": False}
    assert _await_report(report_path) == {**hidden, "started": hidden}
