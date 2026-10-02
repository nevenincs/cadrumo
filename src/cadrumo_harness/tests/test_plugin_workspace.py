"""Tests for the plugin materialiser.

Asserts the plugin layout re-materialises the single authored harness source as
a schema-shaped plugin over a real
filesystem ``tmp_path``: a ``.claude-plugin/plugin.json`` manifest carrying the
required publication fields, a top-level ``skills/`` and ``agents/`` tree, and an
``.mcp.json`` declaring the stdio ``cadrumo-mcp`` server. The agent frontmatter maps
to plugin-native fields and never carries the harness-authoring ``mode:`` field. Where the
``claude`` CLI is on PATH, the emitted tree is additionally asserted to pass
``claude plugin validate --strict``; the structural assertions always run so the
suite never silently degrades to a validator-only skip.
"""

from __future__ import annotations

import inspect
import json
import shutil
import subprocess
import zipfile
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from cadrumo.core.hashing import sha256_hex

from .._workspace import _PluginPythonCohort, materialise_plugin
from ..resources import harness_root, iter_personas
from ._plugin_cohort import PluginTestCohort

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_UTF_8 = "utf-8"


def _shipped_skill_names() -> list[str]:
    skills_root = harness_root().joinpath("skills")
    return sorted(
        child.name for child in skills_root.iterdir() if child.is_dir() and child.joinpath("SKILL.md").is_file()
    )


def _persona_slugs() -> list[str]:
    return sorted(persona.name[:-3] for persona in iter_personas())


def _agent_frontmatter(path: Path) -> dict[str, object]:
    text = path.read_text(encoding=_UTF_8)
    assert text.startswith("---\n"), f"{path.name} has no leading frontmatter"
    _, block, _ = text.split("---\n", 2)
    loaded = yaml.safe_load(block)
    assert isinstance(loaded, dict), f"{path.name} frontmatter is not a mapping"
    frontmatter: dict[str, object] = {}
    for key, value in loaded.items():
        assert isinstance(key, str), f"{path.name} frontmatter has a non-string key"
        frontmatter[key] = value
    return frontmatter


def test_plugin_manifest_carries_required_fields(tmp_path: Path, plugin_cohort: _PluginPythonCohort) -> None:
    output = tmp_path / "plugin"
    manifest = materialise_plugin(output, cohort=plugin_cohort)
    assert manifest.plugin_name == "cadrumo"

    document = json.loads((output / ".claude-plugin" / "plugin.json").read_text(encoding=_UTF_8))
    assert document["name"] == "cadrumo"
    assert document["displayName"] == "CADRUMO Spanish tax assistant"
    assert document["version"] == manifest.version
    assert document["defaultEnabled"] is False
    assert document["license"] == "Apache-2.0"
    assert document["author"] == {"name": "CADRUMO tax assistant project"}
    assert isinstance(document["keywords"], list) and document["keywords"]
    # Bilingual (English + Spanish) copy; "never files" stated in the English section.
    assert "never files" in document["description"].lower()
    assert document["description"].startswith("English: Operate Cadrumo, the deterministic Spanish-tax CLI,")
    assert "\nEspañol: " in document["description"]
    assert "aeat Spanish-tax CLI" not in document["description"]


def test_plugin_emits_the_skills_tree_from_the_authored_source(
    tmp_path: Path, plugin_cohort: _PluginPythonCohort
) -> None:
    output = tmp_path / "plugin"
    manifest = materialise_plugin(output, cohort=plugin_cohort)
    assert manifest.skills_written == len(_shipped_skill_names())

    assert (output / "skills" / "cadrumo-preparar-modelo-130" / "SKILL.md").is_file()
    # The progressive-disclosure reference a SKILL cites must travel with it.
    assert (output / "skills" / "cadrumo-preparar-modelo-130" / "reference" / "casillas.md").is_file()


def test_plugin_skill_document_matches_the_shipped_bytes(tmp_path: Path, plugin_cohort: _PluginPythonCohort) -> None:
    output = tmp_path / "plugin"
    materialise_plugin(output, cohort=plugin_cohort)
    shipped = harness_root().joinpath("skills", "cadrumo-preparar-modelo-130", "SKILL.md").read_text(encoding=_UTF_8)
    written = (output / "skills" / "cadrumo-preparar-modelo-130" / "SKILL.md").read_text(encoding=_UTF_8)
    assert written == shipped


def test_plugin_agents_carry_claude_frontmatter_never_mode(tmp_path: Path, plugin_cohort: _PluginPythonCohort) -> None:
    output = tmp_path / "plugin"
    manifest = materialise_plugin(output, cohort=plugin_cohort)
    slugs = _persona_slugs()
    assert manifest.agents_written == len(slugs)

    agents_dir = output / "agents"
    for slug in slugs:
        frontmatter = _agent_frontmatter(agents_dir / f"{slug}.md")
        assert frontmatter["name"] == slug
        assert isinstance(frontmatter["description"], str) and frontmatter["description"].strip()
        # The harness-authoring mode: field is not a Claude field and must never be emitted.
        assert "mode" not in frontmatter


