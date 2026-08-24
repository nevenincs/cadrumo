"""Structural ownership checks for Google terminal-precondition transport."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _constructed_model_names(source_path: Path) -> tuple[str, ...]:
    """Return direct evidence/verdict constructor sites in one production module."""
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    constructed: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        match node.func:
            case ast.Name(id=name) | ast.Attribute(attr=name):
                if name in {"ConditionEvidence", "PreconditionVerdict"}:
                    constructed.append(f"{source_path.name}:{node.lineno}:{name}")
    return tuple(constructed)


def test_google_modules_delegate_terminal_verdict_construction_to_application_owner() -> None:
    google_package = Path(__file__).parents[1]
    direct_construction = tuple(
        constructed
        for source_path in google_package.glob("*.py")
        for constructed in _constructed_model_names(source_path)
    )

    assert direct_construction == ()
