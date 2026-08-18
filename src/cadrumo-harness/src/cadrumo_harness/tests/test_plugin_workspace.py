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
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest
import yaml

from .. import harness_root, iter_personas
from .._workspace import materialise_plugin

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


def test_plugin_manifest_carries_required_fields(tmp_path: Path) -> None:
    manifest = materialise_plugin(tmp_path)
    assert manifest.plugin_name == "cadrumo"

    document = json.loads((tmp_path / ".claude-plugin" / "plugin.json").read_text(encoding=_UTF_8))
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


def test_plugin_emits_the_skills_tree_from_the_authored_source(tmp_path: Path) -> None:
    manifest = materialise_plugin(tmp_path)
    assert manifest.skills_written == len(_shipped_skill_names())

    assert (tmp_path / "skills" / "cadrumo-preparar-modelo-130" / "SKILL.md").is_file()
    # The progressive-disclosure reference a SKILL cites must travel with it.
    assert (tmp_path / "skills" / "cadrumo-preparar-modelo-130" / "reference" / "casillas.md").is_file()


def test_plugin_skill_document_matches_the_shipped_bytes(tmp_path: Path) -> None:
    materialise_plugin(tmp_path)
    shipped = harness_root().joinpath("skills", "cadrumo-preparar-modelo-130", "SKILL.md").read_text(encoding=_UTF_8)
    written = (tmp_path / "skills" / "cadrumo-preparar-modelo-130" / "SKILL.md").read_text(encoding=_UTF_8)
    assert written == shipped


def test_plugin_agents_carry_claude_frontmatter_never_mode(tmp_path: Path) -> None:
    manifest = materialise_plugin(tmp_path)
    slugs = _persona_slugs()
    assert manifest.agents_written == len(slugs)

    agents_dir = tmp_path / "agents"
    for slug in slugs:
        frontmatter = _agent_frontmatter(agents_dir / f"{slug}.md")
        assert frontmatter["name"] == slug
        assert isinstance(frontmatter["description"], str) and frontmatter["description"].strip()
        # The harness-authoring mode: field is not a Claude field and must never be emitted.
        assert "mode" not in frontmatter


def test_read_only_persona_maps_to_a_disallowed_tools_denylist(tmp_path: Path) -> None:
    materialise_plugin(tmp_path)
    agents_dir = tmp_path / "agents"
    # The coordinator's tool scope declares itself read-only (orchestration only),
    # so it carries a workspace-mutation denylist; a state-mutating persona does not.
    coordinator = _agent_frontmatter(agents_dir / "cadrumo-coordinator.md")
    assert coordinator["disallowedTools"] == ["Edit", "Write", "NotebookEdit"]
    classifier = _agent_frontmatter(agents_dir / "cadrumo-classifier.md")
    assert "disallowedTools" not in classifier


def test_plugin_agent_body_preserves_the_shipped_persona_prose(tmp_path: Path) -> None:
    materialise_plugin(tmp_path)
    written = (tmp_path / "agents" / "cadrumo-coordinator.md").read_text(encoding=_UTF_8)
    shipped = harness_root().joinpath("personas", "cadrumo-coordinator.md").read_text(encoding=_UTF_8)
    # The persona prose rides verbatim as the agent system prompt after the frontmatter.
    assert written.endswith(shipped)


def test_version_interpolates_into_manifest_and_mcp_pin(tmp_path: Path) -> None:
    materialise_plugin(tmp_path, version="1.2.3")
    document = json.loads((tmp_path / ".claude-plugin" / "plugin.json").read_text(encoding=_UTF_8))
    assert document["version"] == "1.2.3"
    # The surface option defaults to the orientation core.
    assert document["userConfig"]["surface"]["default"] == "core"

    mcp = json.loads((tmp_path / ".mcp.json").read_text(encoding=_UTF_8))
    assert "aeat" not in mcp["mcpServers"]
    server = mcp["mcpServers"]["cadrumo"]
    assert server["command"] == "uvx"
    # The retired cadrumo[agent] extra is gone: the launcher pin names the
    # sibling cadrumo-harness distribution at its OWN declared version (the
    # harness is versioned independently, so the plugin version must not leak
    # into the pin).
    harness_pyproject = tomllib.loads(
        (Path(__file__).resolve().parents[4] / "pyproject.toml").read_text(encoding=_UTF_8),
    )
    assert server["args"] == [
        "--from",
        f"cadrumo-harness=={harness_pyproject['project']['version']}",
        "cadrumo-mcp",
    ]
    assert not (tmp_path / "artifacts").exists()
    assert server["env"] == {
        "CADRUMO_MCP_REQUIRED_VERSION": "1.2.3",
        "CADRUMO_MCP_PERSONA": "${user_config.persona}",
        "CADRUMO_MCP_SURFACE": "${user_config.surface}",
    }


def test_persona_default_interpolates_into_user_config(tmp_path: Path) -> None:
    materialise_plugin(tmp_path, persona_default="cadrumo-verifier")
    document = json.loads((tmp_path / ".claude-plugin" / "plugin.json").read_text(encoding=_UTF_8))
    persona = document["userConfig"]["persona"]
    assert persona["type"] == "string"
    assert persona["default"] == "cadrumo-verifier"
    assert persona["required"] is False


def test_default_persona_is_the_full_surface(tmp_path: Path) -> None:
    materialise_plugin(tmp_path)
    document = json.loads((tmp_path / ".claude-plugin" / "plugin.json").read_text(encoding=_UTF_8))
    assert document["userConfig"]["persona"]["default"] == ""


def test_emitted_plugin_passes_claude_validate_strict_when_cli_present(tmp_path: Path) -> None:
    """The emitted tree is schema-valid; where ``claude`` exists, prove it strict.

    The structural materialisation and its assertion always run. The live
    ``claude plugin validate --strict`` assertion runs only when the CLI is on
    PATH - it is an ADDITIONAL gate, never a substitute that lets the test pass
    without exercising the emitter, so a missing CLI degrades to "structure
    checked" rather than a silent skip of the whole test.
    """
    manifest = materialise_plugin(tmp_path)
    assert (tmp_path / ".claude-plugin" / "plugin.json").is_file()
    assert manifest.skills_written > 0
    assert manifest.agents_written > 0

    claude = shutil.which("claude")
    if claude is not None:
        completed = subprocess.run(  # noqa: S603 - claude resolved from PATH, fixed args
            [claude, "plugin", "validate", "--strict", str(tmp_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, (
            f"claude plugin validate --strict failed:\n{completed.stdout}\n{completed.stderr}"
        )
