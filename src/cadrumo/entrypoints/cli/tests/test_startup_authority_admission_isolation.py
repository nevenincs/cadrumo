"""Fresh CLI startup admits authority without loading its execution graph.

The CLI's startup admission runs before any command is parsed. Its whole import
closure, including the typed error boundary around the application admission,
must leave authority execution modules unloaded and storage uncreated.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from ....domain.calculations.registry.authority_location import bundled_authority_descriptor_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_fresh_cli_admission_and_gate_construction_exclude_authority_execution_dependencies(tmp_path: Path) -> None:
    """Exercise the real CLI admission owner while the execution modules are unavailable."""
    source = Path(__file__).resolve().parents[4]
    authority = bundled_authority_descriptor_path().parent
    script = """
import importlib.abc
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
blocked = {
    'cadrumo.domain.calculations.registry.authority',
    'cadrumo.domain.calculations.registry.authority_component_codec',
    'cadrumo.domain.calculations.registry.schema',
    'cadrumo.domain.calculations.registry.governed_fact_scope',
    'cadrumo.domain.calculations.registry.nif_iva_catalogue',
    'cadrumo.domain.calculations.registry.tax_id_format',
}

class MissingExecutionDependencies(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname in blocked:
            raise ModuleNotFoundError('fixture: authority execution dependency unavailable', name=fullname)

def refuse_actions(event, args):
    if event in {'socket.connect', 'socket.bind', 'subprocess.Popen', 'os.system'}:
        raise AssertionError('admission-only fixture attempted an active effect')

sys.addaudithook(refuse_actions)
sys.meta_path.insert(0, MissingExecutionDependencies())
from cadrumo.entrypoints.cli.main import _admit_authority_at_startup
from cadrumo.domain.calculations.registry.authority_location import published_authority_generation
from cadrumo.domain.calculations.registry.tax_identity_admission import RegistryTaxIdentityAdmission

_admit_authority_at_startup()
assert published_authority_generation() is not None
admission = RegistryTaxIdentityAdmission()
for candidate in ('SIGN', 'CODE', 'XI', ''):
    assert admission.admits_nif_iva(candidate) is False
assert blocked.isdisjoint(sys.modules), blocked.intersection(sys.modules)
assert not Path(sys.argv[2]).exists()
"""
    allowed = {"SYSTEMROOT", "WINDIR", "SYSTEMDRIVE", "PATH", "COMSPEC"}
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
    result = subprocess.run(  # noqa: S603 - fixed interpreter and finite repository-owned admission fixture
        [sys.executable, "-I", "-B", "-c", script, str(source), str(tmp_path / "storage")],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=None,
        check=False,
    )
    assert result.returncode == 0, result.stderr
