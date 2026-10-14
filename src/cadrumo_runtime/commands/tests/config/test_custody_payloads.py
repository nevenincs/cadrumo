"""Runtime custody result ownership and unselected sign-in status remain light."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.authority_location import bundled_authority_descriptor_path
from cadrumo_runtime.commands.command_specs import RUNTIME_COMMAND_GRAPH

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_fresh_unselected_runtime_status_excludes_authority_execution_and_profile_health(tmp_path: Path) -> None:
    spec = RUNTIME_COMMAND_GRAPH.by_schema_identity()["config.sign-in-status"]
    target = spec.result_schema.target
    assert target is not None
    assert target.identity == "cadrumo_client.commands.custody_payloads:ConfigSignInStatusResult"
    source = Path(__file__).resolve().parents[4]
    authority = bundled_authority_descriptor_path().parent
    script = """
import importlib.abc
import json
import sys
from contextlib import redirect_stdout
from io import StringIO

sys.path.insert(0, sys.argv[1])
blocked = {
    'cadrumo_client.transport.installed_client',
    'cadrumo_client.transport.frontend_client',
    'cadrumo.application.provisioning',
    'cadrumo.application.workflow.profile_health',
    'cadrumo.application.workflow.run_models',
    'cadrumo.domain.calculations.registry.authority',
    'cadrumo.domain.calculations.registry.authority_component_codec',
    'cadrumo.domain.calculations.registry.schema',
    'cadrumo.domain.calculations.registry.governed_fact_scope',
    'cadrumo.domain.calculations.registry.nif_iva_catalogue',
    'cadrumo.domain.calculations.registry.tax_id_format',
    'cadrumo.domain.user_profile.setup_answers',
    'cadrumo_client.commands.payloads',
}

class MissingExecutionDependencies(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname in blocked:
            raise ModuleNotFoundError('fixture: execution dependency unavailable', name=fullname)

def refuse_actions(event, args):
    if event in {'socket.connect', 'socket.bind', 'subprocess.Popen', 'os.system'}:
        raise AssertionError('unselected status attempted an active effect')

sys.addaudithook(refuse_actions)
sys.meta_path.insert(0, MissingExecutionDependencies())
from cadrumo_runtime.commands import main as runtime_main

def expose_unexpected_failure(error, arguments, *, click_context=None):
    original = getattr(error, 'original_exception', None)
    if isinstance(original, BaseException):
        raise original
    raise error

# This isolated child asserts a successful cold execution. Preserve the exact
# exception on failure instead of reducing missing dependencies to an envelope.
runtime_main._emit_error = expose_unexpected_failure

output = StringIO()
with redirect_stdout(output):
    assert runtime_main.main(['--format', 'json', 'config', 'sign-in-status']) == 0

result = json.loads(output.getvalue())
assert result['command'] == 'config.sign-in-status'
assert result['result']['profile_id'] is None
assert result['result']['status']['presence'] == 'absent'
assert blocked.isdisjoint(sys.modules), blocked.intersection(sys.modules)
"""
    allowed = {"SYSTEMROOT", "WINDIR", "SYSTEMDRIVE", "PATH", "COMSPEC", "USERNAME", "USERDOMAIN"}
    environment = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    environment.update(
        {
            "CADRUMO_AUTHORITY_ROOT": str(authority),
            "CADRUMO_LOCAL_STORAGE_ROOT": str(tmp_path / "storage"),
            "CADRUMO_STORAGE_ROOT": str(tmp_path / "storage"),
            "PYDANTIC_DISABLE_PLUGINS": "__all__",
            "TEMP": str(tmp_path),
            "TMP": str(tmp_path),
            "USERPROFILE": str(tmp_path),
            "APPDATA": str(tmp_path),
            "LOCALAPPDATA": str(tmp_path),
        }
    )
    result = subprocess.run(  # noqa: S603 - fixed interpreter and finite empty-root CLI fixture
        [sys.executable, "-I", "-B", "-c", script, str(source)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=None,
        check=False,
    )
    assert result.returncode == 0, result.stderr
