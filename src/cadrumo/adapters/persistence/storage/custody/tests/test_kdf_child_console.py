"""A supervised runtime's KDF worker runs on a console of its own.

A manager stops a supervised runtime with a console Ctrl+C, which Windows
delivers to every process on that console. Each case runs a real worker from
a disposable process that owns a hidden console, and reads that console's
process list while the worker is ready.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from cadrumo.adapters.local_runtime.tests.process_support import fixture_arguments, fixture_environment, native_python

from ......core.child_console import WINDOWS_CREATE_NO_WINDOW

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_persistence_adapter,
    pytest.mark.skipif(sys.platform != "win32", reason="console ownership is a Windows launch property"),
]

_FIXTURE = "cadrumo.adapters.persistence.storage.custody.tests.kdf_console_fixture"


def _console_members(mode: str, root: Path) -> dict[str, object]:
    completed = subprocess.run(  # noqa: S603 -- exact interpreter and fixed in-repository fixture.
        (str(native_python()), *fixture_arguments(_FIXTURE, mode, str(root))),
        env=fixture_environment(),
        capture_output=True,
        timeout=None,
        check=False,
        # A hidden console of the fixture's own keeps the probe off the test runner's console.
        creationflags=WINDOWS_CREATE_NO_WINDOW,
    )
    assert completed.returncode == 0, completed.stderr.decode(errors="replace")[-4000:]
    loaded: object = json.loads(completed.stdout)
    assert isinstance(loaded, dict)
    return {str(key): value for key, value in loaded.items()}


@pytest.mark.parametrize(("mode", "shares_console"), [("shared", True), ("isolated", False)])
def test_only_an_isolating_process_gives_the_kdf_worker_its_own_console(
    tmp_path: Path, mode: str, shares_console: bool
) -> None:
    members = _console_members(mode, tmp_path)
    console = members["console"]
    assert isinstance(console, list)
    # The probe reads a real console: the fixture itself is always listed.
    assert members["fixture"] in console
    assert (members["worker"] in console) is shares_console
