"""Real registry construction tolerates unavailable migration execution modules."""

from __future__ import annotations

from pathlib import Path

import pytest

from .isolated_registry_probe_support import run_isolated_registry_probe

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_production_registry_defers_calculation_migration_implementation(tmp_path: Path) -> None:
    probe = """
import faulthandler
import importlib.abc
import json
import os
import sys

print(json.dumps({'pid': os.getpid(), 'interpreter': sys.executable}), flush=True)
faulthandler.dump_traceback_later(25)
sys.path[:0] = [sys.argv[1], *json.loads(sys.argv[2])]
blocked = {
    'cadrumo.adapters.persistence.profile.calculation_revision_override_migration',
    'cadrumo.adapters.persistence.profile.relation_binding_join',
}

class UnavailableMigration(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname in blocked:
            raise ModuleNotFoundError('fixture: migration implementation unavailable', name=fullname)

def refuse_effects(event, args):
    if event in {
        'socket.connect', 'socket.bind', 'subprocess.Popen', 'os.system',
        'os.exec', 'os.fork', 'os.forkpty', 'os.posix_spawn', 'os.spawn',
    }:
        raise AssertionError('registry construction attempted an active effect')

sys.addaudithook(refuse_effects)
sys.meta_path.insert(0, UnavailableMigration())
from cadrumo.core.config import Settings
from cadrumo.entrypoints.operation_composition import build_production_operation_registry
from cadrumo.adapters.persistence.profile.guarded_calculation_revision_migration import GuardedCalculationRevisionMigration

registry = build_production_operation_registry(settings=Settings(_env_file=None))
assert registry.public_contract_set.definitions
assert registry.public_contract_set.contract_set_digest
assert GuardedCalculationRevisionMigration.__module__ == 'cadrumo.adapters.persistence.profile.guarded_calculation_revision_migration'
assert not blocked.intersection(sys.modules)
faulthandler.cancel_dump_traceback_later()
"""
    run_isolated_registry_probe(tmp_path, probe)
