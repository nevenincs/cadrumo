"""Regression gates for the base-CLI/harness dependency direction.

The harness ships inside the product wheel rather than as its own distribution,
so the direction is no longer expressed by a dependency declaration between two
projects. It is expressed by the import graph within one package, which is what
these gates read.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ..._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BASE_PACKAGE = REPO_ROOT / "src" / "cadrumo"
_HARNESS_PACKAGE = REPO_ROOT / "src" / "cadrumo_harness"


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


def test_the_harness_reaches_the_base_cli_through_its_command_api() -> None:
    """The harness depends inward, and through the boundary meant to carry it.

    Both halves matter. Importing nothing from the base package would mean the
    harness had grown its own copy of the command surface; importing it through
    some module other than the command API would mean the boundary had been
    bypassed rather than used.
    """
    production_imports = {
        target
        for path in _HARNESS_PACKAGE.rglob("*.py")
        if "tests" not in path.parts
        for target in _import_targets(path)
        if target == "cadrumo" or target.startswith("cadrumo.")
    }

    assert production_imports, "the harness imports nothing from the base package"
    assert "cadrumo.entrypoints.cli.command_api" in production_imports


def test_the_harness_evaluation_lane_stays_separate_from_the_release_path() -> None:
    """The harness keeps its own assurance lane and does not ride the release one.

    It ships in the product wheel now, so nothing structural stops its suite
    being folded into the publish path. Keeping it separate is what stops a
    harness failure blocking a product release, and the reverse.
    """
    assert (REPO_ROOT / ".github/workflows/agent-harness-eval.yml").is_file()

    publish = (REPO_ROOT / ".github/workflows/publish.yml").read_text(encoding="utf-8")
    assert "cadrumo_harness" not in publish, "the publish path runs harness-specific work"
