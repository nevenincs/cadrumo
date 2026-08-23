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

import json
import inspect
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from .. import harness_root, iter_personas
from .._workspace import materialise_plugin
from ._plugin_cohort import TestPluginCohort

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


def test_plugin_manifest_carries_required_fields(tmp_path: Path, plugin_cohort: TestPluginCohort) -> None:
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
    tmp_path: Path, plugin_cohort: TestPluginCohort
) -> None:
    output = tmp_path / "plugin"
    manifest = materialise_plugin(output, cohort=plugin_cohort)
    assert manifest.skills_written == len(_shipped_skill_names())

    assert (output / "skills" / "cadrumo-preparar-modelo-130" / "SKILL.md").is_file()
    # The progressive-disclosure reference a SKILL cites must travel with it.
    assert (output / "skills" / "cadrumo-preparar-modelo-130" / "reference" / "casillas.md").is_file()


def test_plugin_skill_document_matches_the_shipped_bytes(
    tmp_path: Path, plugin_cohort: TestPluginCohort
) -> None:
    output = tmp_path / "plugin"
    materialise_plugin(output, cohort=plugin_cohort)
    shipped = harness_root().joinpath("skills", "cadrumo-preparar-modelo-130", "SKILL.md").read_text(encoding=_UTF_8)
    written = (output / "skills" / "cadrumo-preparar-modelo-130" / "SKILL.md").read_text(encoding=_UTF_8)
    assert written == shipped


def test_plugin_agents_carry_claude_frontmatter_never_mode(
    tmp_path: Path, plugin_cohort: TestPluginCohort
) -> None:
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
    tmp_path: Path, plugin_cohort: TestPluginCohort
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
    tmp_path: Path, plugin_cohort: TestPluginCohort
) -> None:
    output = tmp_path / "plugin"
    materialise_plugin(output, cohort=plugin_cohort)
    written = (output / "agents" / "cadrumo-coordinator.md").read_text(encoding=_UTF_8)
    shipped = harness_root().joinpath("personas", "cadrumo-coordinator.md").read_text(encoding=_UTF_8)
    # The persona prose rides verbatim as the agent system prompt after the frontmatter.
    assert written.endswith(shipped)


def test_exact_closed_world_cohort_interpolates_into_manifest_and_mcp_launch(
    tmp_path: Path, plugin_cohort: TestPluginCohort
) -> None:
    output = tmp_path / "plugin"
    materialise_plugin(output, cohort=plugin_cohort)
    document = json.loads((output / ".claude-plugin" / "plugin.json").read_text(encoding=_UTF_8))
    assert document["version"] == "1.2.3"
    # The surface option defaults to the orientation core.
    assert document["userConfig"]["surface"]["default"] == "core"

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
        f"${{CLAUDE_PLUGIN_ROOT}}/artifacts/python/{plugin_cohort.harness_wheel.name}",
        "--with",
        f"${{CLAUDE_PLUGIN_ROOT}}/artifacts/python/{plugin_cohort.root_wheel.name}",
        "--with",
        f"${{CLAUDE_PLUGIN_ROOT}}/artifacts/python/{plugin_cohort.manuals_wheel.name}",
        "--with",
        f"${{CLAUDE_PLUGIN_ROOT}}/artifacts/python/{plugin_cohort.official_wheel.name}",
        "cadrumo-mcp",
    ]
    retained = json.loads(
        (output / "artifacts" / "python" / "plugin-python-cohort.json").read_text(encoding=_UTF_8)
    )
    assert set(retained) == {
        "artifacts",
        "harness_version",
        "runtime_wheelhouse",
        "runtime_wheelhouse_sha256",
        "schema",
        "sha256",
        "source_commit",
        "version",
    }
    assert retained["schema"] == "cadrumo.plugin-python-cohort.v1"
    assert retained["artifacts"] == {
        "cadrumo": plugin_cohort.root_wheel.name,
        "cadrumo-harness": plugin_cohort.harness_wheel.name,
        "cadrumo-data-manuals": plugin_cohort.manuals_wheel.name,
        "cadrumo-data-official": plugin_cohort.official_wheel.name,
    }
    assert retained["sha256"] == {
        name: plugin_cohort.sha256[name]
        for name in ("cadrumo", "cadrumo-harness", "cadrumo-data-manuals", "cadrumo-data-official")
    }
    assert retained["harness_version"] == plugin_cohort.harness_version
    assert retained["runtime_wheelhouse"] == plugin_cohort.runtime_wheelhouse_manifest
    assert retained["runtime_wheelhouse_sha256"] == plugin_cohort.sha256["runtime-wheelhouse"]
    assert server["env"] == {
        "CADRUMO_MCP_REQUIRED_VERSION": "1.2.3",
        "CADRUMO_MCP_PERSONA": "${user_config.persona}",
        "CADRUMO_MCP_SURFACE": "${user_config.surface}",
        "PYTHONNOUSERSITE": "1",
        "PYTHONPATH": "",
    }


def test_persona_default_interpolates_into_user_config(
    tmp_path: Path, plugin_cohort: TestPluginCohort
) -> None:
    output = tmp_path / "plugin"
    materialise_plugin(output, persona_default="cadrumo-verifier", cohort=plugin_cohort)
    document = json.loads((output / ".claude-plugin" / "plugin.json").read_text(encoding=_UTF_8))
    persona = document["userConfig"]["persona"]
    assert persona["type"] == "string"
    assert persona["default"] == "cadrumo-verifier"
    assert persona["required"] is False


def test_default_persona_is_the_full_surface(tmp_path: Path, plugin_cohort: TestPluginCohort) -> None:
    output = tmp_path / "plugin"
    materialise_plugin(output, cohort=plugin_cohort)
    document = json.loads((output / ".claude-plugin" / "plugin.json").read_text(encoding=_UTF_8))
    assert document["userConfig"]["persona"]["default"] == ""


def test_emitted_plugin_passes_claude_validate_strict_when_cli_present(
    tmp_path: Path, plugin_cohort: TestPluginCohort
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
        completed = subprocess.run(  # noqa: S603 - claude resolved from PATH, fixed args
            [claude, "plugin", "validate", "--strict", str(output)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, (
            f"claude plugin validate --strict failed:\n{completed.stdout}\n{completed.stderr}"
        )


def test_materialiser_has_no_cohortless_or_version_override_compatibility() -> None:
    parameters = inspect.signature(materialise_plugin).parameters
    assert parameters["cohort"].default is inspect.Parameter.empty
    assert "version" not in parameters


def test_foreign_harness_bytes_are_refused(
    tmp_path: Path, plugin_cohort: TestPluginCohort
) -> None:
    plugin_cohort.harness_wheel.write_bytes(b"foreign harness")
    with pytest.raises(ValueError, match="cadrumo-harness"):
        materialise_plugin(tmp_path / "plugin", cohort=plugin_cohort)
