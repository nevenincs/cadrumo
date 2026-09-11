"""AST gate for retired CLI/TUI routing vocabulary.

Import edges between the sibling entrypoints are owned by Import Linter and
proved by the real ``just check-import-boundaries`` planted-defect suite.  This retained
test covers the separate governance predicate for legacy routing names.
"""

from __future__ import annotations

import ast
import re

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_CROSSING_WORDS = frozenset({"capability", "destination", "outcome", "request", "route", "session"})


def _words(value: str) -> frozenset[str]:
    """Split identifiers and literal keys into semantic words."""
    expanded = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", value)
    # `re.findall` is typed `list[Any]`; with one capture-free pattern every
    # element is a `str`, which the comprehension states for the checker.
    return frozenset(str(word) for word in re.findall(r"[a-z0-9]+", expanded.casefold()))


def _is_retired_crossing(value: str) -> bool:
    words = _words(value)
    names_a_crossing = any(word.startswith(marker) for word in words for marker in _CROSSING_WORDS)
    is_tui_crossing = "tui" in words and names_a_crossing
    is_full_screen_crossing = {"full", "screen"}.issubset(words) and names_a_crossing
    return is_tui_crossing or is_full_screen_crossing or value == "--tui"


def _violations(tree: ast.AST) -> tuple[str, ...]:
    """Return legacy route/capability/destination names from one module."""
    findings: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and _is_retired_crossing(node.id):
            findings.add(f"retired crossing identifier: {node.id}")
        elif isinstance(node, ast.Attribute) and _is_retired_crossing(node.attr):
            findings.add(f"retired crossing identifier: {node.attr}")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value.startswith("cadrumo.entrypoints.tui"):
                findings.add(f"TUI module literal: {node.value}")
            elif not any(character.isspace() for character in node.value) and _is_retired_crossing(node.value):
                findings.add(f"retired crossing literal: {node.value}")
    return tuple(sorted(findings))


def test_the_detector_rejects_legacy_routing_shape() -> None:
    """A representative legacy routing shape fails, so the gate has teeth."""
    fixture = ast.parse("destination = FullScreenDestination.MODELO_WORK_REVIEW\nstate['tui_requested'] = True\n")

    findings = _violations(fixture)

    assert any("FullScreenDestination" in finding for finding in findings)
    assert any("tui_requested" in finding for finding in findings)
