"""Process-level proof that final shutdown cannot outlive its native bound."""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path
from threading import Event

import pytest

from cadrumo.adapters.local_runtime.tests.process_support import fixture_arguments, fixture_environment, native_python
from cadrumo.adapters.local_runtime.windows_process import WindowsProcessScope
from cadrumo.entrypoints.runtime.shutdown import RuntimeShutdownWatchdog

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows process containment"),
]

_FIXTURE = "cadrumo.entrypoints.runtime.tests.shutdown_watchdog_fixture"


@pytest.mark.parametrize("mode,exit_code,cleanup", [("blocked", 2, False), ("healthy", 0, True)])
def test_shutdown_watchdog_ends_owner_and_its_contained_child(
    tmp_path: Path, mode: str, exit_code: int, cleanup: bool
) -> None:
    import win32api
    import win32event

    outer = WindowsProcessScope()
    handles: list[int] = []
    try:
        fixture = outer.launch(
            executable=native_python(),
            arguments=fixture_arguments(_FIXTURE, str(tmp_path), mode),
            directory=tmp_path,
            environment=fixture_environment(),
        )
        ready_path = tmp_path / "child-ready.json"
        deadline = time.monotonic() + 8
        while not ready_path.exists():
            assert time.monotonic() < deadline, "fixture did not publish child readiness"
            time.sleep(0.01)
        ready = json.loads(ready_path.read_text(encoding="ascii"))
        assert ready["parent"] == fixture.pid
        child_handle = win32api.OpenProcess(0x100000, False, ready["child"])
        handles.append(child_handle)
        assert win32event.WaitForSingleObject(child_handle, 0) == win32event.WAIT_TIMEOUT
        (tmp_path / "begin-shutdown").write_text("go", encoding="ascii")

        assert fixture.wait(timeout=5) == exit_code
        assert win32event.WaitForSingleObject(child_handle, 2000) == win32event.WAIT_OBJECT_0
        assert (tmp_path / "cleanup-complete").exists() is cleanup
    finally:
        outer.terminate()
        for handle in handles:
            win32api.CloseHandle(handle)


@pytest.mark.parametrize("timeout", [0.0, -1.0, math.inf, math.nan])
def test_shutdown_watchdog_requires_a_finite_positive_budget(timeout: float) -> None:
    with pytest.raises(ValueError, match="finite and positive"):
        RuntimeShutdownWatchdog(Event(), timeout=timeout)
