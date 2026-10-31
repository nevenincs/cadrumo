"""Every publishing path records the legal identity of the sources it published.

The build hook and the ``publish-authority`` command both compile through the
one publisher, in the canonical child interpreter, so what a launcher had
imported cannot reach the compile. The run's one publication of the committed
sources is that publisher's real output, so it is the proof of the recorded
identity, and this test asserts against it rather than publishing the same
input again.

What stays on the launcher's side is checked here after the heavier launcher's
modules are loaded: the build hook admits the descriptor-selected pair the
publisher wrote, and the command, deriving the live identity in its own process,
finds that pair current and leaves it untouched.
"""

from __future__ import annotations

import importlib
import importlib.util
import shutil
import sys
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority_store import AuthorityDescriptor
from dev._paths import REPO_ROOT

from ..pipeline.authority_publication import authority_source_identity
from ..pipeline.cli import app as pipeline_app

if TYPE_CHECKING:
    from .committed_authority_publication import RunPublishedAuthority

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

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
    committed_published_authority: RunPublishedAuthority,
    tmp_path: Path,
) -> None:
    for module_name in _LAUNCHER_ONLY_MODULES:
        importlib.import_module(module_name)
    assert all(module_name in sys.modules for module_name in _LAUNCHER_ONLY_MODULES), (
        "the heavier launcher must hold the launcher-only modules"
    )
    legal_identity = authority_source_identity(
        registry_root=bundled_path("registry", "aeat"),
        source_root=bundled_path(),
    )
    publication = committed_published_authority
    assert publication.descriptor.logical_generation == legal_identity

    descriptor_path, database = _hook_module()._selected_pair(publication.root)
    assert AuthorityDescriptor.read(descriptor_path) == publication.descriptor
    assert database.name == publication.descriptor.database

    # The command runs against a copy: a stale verdict would publish, and the
    # shared publication is read by every other worker.
    destination = tmp_path / "cli"
    destination.mkdir()
    shutil.copyfile(publication.descriptor_path, destination / publication.descriptor_path.name)
    shutil.copyfile(database, destination / database.name)
    result = CliRunner().invoke(
        pipeline_app,
        ["publish-authority", "--if-stale", "--destination", str(destination)],
    )
    assert result.exit_code == 0, result.output
    assert f"identity_digest={legal_identity}" in result.output
    assert "published=skipped-current" in result.output
    assert AuthorityDescriptor.read(destination / publication.descriptor_path.name) == publication.descriptor
