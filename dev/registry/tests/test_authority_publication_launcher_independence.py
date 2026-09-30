"""Every publishing path records the legal identity of the sources it published.

The build hook and the ``publish-authority`` command each compile the bundled
registry in the canonical child interpreter. Whatever either launcher had
imported, both record the one identity the legal sources derive. Both
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

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority_store import AuthorityDescriptor
from dev._paths import REPO_ROOT

from ..pipeline.authority_publication import authority_source_identity
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


def test_the_cli_and_the_build_hook_publish_the_legal_identity_whatever_the_launcher_imported(
    tmp_path: Path,
) -> None:
    hook_destination = tmp_path / "hook"
    cli_destination = tmp_path / "cli"

    started = time.monotonic()
    _hook_module()._publish_source_tree_authority(REPO_ROOT, hook_destination)
    hook_seconds = time.monotonic() - started

    for module_name in _LAUNCHER_ONLY_MODULES:
        importlib.import_module(module_name)
    assert all(module_name in sys.modules for module_name in _LAUNCHER_ONLY_MODULES), (
        "the heavier launcher must hold the launcher-only modules"
    )

    started = time.monotonic()
    result = CliRunner().invoke(pipeline_app, ["publish-authority", "--destination", str(cli_destination)])
    cli_seconds = time.monotonic() - started
    assert result.exit_code == 0, result.output
    print(f"publication wall time: hook {hook_seconds:.0f}s, cli {cli_seconds:.0f}s")

    legal_identity = authority_source_identity(
        registry_root=bundled_path("registry", "aeat"),
        source_root=bundled_path(),
    )
    hook_descriptor = AuthorityDescriptor.read(hook_destination / "authority.current.json")
    cli_descriptor = AuthorityDescriptor.read(cli_destination / "authority.current.json")
    assert hook_descriptor.logical_generation == legal_identity
    assert cli_descriptor.logical_generation == legal_identity
