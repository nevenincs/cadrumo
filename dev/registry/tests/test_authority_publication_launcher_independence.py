"""Every publishing path records the same logical generation for the same sources.

The candidate compiles in one canonical child interpreter, so modules a heavier
launcher has already imported cannot enter the recorded compiler closure. Both
publications compile and validate the bundled registry for real, which is why
this is an integration test.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
import time
from pathlib import Path
from types import ModuleType

import pytest
from typer.testing import CliRunner

from cadrumo.domain.calculations.registry.authority_compiler_closure import AuthorityCompilerClosure
from cadrumo.domain.calculations.registry.authority_store import AuthorityDescriptor, SQLiteAuthorityReader
from dev._paths import REPO_ROOT

from ..pipeline.cli import app as pipeline_app

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.timeout(3600)]

_LAUNCHER_ONLY_MODULES = (
    "cadrumo.application.operator_actions.catalogue",
    "dev.registry.analysis.registry_status",
    "dev.registry.registry_collapse_verification",
)


def _hook_module() -> ModuleType:
    path = REPO_ROOT / "packaging" / "authority" / "hatch_build.py"
    spec = importlib.util.spec_from_file_location("cadrumo_authority_hatch_build_launcher_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _published(destination: Path) -> tuple[AuthorityDescriptor, AuthorityCompilerClosure]:
    descriptor_path = destination / "authority.current.json"
    reader = SQLiteAuthorityReader(descriptor_path)
    try:
        closure = reader.compiler_closure()
    finally:
        reader.close()
    return AuthorityDescriptor.read(descriptor_path), closure


def _portable_source(module_name: str) -> str:
    location = sys.modules[module_name].__file__
    assert location is not None
    path = Path(location).resolve()
    source_root = REPO_ROOT / "src"
    anchor = source_root if path.is_relative_to(source_root) else REPO_ROOT
    return path.relative_to(anchor).as_posix()


def test_the_cli_and_the_build_hook_publish_one_generation_whatever_the_launcher_imported(tmp_path: Path) -> None:
    hook_destination = tmp_path / "hook"
    cli_destination = tmp_path / "cli"

    started = time.monotonic()
    _hook_module()._publish_source_tree_authority(REPO_ROOT, hook_destination)
    hook_seconds = time.monotonic() - started

    loaded_before = set(sys.modules)
    for module_name in _LAUNCHER_ONLY_MODULES:
        importlib.import_module(module_name)
    launcher_only = {
        name for name in set(sys.modules) - loaded_before if name.startswith(("cadrumo.", "dev.registry."))
    }
    assert launcher_only, "the heavier launcher must have loaded compiler-root modules the first one had not"

    started = time.monotonic()
    result = CliRunner().invoke(pipeline_app, ["publish-authority", "--destination", str(cli_destination)])
    cli_seconds = time.monotonic() - started
    assert result.exit_code == 0, result.output
    print(f"publication wall time: hook {hook_seconds:.0f}s, cli {cli_seconds:.0f}s")

    hook_descriptor, hook_closure = _published(hook_destination)
    cli_descriptor, cli_closure = _published(cli_destination)
    assert cli_descriptor.logical_generation == hook_descriptor.logical_generation
    assert cli_closure == hook_closure
    recorded = {path for path, _digest in cli_closure.sources}
    assert "dev/registry/pipeline/compile_authority_candidate.py" in recorded
    assert not {_portable_source(name) for name in _LAUNCHER_ONLY_MODULES} & recorded
