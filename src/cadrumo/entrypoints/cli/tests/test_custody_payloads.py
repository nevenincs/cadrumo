"""Custody result contracts resolve without loading profile health or authority execution."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from ....core.json_contract import OutputSchema
from ....domain.calculations.registry.authority_location import bundled_authority_descriptor_path
from ..command_schema import command_schema_type
from ..config.custody_payloads import ConfigLoginResult, ConfigLogoutResult, ConfigSignInStatusResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize(
    ("identity", "schema"),
    [
        ("config.login", ConfigLoginResult),
        ("config.sign-in-status", ConfigSignInStatusResult),
        ("config.logout", ConfigLogoutResult),
    ],
)
def test_custody_graph_resolves_the_canonical_result_owner(identity: str, schema: type[OutputSchema]) -> None:
    assert command_schema_type(identity) is schema
    assert schema.__module__ == "cadrumo.entrypoints.cli.config.custody_payloads"


def test_fresh_unselected_cli_status_excludes_authority_execution_and_profile_health(tmp_path: Path) -> None:
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
    'cadrumo.entrypoints.cli.config_payloads',
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
from cadrumo.entrypoints.cli.main import main

sys.argv = ['aeat', '--format', 'json', 'config', 'sign-in-status']
output = StringIO()
with redirect_stdout(output):
    try:
        main()
    except SystemExit as exit_request:
        assert exit_request.code == 0, exit_request.code

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
