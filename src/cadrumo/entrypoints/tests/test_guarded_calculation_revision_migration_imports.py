"""Real registry construction tolerates unavailable migration execution modules."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import sysconfig
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_production_registry_defers_calculation_migration_implementation(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[3]
    base_executable = getattr(sys, "_base_executable", None)
    assert isinstance(base_executable, str)
    interpreter = Path(base_executable).resolve(strict=True)
    package_paths = sorted({sysconfig.get_path("purelib"), sysconfig.get_path("platlib")})
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
    allowed = {"SYSTEMROOT", "WINDIR", "SYSTEMDRIVE", "PATH", "COMSPEC", "USERNAME", "USERDOMAIN"}
    environment = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    environment.update(
        {
            "CADRUMO_AUTHORITY_ROOT": os.environ["CADRUMO_AUTHORITY_ROOT"],
            "CADRUMO_LOCAL_STORAGE_ROOT": str(tmp_path / "storage"),
            "CADRUMO_STORAGE_ROOT": str(tmp_path / "storage"),
            "PYDANTIC_DISABLE_PLUGINS": "__all__",
            "TEMP": str(tmp_path),
            "TMP": str(tmp_path),
            "HOME": str(tmp_path),
            "USERPROFILE": str(tmp_path),
            "APPDATA": str(tmp_path),
            "LOCALAPPDATA": str(tmp_path),
        }
    )
    stdout_path = tmp_path / "registry-probe.stdout"
    stderr_path = tmp_path / "registry-probe.stderr"
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
        process = subprocess.Popen(  # noqa: S603 - resolved base interpreter, fixed import-only probe, owned child
            [str(interpreter), "-I", "-S", "-B", "-c", probe, str(source), json.dumps(package_paths)],
            cwd=tmp_path,
            env=environment,
            stdout=stdout,
            stderr=stderr,
        )
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired as error:
            error.add_note(f"Owned child PID: {process.pid}")
            error.add_note(stdout_path.read_text(encoding="utf-8"))
            error.add_note(stderr_path.read_text(encoding="utf-8"))
            raise
        finally:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
    assert process.returncode == 0, stderr_path.read_text(encoding="utf-8")
    observation = json.loads(stdout_path.read_text(encoding="utf-8"))
    assert observation["pid"] == process.pid
    assert Path(observation["interpreter"]).resolve(strict=True) == interpreter
    assert not (tmp_path / "storage").exists()
