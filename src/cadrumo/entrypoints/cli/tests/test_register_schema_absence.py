"""Package-wide absence gate for retired runtime schema registration."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_cli_production_has_no_runtime_schema_registration() -> None:
    cli_root = Path(__file__).parents[1]
    violations: list[str] = []
    for path in sorted(cli_root.rglob("*.py")):
        if "tests" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)) and any(
                alias.name == "register_schema" for alias in node.names
            ):
                violations.append(f"{path}:{node.lineno}: import")
            if isinstance(node, ast.Call):
                called = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", None)
                if called == "register_schema":
                    violations.append(f"{path}:{node.lineno}: call/decorator")
    assert violations == []
