"""A worker target owner does not load the operation transport to name its type."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest

from cadrumo.core.storage_environment import STORAGE_ROOT
from cadrumo.tests.audited_process import run_audited_process

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_CHILD: Final = """
import importlib.abc, json, sys

protocol = 'cadrumo.application.runtime.profile_worker'
class RefuseProtocol(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == protocol:
            raise RuntimeError('unneeded_worker_protocol_import')
        return None

sys.meta_path.insert(0, RefuseProtocol())
from cadrumo.adapters.persistence.storage.master_key.profile_worker_binding import ProfileWorkerBindingOwner
owner = ProfileWorkerBindingOwner()
owner.require_session(None)
print(json.dumps({'protocolLoaded': protocol in sys.modules}))
"""


def test_binding_owner_import_does_not_require_the_worker_protocol(tmp_path: Path) -> None:
    environment = {**os.environ, STORAGE_ROOT.variable: str(tmp_path)}
    startupinfo = None
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
    completed = run_audited_process(
        [sys.executable, "-I", "-B", "-c", _CHILD],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        startupinfo=startupinfo,
    )
    assert completed.returncode == 0, "binding import required the worker protocol"
    assert isinstance(completed.stdout, str)
    assert json.loads(completed.stdout) == {"protocolLoaded": False}
