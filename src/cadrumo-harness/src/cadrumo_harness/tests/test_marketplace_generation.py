"""Tests for the marketplace materialiser.

Asserts the marketplace layout emits, in one call, the
``.claude-plugin/marketplace.json`` manifest and the plugin tree its
``plugins[].source`` points at, so the marketplace and the plugin it serves
cannot drift: the served plugin is byte-identical to a standalone
``materialise_plugin`` emission, and the checked-in scaffold under
``packaging/marketplace`` stays in lock-step with the generator's manifest.
Where the ``claude`` CLI is on PATH the emitted marketplace additionally passes
``claude plugin validate --strict``; the structural assertions always run.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from cadrumo.core.directory_scan import DirectoryEntryKind, scan_directory

from .._workspace import _PluginPythonCohort, materialise_marketplace, materialise_plugin

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_UTF_8 = "utf-8"

_REPO_ROOT = Path(__file__).resolve().parents[5]
_SCAFFOLD_MANIFEST = _REPO_ROOT / "packaging" / "marketplace" / ".claude-plugin" / "marketplace.json"
_SCAFFOLD_SUPERSEDES = _REPO_ROOT / "packaging" / "marketplace" / ".claude-plugin" / "supersedes.json"


def test_marketplace_manifest_is_schema_shaped_and_resolves_to_the_plugin(
    tmp_path: Path, plugin_cohort: _PluginPythonCohort
) -> None:
    output = tmp_path / "marketplace"
    manifest = materialise_marketplace(output, cohort=plugin_cohort)
    assert manifest.marketplace_name == "neve"

    document = json.loads((output / ".claude-plugin" / "marketplace.json").read_text(encoding=_UTF_8))
    assert document["name"] == "neve"
    assert document["owner"] == {"name": "CADRUMO tax assistant project"}
    # Bilingual marketplace description (EN + ES).
    description = document["description"]
    assert description.startswith("English: Neve plugin marketplace - Claude plugins")
    assert "\nEspañol: " in description
    assert "it never files" in description.lower()
    (entry,) = document["plugins"]
    assert entry["name"] == "cadrumo"
    assert entry["source"] == manifest.plugin_source == "./plugins/cadrumo"
    assert entry["source"] != "./plugins/aeat"

    # The relative source resolves, from the marketplace root, to the plugin
    # tree materialised in the same call.
    served = output / "plugins" / "cadrumo"
    assert (served / ".claude-plugin" / "plugin.json").is_file()
    assert (served / ".mcp.json").is_file()
    assert not (output / "plugins" / "aeat").exists()
    assert manifest.plugin.skills_written > 0
    assert manifest.plugin.agents_written > 0


def test_served_plugin_equals_the_standalone_plugin_emission(
    tmp_path: Path, plugin_cohort: _PluginPythonCohort
) -> None:
    """No drift by construction: the served plugin is the standalone emission."""
    marketplace_dir = tmp_path / "marketplace"
    standalone_dir = tmp_path / "standalone"
    materialise_marketplace(marketplace_dir, cohort=plugin_cohort)
    materialise_plugin(standalone_dir, cohort=plugin_cohort)

    served_root = marketplace_dir / "plugins" / "cadrumo"
    served = {
        p.relative_to(served_root).as_posix(): p
        for p in scan_directory(served_root, recursive=True, select=DirectoryEntryKind.FILES)
    }
    standalone = {
        p.relative_to(standalone_dir).as_posix(): p
        for p in scan_directory(standalone_dir, recursive=True, select=DirectoryEntryKind.FILES)
    }
    assert served.keys() == standalone.keys()
    for relative, served_path in served.items():
        assert served_path.read_bytes() == standalone[relative].read_bytes(), relative


def test_checked_in_marketplace_scaffold_matches_the_generator(
    tmp_path: Path, plugin_cohort: _PluginPythonCohort
) -> None:
    """The ``packaging/marketplace`` scaffold cannot drift from the generator."""
    output = tmp_path / "marketplace"
    materialise_marketplace(output, cohort=plugin_cohort)
    generated = json.loads((output / ".claude-plugin" / "marketplace.json").read_text(encoding=_UTF_8))
    scaffold = json.loads(_SCAFFOLD_MANIFEST.read_text(encoding=_UTF_8))
    assert scaffold == generated


def test_the_supersedes_sidecar_is_emitted_and_matches_the_scaffold(
    tmp_path: Path, plugin_cohort: _PluginPythonCohort
) -> None:
    """The retirement declaration ships beside the manifest, and cannot drift either.

    Covering the sidecar explicitly, because the manifest comparison above cannot
    see it: with the sidecar emission removed the manifests still match exactly,
    so that assertion stays green while the retirement silently stops shipping.

    It lives beside the manifest rather than inside it because the strict plugin
    validator rejects an unknown manifest field, which the sibling validator test
    would catch; asserting its absence here states the constraint where a reader
    tempted to inline it will look.
    """
    output = tmp_path / "marketplace"
    materialise_marketplace(output, cohort=plugin_cohort)
    emitted = output / ".claude-plugin" / "supersedes.json"
    assert emitted.is_file(), "the retirement declaration must ship with every cohort"

    generated = json.loads(emitted.read_text(encoding=_UTF_8))
    assert generated == {"supersedes": ["aeat"]}
    scaffold = json.loads(_SCAFFOLD_SUPERSEDES.read_text(encoding=_UTF_8))
    assert scaffold == generated

    manifest = json.loads((output / ".claude-plugin" / "marketplace.json").read_text(encoding=_UTF_8))
    assert "supersedes" not in manifest


def test_emitted_marketplace_passes_claude_validate_strict_when_cli_present(
    tmp_path: Path, plugin_cohort: _PluginPythonCohort
) -> None:
    """The emitted marketplace is schema-valid; where ``claude`` exists, prove it strict.

    The structural materialisation and its assertions always run; the live
    validator is an ADDITIONAL gate, never a substitute, so a missing CLI
    degrades to "structure checked" rather than a silent skip.
    """
    output = tmp_path / "marketplace"
    manifest = materialise_marketplace(output, cohort=plugin_cohort)
    assert (output / ".claude-plugin" / "marketplace.json").is_file()
    assert (output / "plugins" / "cadrumo" / ".claude-plugin" / "plugin.json").is_file()
    assert manifest.plugin.skills_written > 0

    claude = shutil.which("claude")
    if claude is not None:
        completed = subprocess.run(  # noqa: S603 - claude resolved from PATH, fixed args
            [claude, "plugin", "validate", "--strict", str(output)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, (
            f"claude plugin validate --strict failed:\n{completed.stdout}\n{completed.stderr}"
        )
