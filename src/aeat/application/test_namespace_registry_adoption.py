"""Guards for application secure-object namespace registry adoption."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from aeat.core.paths import PROJECT_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_SECURE_OBJECT_METHODS = {
    "delete",
    "exists",
    "iter_records_with_failures",
    "list_object_keys",
    "load",
    "peek_metadata",
    "probe_namespace_integrity",
    "save",
}


def test_application_production_secure_object_namespaces_use_registry_definitions() -> None:
    offences: list[str] = []
    for path in _iter_application_production_sources():
        relative = path.relative_to(PROJECT_ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if _assigns_namespace_literal(node):
                offences.append(f"{relative}:{node.lineno}: namespace literal assigned outside registry")
            if isinstance(node, ast.Call) and _passes_namespace_literal(node):
                offences.append(f"{relative}:{node.lineno}: namespace literal passed to secure-object call")

    assert offences == []


def _iter_application_production_sources() -> tuple[Path, ...]:
    return tuple(
        sorted(
            path
            for path in (PROJECT_ROOT / "src/aeat/application").rglob("*.py")
            if not _is_test_surface(path)
        )
    )


def _is_test_surface(path: Path) -> bool:
    return path.name.startswith("test_") or path.name == "conftest.py" or "/test_" in path.as_posix()


def _assigns_namespace_literal(node: ast.AST) -> bool:
    if isinstance(node, ast.Assign):
        return any(_is_namespace_target(target) for target in node.targets) and _is_aeat_namespace_literal(node.value)
    if isinstance(node, ast.AnnAssign):
        return _is_namespace_target(node.target) and _is_aeat_namespace_literal(node.value)
    return False


def _is_namespace_target(node: ast.AST) -> bool:
    if isinstance(node, ast.Name):
        return node.id == "namespace" or node.id.endswith("_NAMESPACE")
    if isinstance(node, ast.Attribute):
        return node.attr == "namespace" or node.attr.endswith("_NAMESPACE")
    return False


def _passes_namespace_literal(node: ast.Call) -> bool:
    if any(keyword.arg == "namespace" and _is_aeat_namespace_literal(keyword.value) for keyword in node.keywords):
        return True
    if not node.args or not _is_aeat_namespace_literal(node.args[0]):
        return False
    return _call_name(node.func) in _SECURE_OBJECT_METHODS


def _is_aeat_namespace_literal(node: ast.AST | None) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.startswith("aeat.")


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""
