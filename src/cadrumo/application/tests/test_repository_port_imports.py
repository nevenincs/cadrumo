"""Composing repository ports does not require financial execution models."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_fresh_repository_port_imports_tolerate_unavailable_domain_models(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[3]
    script = """
import importlib
import importlib.abc
import sys

sys.path.insert(0, sys.argv[1])

class MissingFinancialExecution(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname.startswith('cadrumo.domain.') or fullname in {
            'cadrumo.application.ledger.confirmation_record',
            'cadrumo.application.ledger.extraction_draft_store',
        }:
            raise ModuleNotFoundError('fixture: domain execution model unavailable', name=fullname)

def refuse_actions(event, args):
    if event in {'socket.connect', 'socket.bind', 'subprocess.Popen', 'os.system'}:
        raise AssertionError('repository port import attempted an active effect')

sys.addaudithook(refuse_actions)
sys.meta_path.insert(0, MissingFinancialExecution())
for module in (
    'ledger.confirmation_record_repository',
    'ledger.extraction_draft_repository',
    'ledger.participation_read',
    'ledger.rule_repository',
    'ledger.transaction_repository',
    'ledger.usage_ratio_repository',
    'modelo.calculation_repository',
    'modelo.filing_repository',
    'modelo.justificante_repository',
    'modelo.work_unit_repository',
):
    importlib.import_module('cadrumo.application.' + module)
assert not any(name.startswith('cadrumo.domain.') for name in sys.modules)
"""
    allowed = {"SYSTEMROOT", "WINDIR", "SYSTEMDRIVE", "PATH", "COMSPEC"}
    environment = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    environment.update(
        {
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
    result = subprocess.run(  # noqa: S603 - fixed interpreter and finite import fixture
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
