"""AST gate for the one permitted CLI-to-TUI launch seam."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_CLI_ROOT = Path(__file__).parents[3] / "src" / "cadrumo" / "entrypoints" / "cli"
_ALLOWED_LAUNCHER = _CLI_ROOT / "tui_launcher.py"
_CROSSING_WORDS = frozenset({"capability", "destination", "outcome", "request", "route", "session"})


def _words(value: str) -> frozenset[str]:
    """Split identifiers and literal keys into semantic words."""
    expanded = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", value)
    return frozenset(re.findall(r"[a-z0-9]+", expanded.casefold()))


def _is_retired_crossing(value: str) -> bool:
    words = _words(value)
    names_a_crossing = any(word.startswith(marker) for word in words for marker in _CROSSING_WORDS)
    is_tui_crossing = "tui" in words and names_a_crossing
    is_full_screen_crossing = {"full", "screen"}.issubset(words) and names_a_crossing
    return is_tui_crossing or is_full_screen_crossing or value == "--tui"


def _violations(tree: ast.AST) -> tuple[str, ...]:
    """Return route/capability/destination crossings named by one CLI module."""
    findings: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("cadrumo.entrypoints.tui"):
            findings.add(f"TUI import: {node.module}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("cadrumo.entrypoints.tui"):
                    findings.add(f"TUI import: {alias.name}")
        elif isinstance(node, ast.Name) and _is_retired_crossing(node.id):
            findings.add(f"retired crossing identifier: {node.id}")
        elif isinstance(node, ast.Attribute) and _is_retired_crossing(node.attr):
            findings.add(f"retired crossing identifier: {node.attr}")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value.startswith("cadrumo.entrypoints.tui"):
                findings.add(f"TUI module literal: {node.value}")
            elif not any(character.isspace() for character in node.value) and _is_retired_crossing(node.value):
                findings.add(f"retired crossing literal: {node.value}")
    return tuple(sorted(findings))


def _cli_production_modules() -> tuple[Path, ...]:
    """Discover the entire CLI lane instead of maintaining a TUI module inventory."""
    return tuple(path for path in _CLI_ROOT.rglob("*.py") if "tests" not in path.parts and path != _ALLOWED_LAUNCHER)


def test_only_the_opaque_launcher_may_name_a_tui_crossing() -> None:
    failures = {
        path.relative_to(_CLI_ROOT).as_posix(): _violations(ast.parse(path.read_text(encoding="utf-8")))
        for path in _cli_production_modules()
    }
    failures = {path: findings for path, findings in failures.items() if findings}

    assert failures == {}


def test_the_detector_rejects_imports_and_legacy_routing_shape() -> None:
    """A representative forbidden crossing fails, so the gate has teeth."""
    fixture = ast.parse(
        "from cadrumo.entrypoints.tui import app\n"
        "destination = FullScreenDestination.MODELO_WORK_REVIEW\n"
        "state['tui_requested'] = True\n"
    )

    findings = _violations(fixture)

    assert any(finding.startswith("TUI import:") for finding in findings)
    assert any("FullScreenDestination" in finding for finding in findings)
    assert any("tui_requested" in finding for finding in findings)