def test_read_only_persona_maps_to_a_disallowed_tools_denylist(
    tmp_path: Path, plugin_cohort: _PluginPythonCohort
) -> None:
    output = tmp_path / "plugin"
    materialise_plugin(output, cohort=plugin_cohort)
    agents_dir = output / "agents"
    # The coordinator's tool scope declares itself read-only (orchestration only),
    # so it carries a workspace-mutation denylist; a state-mutating persona does not.
    coordinator = _agent_frontmatter(agents_dir / "cadrumo-coordinator.md")
    assert coordinator["disallowedTools"] == ["Edit", "Write", "NotebookEdit"]
    classifier = _agent_frontmatter(agents_dir / "cadrumo-classifier.md")
    assert "disallowedTools" not in classifier


def test_plugin_agent_body_preserves_the_shipped_persona_prose(
    tmp_path: Path, plugin_cohort: _PluginPythonCohort
) -> None:
    output = tmp_path / "plugin"
    materialise_plugin(output, cohort=plugin_cohort)
    written = (output / "agents" / "cadrumo-coordinator.md").read_text(encoding=_UTF_8)
    shipped = harness_root().joinpath("personas", "cadrumo-coordinator.md").read_text(encoding=_UTF_8)
    # The persona prose rides verbatim as the agent system prompt after the frontmatter.
    assert written.endswith(shipped)


def test_exact_closed_world_cohort_interpolates_into_manifest_and_mcp_launch(
    tmp_path: Path, plugin_cohort: PluginTestCohort
) -> None:
    output = tmp_path / "plugin"
    materialise_plugin(output, cohort=plugin_cohort)
    document = json.loads((output / ".claude-plugin" / "plugin.json").read_text(encoding=_UTF_8))
    assert document["version"] == "1.2.3"
    profile = document["userConfig"]["profile_id"]
    assert profile["type"] == "string"
    assert profile["required"] is True
    credential_reference = document["userConfig"]["credential_reference"]
    assert credential_reference["type"] == "string"
    assert credential_reference["default"] == ""
    assert credential_reference["required"] is False

    mcp = json.loads((output / ".mcp.json").read_text(encoding=_UTF_8))
    assert "aeat" not in mcp["mcpServers"]
    server = mcp["mcpServers"]["cadrumo"]
    assert server["command"] == "uvx"
    assert server["args"] == [
        "--isolated",
        "--no-config",
        "--no-sources",
        "--offline",
        "--no-index",
        "--find-links",
        "${CLAUDE_PLUGIN_ROOT}/artifacts/python/wheelhouse",
        "--no-python-downloads",
        "--from",
        f"${{CLAUDE_PLUGIN_ROOT}}/artifacts/python/{plugin_cohort.root_wheel.name}",
        "--with",
        f"${{CLAUDE_PLUGIN_ROOT}}/artifacts/python/{plugin_cohort.manuals_wheel.name}",
        "--with",
        f"${{CLAUDE_PLUGIN_ROOT}}/artifacts/python/{plugin_cohort.official_wheel.name}",
        "cadrumo-mcp",
        "--profile-id",
        "${user_config.profile_id}",
        "--credential-reference",
        "${user_config.credential_reference}",
    ]
    retained = json.loads((output / "artifacts" / "python" / "plugin-python-cohort.json").read_text(encoding=_UTF_8))
    assert set(retained) == {
        "artifacts",
        "runtime_wheelhouse",
        "runtime_wheelhouse_sha256",
        "schema",
        "sha256",
        "source_digest",
        "version",
    }
    assert retained["schema"] == "cadrumo.plugin-python-cohort.v2"
    assert retained["artifacts"] == {
        "cadrumo": plugin_cohort.root_wheel.name,
        "cadrumo-data-manuals": plugin_cohort.manuals_wheel.name,
        "cadrumo-data-official": plugin_cohort.official_wheel.name,
    }
    assert retained["sha256"] == {
        name: plugin_cohort.sha256[name] for name in ("cadrumo", "cadrumo-data-manuals", "cadrumo-data-official")
    }
    assert retained["source_digest"] == plugin_cohort.source_digest
    assert retained["version"] == plugin_cohort.version
    assert retained["runtime_wheelhouse"] == plugin_cohort.runtime_wheelhouse_manifest
    assert retained["runtime_wheelhouse_sha256"] == plugin_cohort.sha256["runtime-wheelhouse"]
    artifact_directory = output / "artifacts" / "python"
    assert {path.name for path in artifact_directory.glob("*.whl")} == {
        wheel.name for wheel in plugin_cohort.product_wheels
    }
    for wheel in plugin_cohort.product_wheels:
        assert (artifact_directory / wheel.name).read_bytes() == wheel.read_bytes()
    assert server["env"] == {
        "CADRUMO_MCP_REQUIRED_VERSION": "1.2.3",
        "PYTHONNOUSERSITE": "1",
        "PYTHONPATH": "",
    }


