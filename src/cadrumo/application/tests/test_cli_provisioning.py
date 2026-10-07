"""CLI startup reads published authority without loading its execution graph."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest

from ...core.config import override_settings
from ...domain.calculations.registry.authority_location import (
    bundled_authority_descriptor_path,
    published_authority_generation,
)
from ...domain.calculations.registry.authority_store import AuthorityDescriptor, AuthorityStoreError
from ...domain.calculations.registry.errors import AuthorityDescriptorUnavailableError
from ..cli_provisioning import admit_cli_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_normal_authority_admission_retains_generation_and_log_fact_without_creating_storage(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    descriptor_path = bundled_authority_descriptor_path()
    descriptor = AuthorityDescriptor.read(descriptor_path)
    storage = tmp_path / "storage"
    caplog.set_level(logging.DEBUG, logger="cadrumo.application.cli_provisioning")

    with override_settings(cadrumo_authority_root=descriptor_path.parent, cadrumo_local_storage_root=storage):
        admit_cli_authority()
        assert published_authority_generation() == descriptor.logical_generation

    assert "CLI authority admitted" in caplog.messages
    assert not storage.exists()


@pytest.mark.parametrize("payload", [b"{}", b'{"format":"unexpected"}', b"not JSON"])
def test_malformed_authority_remains_a_refusal_without_materializing_storage(tmp_path: Path, payload: bytes) -> None:
    authority = tmp_path / "authority"
    authority.mkdir()
    (authority / "authority.current.json").write_bytes(payload)
    storage = tmp_path / "storage"

    with override_settings(cadrumo_authority_root=authority, cadrumo_local_storage_root=storage):
        with pytest.raises(AuthorityStoreError):
            admit_cli_authority()
        assert published_authority_generation() is None

    assert not storage.exists()


def test_absent_authority_is_not_provisioned_or_replaced_by_packaged_authority(tmp_path: Path) -> None:
    authority = tmp_path / "absent-authority"
    storage = tmp_path / "storage"

    with override_settings(cadrumo_authority_root=authority, cadrumo_local_storage_root=storage):
        with pytest.raises(AuthorityDescriptorUnavailableError) as refusal:
            admit_cli_authority()
        assert published_authority_generation() is None

    assert refusal.value.authority_root_configured is True
    assert refusal.value.searched_path == authority / "authority.current.json"
    assert not authority.exists()
    assert not storage.exists()


def test_fresh_cli_admission_and_gate_construction_exclude_authority_execution_dependencies(tmp_path: Path) -> None:
    """Exercise the real CLI admission owner while the execution modules are unavailable."""
    source = Path(__file__).resolve().parents[3]
    authority = bundled_authority_descriptor_path().parent
    script = """
import importlib.abc
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
blocked = {
    'cadrumo.application.provisioning',
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
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
