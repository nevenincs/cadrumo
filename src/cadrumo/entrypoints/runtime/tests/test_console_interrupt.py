"""A console Ctrl+C drains the runtime even when its launcher passed on "ignore Ctrl+C".

Each case runs a disposable launcher on a hidden console of its own. The
launcher sets the ignore flag, which the runtime inherits, and then sends
Ctrl+C to that whole console. Synthetic roots contain no taxpayer profiles.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from cadrumo.adapters.local_runtime.tests.process_support import fixture_arguments, fixture_environment, native_python
from cadrumo.application.runtime.contracts import RuntimeExitReason
from cadrumo.core.child_console import WINDOWS_CREATE_NO_WINDOW

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="the inherited ignore flag is a Windows console property"),
]

_FIXTURE = "cadrumo.entrypoints.runtime.tests.console_interrupt_fixture"


def _interrupted(mode: str, root: Path) -> dict[str, object]:
    completed = subprocess.run(  # noqa: S603 -- exact interpreter and fixed in-repository fixture.
        (str(native_python()), *fixture_arguments(_FIXTURE, mode, str(root))),
        env=fixture_environment(),
        capture_output=True,
        timeout=None,
        check=False,
        # The fixture's Ctrl+C reaches only the processes on this hidden console.
        creationflags=WINDOWS_CREATE_NO_WINDOW,
    )
    runtime_errors = (root / "runtime.stderr").read_bytes() if (root / "runtime.stderr").exists() else b""
    assert completed.returncode == 0, (completed.stderr[-4000:], runtime_errors[-4000:])
    loaded: object = json.loads(completed.stdout)
    assert isinstance(loaded, dict)
    return {str(key): value for key, value in loaded.items()}


@pytest.mark.parametrize("mode", ["supervised", "unsupervised"])
def test_ctrl_c_drains_a_runtime_that_inherited_the_ignore_flag(tmp_path: Path, mode: str) -> None:
    result = _interrupted(mode, tmp_path)
    assert result["exit_code"] == RuntimeExitReason.SIGNAL_STOP
    announcements = result["announcements"]
    assert isinstance(announcements, list)
    if mode == "supervised":
        assert [entry["type"] for entry in announcements] == ["ready", "stopping"]
        assert announcements[-1] == {"type": "stopping", "reason": RuntimeExitReason.SIGNAL_STOP.value}
    else:
        assert announcements == []


def test_without_restoring_ctrl_c_the_inherited_flag_hides_the_stop(tmp_path: Path) -> None:
    # The same launch with the restoring call removed proves the case above
    # exercises a real inherited flag rather than a console that never ignored Ctrl+C.
    assert _interrupted("without-reenable", tmp_path) == {"serving_after_interrupt": True}
