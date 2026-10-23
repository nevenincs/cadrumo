"""A process the lane starts, at any depth, ends when the lane ends, and the lane keeps its exit code."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import psutil
import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.windows_only]

_NO_WINDOW = 0x08000000
_REPOSITORY = Path(__file__).resolve().parents[3]
# The grandchild waits on an event nothing sets, so only its Job can end it.
_GRANDCHILD = "import threading; threading.Event().wait()"
_LANE = f"""
import subprocess, sys
sys.path.insert(0, {str(_REPOSITORY)!r})
contained = sys.argv[1] == "contained"
if contained:
    from dev.desktop_agent_live.containment import LaneJob
    job = LaneJob()
child = subprocess.Popen([sys.executable, "-c", {_GRANDCHILD!r}], creationflags={_NO_WINDOW})
print(child.pid, flush=True)
if contained:
    print(sorted(job.others()), flush=True)
sys.stdin.readline()
if contained:
    job.end(7)
"""


def _lane(scope: Any, mode: str) -> tuple[Any, int, list[str]]:
    """Start a stand-in lane in ``scope``; return its standard input, its child's PID and what it reported."""
    environment = {name: value for name, value in os.environ.items() if name.upper() in {"SYSTEMROOT", "PATH"}}
    _process, stdin, stdout, stderr = scope.launch_with_standard_pipes(
        executable=Path(sys.executable).resolve(),
        arguments=("-c", _LANE, mode),
        directory=_REPOSITORY,
        environment=environment,
    )
    stderr.close()
    grandchild = int(stdout.readline())
    reported = [stdout.readline().decode().strip()] if mode == "contained" else []
    return (_process, stdin), grandchild, reported


def _end(lane: Any, code: int) -> None:
    process, stdin = lane
    stdin.write(b"done\n")
    stdin.close()
    assert process.wait(timeout=60) == code


def test_a_grandchild_ends_with_the_lane_which_keeps_its_exit_code() -> None:
    from cadrumo_client.transport.windows_process import WindowsProcessScope

    scope = WindowsProcessScope()
    try:
        lane, grandchild, reported = _lane(scope, "contained")
        survivor = psutil.Process(grandchild)
        _end(lane, 7)
        # Its only ending is the lane Job closing; the scope has not been terminated yet.
        survivor.wait(timeout=60)
    finally:
        scope.terminate(timeout=30)
    assert reported == [str([grandchild])]


def test_without_the_job_the_same_grandchild_survives_its_lane() -> None:
    from cadrumo_client.transport.windows_process import WindowsProcessScope

    scope = WindowsProcessScope()
    try:
        lane, grandchild, _ = _lane(scope, "uncontained")
        survivor = psutil.Process(grandchild)
        _end(lane, 0)
        assert survivor.is_running()
    finally:
        scope.terminate(timeout=30)
