"""Tests for the operator-workspace materialiser."""

from __future__ import annotations

from pathlib import Path

import pytest

from .. import materialise_workspace

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]


def test_materialise_writes_rules_personas_and_skills(tmp_path: Path) -> None:
    manifest = materialise_workspace(tmp_path)
    assert manifest.rules_written == 4
    assert manifest.personas_written >= 3
    assert manifest.skills_written >= 1

    assert (tmp_path / "rules" / "operator-operating-rules.md").is_file()
    assert (tmp_path / "personas" / "coordinator.md").is_file()
    assert (tmp_path / "skills" / "preparar-modelo-130" / "SKILL.md").is_file()


def test_materialised_content_matches_the_shipped_rules(tmp_path: Path) -> None:
    materialise_workspace(tmp_path)
    text = (tmp_path / "rules" / "operator-operating-rules.md").read_text(encoding="utf-8")
    assert text.strip().startswith("# ")
    assert "never compute" in text.lower()


def test_materialise_counts_match_written_files(tmp_path: Path) -> None:
    manifest = materialise_workspace(tmp_path)
    assert len(list((tmp_path / "rules").glob("*.md"))) == manifest.rules_written
    assert len(list((tmp_path / "personas").glob("*.md"))) == manifest.personas_written
    assert len(list((tmp_path / "skills").glob("*/SKILL.md"))) == manifest.skills_written
