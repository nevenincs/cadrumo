"""A desktop holder must not trace back to the runtime that admits it."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from ...adapters.service_verification import native_process_identity
from ..desktop_holder_identity import descends_from_this_runtime

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_inbound_adapter,
    pytest.mark.skipif(sys.platform not in ("win32", "linux"), reason="reads native process ancestry"),
]


def _owner() -> str:
    if sys.platform == "win32":
        import ctypes

        from cadrumo_client.transport.windows_native_io import windows_owner_sid

        return windows_owner_sid(ctypes.windll.kernel32.GetCurrentProcess())
    return str(os.getuid())


def test_the_runtime_and_the_processes_it_starts_descend_from_it() -> None:
    owner = _owner()
    assert descends_from_this_runtime(native_process_identity(os.getpid(), owner), owner)
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        assert descends_from_this_runtime(native_process_identity(child.pid, owner), owner)
    finally:
        child.kill()
        child.wait()


def test_the_process_that_started_the_runtime_does_not_descend_from_it() -> None:
    owner = _owner()
    parent = native_process_identity(native_process_identity(os.getpid(), owner).parent_pid, owner)
    assert not descends_from_this_runtime(parent, owner)
