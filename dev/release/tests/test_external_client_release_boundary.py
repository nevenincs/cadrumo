"""Regression gates for the base-CLI/harness dependency direction."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ..._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BASE_PACKAGE = REPO_ROOT / "src" / "cadrumo"
_HARNESS_PACKAGE = REPO_ROOT / "src" / "cadrumo-harness"


def _import_targets(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    targets: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            targets.append(node.module)
    return tuple(targets)


def test_base_cli_never_imports_the_harness() -> None:
    """The shipped base package has no dependency edge to its harness client."""
    crossings = {
        path.relative_to(REPO_ROOT): target
        for path in _BASE_PACKAGE.rglob("*.py")
        for target in _import_targets(path)
        if target == "cadrumo_harness" or target.startswith("cadrumo_harness.")
    }
    assert not crossings


def test_harness_declares_and_exercises_its_base_cli_dependency() -> None:
    """The separately shipped harness depends inward on the base CLI/library."""
    project_text = (_HARNESS_PACKAGE / "pyproject.toml").read_text(encoding="utf-8")
    assert '"cadrumo>=0.2.2,<0.3"' in project_text

    production_imports = {
        target
        for path in (_HARNESS_PACKAGE / "src" / "cadrumo_harness").rglob("*.py")
        if "tests" not in path.parts
        for target in _import_targets(path)
        if target == "cadrumo" or target.startswith("cadrumo.")
    }
    assert "cadrumo.entrypoints.cli.command_api" in production_imports


def test_harness_release_lanes_remain_present_and_separate() -> None:
    """Client-owned build/evaluation lanes remain available beside base release lanes."""
    assert (REPO_ROOT / ".github/workflows/packaging-claude.yml").is_file()
    assert (REPO_ROOT / ".github/workflows/agent-harness-eval.yml").is_file()
