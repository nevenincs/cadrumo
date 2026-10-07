"""An ordinary runtime client does not hydrate tax or profile-view models."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest

from ....core.storage_environment import STORAGE_ROOT
from ....tests.audited_process import run_audited_process

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_CHILD: Final = """
import importlib.abc, json, sys

excluded = {
    'cadrumo.domain.calculations.registry.authority',
    'cadrumo.application.user_profile.view_operation',
}
class RefuseUnusedModels(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in excluded:
            raise RuntimeError('unneeded_client_model_import')
        return None

def refuse_actions(event, args):
    if event in {'socket.connect', 'socket.bind', 'subprocess.Popen', 'os.system'}:
        raise RuntimeError('import_action_refused')

sys.meta_path.insert(0, RefuseUnusedModels())
sys.addaudithook(refuse_actions)
from cadrumo.adapters.local_runtime import runtime_client
print(json.dumps({'excludedLoaded': sorted(excluded.intersection(sys.modules))}))
"""


def test_runtime_client_import_does_not_require_tax_authority_or_profile_view_models(tmp_path: Path) -> None:
    environment = {**os.environ, STORAGE_ROOT.variable: str(tmp_path), "PYDANTIC_DISABLE_PLUGINS": "__all__"}
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
    assert completed.returncode == 0, "runtime client imported unused tax or view models"
    assert isinstance(completed.stdout, str)
    assert json.loads(completed.stdout) == {"excludedLoaded": []}
