"""Every publishing path records the same logical generation for the same sources.

The candidate compiles in one canonical child interpreter, so modules a heavier
launcher has already imported cannot enter the recorded compiler closure. Both
publications compile and validate the bundled registry for real, which is why
this is an integration test.

The light launcher is a fresh interpreter rather than this test process. A test
process has already imported whatever the tests before it in the same worker
imported, so a comparison anchored to its ``sys.modules`` held only when this
test happened to run early, and refused otherwise.
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

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


def _publish_from_a_light_launcher(destination: Path) -> list[str]:
    """Publish through the build hook in a clean interpreter; return the watched modules it loaded."""
    environment = {
        **os.environ,
        "LAUNCHER_TEST_REPOSITORY": str(REPO_ROOT),
        "LAUNCHER_TEST_DESTINATION": str(destination),
        "LAUNCHER_TEST_WATCHED": json.dumps(_LAUNCHER_ONLY_MODULES),
    }
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import importlib.util, json, os, sys\n"
            "from pathlib import Path\n"
            "repository = Path(os.environ['LAUNCHER_TEST_REPOSITORY'])\n"
            "spec = importlib.util.spec_from_file_location(\n"
            "    'cadrumo_authority_hatch_build_launcher_test',\n"
            "    repository / 'packaging' / 'authority' / 'hatch_build.py',\n"
            ")\n"
            "module = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(module)\n"
            "module._publish_source_tree_authority(repository, Path(os.environ['LAUNCHER_TEST_DESTINATION']))\n"
            "watched = json.loads(os.environ['LAUNCHER_TEST_WATCHED'])\n"
            "print(json.dumps(sorted(name for name in watched if name in sys.modules)))\n",
        ],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    loaded = json.loads(completed.stdout.strip().splitlines()[-1])
    assert isinstance(loaded, list) and all(isinstance(name, str) for name in loaded), loaded
    return [str(name) for name in loaded]


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
    light_loaded = _publish_from_a_light_launcher(hook_destination)
    hook_seconds = time.monotonic() - started
    assert light_loaded == [], f"the light launcher must not hold the heavier launcher's modules: {light_loaded}"

    for module_name in _LAUNCHER_ONLY_MODULES:
        importlib.import_module(module_name)
    assert all(name in sys.modules for name in _LAUNCHER_ONLY_MODULES)

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
