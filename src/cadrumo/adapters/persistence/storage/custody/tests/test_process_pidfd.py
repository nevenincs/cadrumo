from __future__ import annotations

import os
import select
import subprocess
import sys

import pytest

from ..process_pidfd import open_process_pidfd

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hex_persistence_adapter,
    pytest.mark.skipif(sys.platform != "linux", reason="Linux process descriptors are a Linux kernel contract"),
]


@pytest.fixture(params=["interpreter", "kernel call"])
def interpreter_pidfd(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> str:
    """Run each case with and without ``os.pidfd_open``, as builds such as uv's CPython 3.13 lack it."""
    if request.param == "kernel call":
        monkeypatch.delattr(os, "pidfd_open", raising=False)
    elif not hasattr(os, "pidfd_open"):
        pytest.skip("this interpreter has no os.pidfd_open; the kernel-call case covers it")
    return str(request.param)


def test_a_process_descriptor_becomes_readable_only_when_its_process_ends(interpreter_pidfd: str) -> None:
    child = subprocess.Popen([sys.executable, "-c", "import sys; sys.stdin.read()"], stdin=subprocess.PIPE)
    descriptor = open_process_pidfd(child.pid)
    try:
        assert not os.get_inheritable(descriptor), interpreter_pidfd
        assert select.select([descriptor], [], [], 0.2)[0] == [], "readable while the process still runs"
        assert child.stdin is not None
        child.stdin.close()
        assert select.select([descriptor], [], [], 10)[0] == [descriptor], "not readable after the process ended"
    finally:
        os.close(descriptor)
        child.wait(timeout=10)


def test_a_process_that_no_longer_exists_is_refused_as_absent(interpreter_pidfd: str) -> None:
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait(timeout=10)
    with pytest.raises(ProcessLookupError):
        open_process_pidfd(child.pid)
