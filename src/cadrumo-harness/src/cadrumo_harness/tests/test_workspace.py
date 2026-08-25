"""Tests for the Claude-native operator-workspace materialiser.

Asserts the workspace materialiser writes the shipped harness in the
Claude-native layout - ``.claude/skills/<name>/SKILL.md`` plus reference
material, ``.claude/agents/<persona>.md``, ``.claude/rules/<rule>.md``, and a
root ``CLAUDE.md`` importing every rule - with strict content equality against
the shipped data, over a real filesystem ``tmp_path``. The prior flat layout is
gone (no-legacy), so its absence is asserted too.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.directory_scan import scan_directory

from .. import harness_root, iter_operator_rules, iter_personas
from .._workspace import materialise_workspace

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_UTF_8 = "utf-8"


def _shipped_skill_names() -> list[str]:
    skills_root = harness_root().joinpath("skills")
    return sorted(
        child.name for child in skills_root.iterdir() if child.is_dir() and child.joinpath("SKILL.md").is_file()
    )


def test_materialise_writes_the_claude_native_layout(tmp_path: Path) -> None:
    manifest = materialise_workspace(tmp_path)
    assert manifest.rules_written == 7
    assert manifest.personas_written == 7
    assert manifest.skills_written == len(_shipped_skill_names())

    assert (tmp_path / ".claude" / "rules" / "cadrumo-operator-operating-rules.md").is_file()
    assert (tmp_path / ".claude" / "agents" / "cadrumo-coordinator.md").is_file()
    assert (tmp_path / ".claude" / "skills" / "cadrumo-preparar-modelo-130" / "SKILL.md").is_file()
    # The progressive-disclosure reference a SKILL cites must travel with it.
    assert (tmp_path / ".claude" / "skills" / "cadrumo-preparar-modelo-130" / "reference" / "casillas.md").is_file()


def test_the_prior_flat_layout_is_gone(tmp_path: Path) -> None:
    materialise_workspace(tmp_path)
    assert not (tmp_path / "rules").exists()
    assert not (tmp_path / "personas").exists()
    assert not (tmp_path / "skills").exists()


def test_claude_memory_imports_every_operator_rule(tmp_path: Path) -> None:
    materialise_workspace(tmp_path)
    memory = (tmp_path / "CLAUDE.md").read_text(encoding=_UTF_8)
    for rule in iter_operator_rules():
        assert f"@.claude/rules/{rule.name}" in memory


def test_written_rules_and_personas_match_the_shipped_bytes(tmp_path: Path) -> None:
    materialise_workspace(tmp_path)
    for rule in iter_operator_rules():
        written = (tmp_path / ".claude" / "rules" / rule.name).read_text(encoding=_UTF_8)
        assert written == rule.read_text(encoding=_UTF_8)
    for persona in iter_personas():
        written = (tmp_path / ".claude" / "agents" / persona.name).read_text(encoding=_UTF_8)
        assert written == persona.read_text(encoding=_UTF_8)


def test_written_skill_document_matches_the_shipped_bytes(tmp_path: Path) -> None:
    materialise_workspace(tmp_path)
    shipped = harness_root().joinpath("skills", "cadrumo-preparar-modelo-130", "SKILL.md").read_text(encoding=_UTF_8)
    written = (tmp_path / ".claude" / "skills" / "cadrumo-preparar-modelo-130" / "SKILL.md").read_text(encoding=_UTF_8)
    assert written == shipped


def test_manifest_counts_match_written_files(tmp_path: Path) -> None:
    manifest = materialise_workspace(tmp_path)
    claude = tmp_path / ".claude"
    assert len(list(scan_directory(claude / "rules", pattern="*.md"))) == manifest.rules_written
    assert len(list(scan_directory(claude / "agents", pattern="*.md"))) == manifest.personas_written
    assert len(list((claude / "skills").glob("*/SKILL.md"))) == manifest.skills_written
