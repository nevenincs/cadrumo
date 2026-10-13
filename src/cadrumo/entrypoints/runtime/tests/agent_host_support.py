"""A stand-in cadrumo-agent source tree, a marked lane root and the checks on what the agent received.

The stand-in tree has the layout the runtime launches from: its own
``.venv`` interpreter (a copy of this checkout's environment launcher, which
starts the base interpreter with an empty environment of its own) and a
``cadrumo_agent`` package whose ``cli.main`` module, the agent's declared
command-line module, runs the shared agent peer fixture for ``serve``.
So the runtime's real launch path, containment and frame are exercised, and
nothing of Cadrumo is importable inside the agent.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Final

from cadrumo.adapters.local_runtime.tests import agent_host_fixture
from cadrumo.application.agent_host.lane_root import LANE_MARK_KIND, LANE_MARK_NAME

FAKE_KEY: Final = "sk-test-NOT-A-REAL-KEY"
FAKE_BEARER: Final = "bearer-test-NOT-A-REAL-TOKEN"
DEVELOPMENT_KEY_VARIABLE: Final = "CADRUMO_LLM_CLAUDE_API_KEY"

_STAND_IN_MAIN: Final = """\
import json, runpy, subprocess, sys, threading
from pathlib import Path

config = json.loads((Path(__file__).resolve().parents[2] / "stand_in.json").read_text(encoding="utf-8"))


def probe(command):
    # A program the agent's tree starts: a member of the agent's job, as anything the agent runs is.
    done = subprocess.run(
        command["argv"], input=command["stdin"].encode(), env=command["env"], capture_output=True, timeout=240
    )
    result = {
        "returncode": done.returncode,
        "stdout": done.stdout.decode(errors="replace"),
        "stderr": done.stderr.decode(errors="replace")[-4000:],
    }
    (Path(config["record"]) / "probe.json").write_text(json.dumps(result), encoding="utf-8")


if config.get("probe"):
    threading.Thread(target=probe, args=(config["probe"],), daemon=True).start()
sys.argv = [config["fixture"], config["mode"], config["record"], *sys.argv[1:]]
runpy.run_path(config["fixture"], run_name="__main__")
"""


def stand_in_agent_source(
    directory: Path, *, mode: str = "ready", probe: dict[str, object] | None = None
) -> tuple[Path, Path]:
    """Build a stand-in agent source tree and return it with the directory its peer records into.

    ``probe`` names a program, its environment and its standard input, which
    the stand-in starts as soon as it runs: a process inside the agent's tree.
    """
    source, record = directory / "agent-source", directory / "agent-record"
    environment = Path(sys.executable).parent
    (source / ".venv" / "Scripts").mkdir(parents=True)
    record.mkdir()
    shutil.copy2(environment / "python.exe", source / ".venv" / "Scripts" / "python.exe")
    shutil.copy2(environment.parent / "pyvenv.cfg", source / ".venv" / "pyvenv.cfg")
    command_line = source / "cadrumo_agent" / "cli"
    command_line.mkdir(parents=True)
    (command_line / "__init__.py").write_text("", encoding="utf-8")
    (command_line / "main.py").write_text(_STAND_IN_MAIN, encoding="utf-8")
    (source / "stand_in.json").write_text(
        json.dumps({"fixture": agent_host_fixture.__file__, "mode": mode, "record": str(record), "probe": probe}),
        encoding="utf-8",
    )
    return source, record


def mark_lane_root(root: Path) -> None:
    """Mark an existing storage root for the development lane, as the lane recipe does on an empty root."""
    canonical = Path(os.path.normcase(root.resolve(strict=True)))
    document = {"schema": 1, "kind": LANE_MARK_KIND, "root": str(canonical)}
    (canonical / LANE_MARK_NAME).write_text(json.dumps(document, sort_keys=True), encoding="utf-8")


def received(record: Path, *, within: float = 30) -> dict[str, object]:
    """Return what the stand-in agent recorded once it has recorded it."""
    path = record / "received.json"
    deadline = time.monotonic() + within
    while not path.exists():
        assert time.monotonic() < deadline, "the agent never recorded its start"
        time.sleep(0.05)
    document: object = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return {str(key): value for key, value in document.items()}


def stopped_by_input_end(record: Path) -> bool:
    """Whether the stand-in agent saw its standard input close before it was ended."""
    return (record / "stopped").exists()


def process_alive(pid: int, *, within: float = 0) -> bool:
    """Whether the process still runs after up to ``within`` seconds of waiting for it to end."""
    import pywintypes
    import win32api
    import win32event

    try:
        handle = win32api.OpenProcess(0x100000, False, pid)
    except pywintypes.error:
        return False
    try:
        return win32event.WaitForSingleObject(handle, int(within * 1000)) == win32event.WAIT_TIMEOUT
    finally:
        win32api.CloseHandle(handle)


def tree_reaped(record: Path, *, within: float = 30) -> bool:
    """Whether the stand-in agent's grandchild, which only the tree's containment ends, is gone."""
    grandchild = received(record)["grandchild"]
    assert isinstance(grandchild, int)
    return not process_alive(grandchild, within=within)


def assert_no_secret_exposed(document: dict[str, object]) -> None:
    """Neither the key nor the bearer is in the agent's environment or arguments."""
    exposed = json.dumps({"environment": document["environment"], "arguments": document["arguments"]})
    assert FAKE_KEY not in exposed
    assert FAKE_BEARER not in exposed
    assert "NOT-A-REAL" not in exposed


def probe_result(record: Path, *, within: float = 300) -> dict[str, object]:
    """Return what the program the agent's tree started reported once it has finished."""
    path = record / "probe.json"
    deadline = time.monotonic() + within
    while not path.exists():
        assert time.monotonic() < deadline, "the agent tree's program never finished"
        time.sleep(0.2)
    document: object = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return {str(key): value for key, value in document.items()}
