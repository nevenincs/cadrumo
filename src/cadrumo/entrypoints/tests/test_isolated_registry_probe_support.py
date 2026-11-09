"""An isolated registry probe can refuse process launches from its first line, whatever the host's load."""

from __future__ import annotations

from pathlib import Path

import pytest

from .isolated_registry_probe_support import run_isolated_registry_probe

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_a_guarded_probe_reads_the_host_identity_without_launching_a_process(tmp_path: Path) -> None:
    """A failed WMI query sends the first ``uname()`` to a ``cmd`` launch; the probe has its answer before then.

    The probe drops the WMI module the way the stdlib does after a query fails or
    times out, so an identity not yet resolved when the guard goes in is read by
    launching a process, which the guard refuses.
    """
    probe = """
import json
import os
import platform
import sys

print(json.dumps({'pid': os.getpid(), 'interpreter': sys.executable}), flush=True)

def refuse_effects(event, args):
    if event in {'subprocess.Popen', 'os.system', 'os.exec', 'os.posix_spawn', 'os.spawn'}:
        raise AssertionError('the probe launched a process: ' + event)

sys.addaudithook(refuse_effects)
platform._wmi = None
assert isinstance(platform.machine(), str)
"""
    run_isolated_registry_probe(tmp_path, probe)
