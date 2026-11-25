"""The install lock excludes a live installer and never outlives a dead one.

Each case runs a real second process that takes the lock through the same
entry point an install uses, so the exclusion and its release are the
operating system's, not a stand-in's.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path

import pytest

from dev.paths import REPO_ROOT

from ..venv import exclusive

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]


def _start_holder(venv: Path) -> tuple[subprocess.Popen[str], int]:
    """Start a process that holds the install lock for ``venv`` until it ends.

    Returns the started process and the PID of the interpreter that holds the
    lock. They differ where the venv's ``python`` is a launcher that runs the
    interpreter as its child, as on Windows.
    """
    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import os, sys\n"
            "from pathlib import Path\n"
            "from dev.env.venv import exclusive\n"
            "with exclusive(Path(os.environ['CADRUMO_LOCK_PROBE_VENV'])):\n"
            "    print('held', os.getpid(), flush=True)\n"
            "    sys.stdin.read()\n",
        ],
        cwd=REPO_ROOT,
        env={**os.environ, "CADRUMO_LOCK_PROBE_VENV": str(venv)},
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    assert holder.stdout is not None
    word, owner = holder.stdout.readline().split()
    assert word == "held"
    return holder, int(owner)


def test_a_live_installer_refuses_a_second_one(tmp_path: Path) -> None:
    venv = tmp_path / ".venv"
    holder, _owner = _start_holder(venv)
    try:
        with pytest.raises(RuntimeError, match="Another dependency install already owns"), exclusive(venv):
            pass
    finally:
        holder.communicate(input="")
    with exclusive(venv):
        pass


def test_an_installer_killed_while_holding_the_lock_leaves_none_behind(tmp_path: Path) -> None:
    """A cancelled job ends the installer before its cleanup runs; the next install proceeds."""
    venv = tmp_path / ".venv"
    holder, owner = _start_holder(venv)
    os.kill(owner, getattr(signal, "SIGKILL", signal.SIGTERM))
    holder.wait()
    with exclusive(venv):
        pass