def test_emitted_plugin_passes_claude_validate_strict_when_cli_present(
    tmp_path: Path, plugin_cohort: _PluginPythonCohort
) -> None:
    """The emitted tree is schema-valid; where ``claude`` exists, prove it strict.

    The structural materialisation and its assertion always run. The live
    ``claude plugin validate --strict`` assertion runs only when the CLI is on
    PATH - it is an ADDITIONAL gate, never a substitute that lets the test pass
    without exercising the emitter, so a missing CLI degrades to "structure
    checked" rather than a silent skip of the whole test.
    """
    output = tmp_path / "plugin"
    manifest = materialise_plugin(output, cohort=plugin_cohort)
    assert (output / ".claude-plugin" / "plugin.json").is_file()
    assert manifest.skills_written > 0
    assert manifest.agents_written > 0

    claude = shutil.which("claude")
    if claude is not None:
        completed = subprocess.run(  # noqa: S603 - explicit validator executable and fixed argv, no shell
            [claude, "plugin", "validate", "--strict", str(output)],
            capture_output=True,
            check=False,
            timeout=60,
            encoding=_UTF_8,
        )
        assert completed.returncode == 0, (
            f"claude plugin validate --strict failed:\n{completed.stdout}\n{completed.stderr}"
        )


def test_materialiser_has_no_cohortless_or_version_override_compatibility() -> None:
    parameters = inspect.signature(materialise_plugin).parameters
    assert parameters["cohort"].default is inspect.Parameter.empty
    assert "version" not in parameters


@pytest.mark.parametrize("distribution", ["cadrumo", "cadrumo-data-manuals", "cadrumo-data-official"])
def test_foreign_product_wheel_bytes_are_refused(
    tmp_path: Path, plugin_cohort: PluginTestCohort, distribution: str
) -> None:
    wheels = {
        "cadrumo": plugin_cohort.root_wheel,
        "cadrumo-data-manuals": plugin_cohort.manuals_wheel,
        "cadrumo-data-official": plugin_cohort.official_wheel,
    }
    wheels[distribution].write_bytes(b"foreign product wheel")
    with pytest.raises(ValueError, match=f"digest mismatch for '{distribution}'"):
        materialise_plugin(tmp_path / "plugin", cohort=plugin_cohort)


def test_foreign_runtime_wheelhouse_bytes_are_refused(tmp_path: Path, plugin_cohort: PluginTestCohort) -> None:
    plugin_cohort.runtime_wheelhouse.write_bytes(b"foreign runtime wheelhouse")
    with pytest.raises(ValueError, match="digest mismatch for 'runtime-wheelhouse'"):
        materialise_plugin(tmp_path / "plugin", cohort=plugin_cohort)


def test_runtime_wheelhouse_rejects_undeclared_members(tmp_path: Path, plugin_cohort: PluginTestCohort) -> None:
    with zipfile.ZipFile(plugin_cohort.runtime_wheelhouse, "a") as archive:
        archive.writestr("wheels/3.13/unapproved-1.0-py3-none-any.whl", b"unapproved dependency")
    changed = replace(
        plugin_cohort,
        sha256=plugin_cohort.sha256 | {"runtime-wheelhouse": sha256_hex(plugin_cohort.runtime_wheelhouse.read_bytes())},
    )
    with pytest.raises(ValueError, match="member inventory drifted"):
        materialise_plugin(tmp_path / "plugin", cohort=changed)


@pytest.mark.parametrize("relationship", ["equal", "source-below-artifacts", "artifacts-below-source"])
def test_overlapping_output_refuses_without_deleting_source_artifacts(tmp_path: Path, relationship: str) -> None:
    from ._plugin_cohort import make_test_plugin_cohort

    output = tmp_path / "plugin"
    artifact_directory = output / "artifacts" / "python"
    if relationship == "equal":
        source_directory = artifact_directory
    elif relationship == "source-below-artifacts":
        source_directory = artifact_directory / "cohort"
    else:
        source_directory = output
    cohort = make_test_plugin_cohort(source_directory)
    # A non-normalized input must receive the same protection as an absolute one.
    cohort = replace(cohort, directory=source_directory / ".." / source_directory.name)
    original_bytes = {path: path.read_bytes() for path in source_directory.iterdir() if path.is_file()}
    with pytest.raises(ValueError, match="must not overlap"):
        materialise_plugin(output, cohort=cohort)
    assert {path: path.read_bytes() for path in original_bytes} == original_bytes
