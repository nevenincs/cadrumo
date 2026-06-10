"""Guards for application secure-object namespace registry adoption."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ...core.paths import PROJECT_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

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
        local_namespaces = _collect_local_namespace_bindings(tree)
        registry_namespaces = _collect_registry_namespace_imports(tree)
        registry_namespaces.update(_collect_registry_derived_namespace_bindings(tree, registry_namespaces))
        for node in ast.walk(tree):
            if _assigns_namespace_literal(node):
                lineno = getattr(node, "lineno", "?")
                offences.append(f"{relative}:{lineno}: namespace literal assigned outside registry")
            if isinstance(node, ast.Call) and _passes_namespace_literal(node):
                lineno = getattr(node, "lineno", "?")
                offences.append(f"{relative}:{lineno}: namespace literal passed to secure-object call")
            if (
                isinstance(node, ast.Call)
                and (namespace_name := _secure_object_namespace_name(node)) is not None
                and namespace_name in local_namespaces
                and namespace_name not in registry_namespaces
            ):
                lineno = getattr(node, "lineno", "?")
                offences.append(
                    f"{relative}:{lineno}: secure-object namespace constant must come from storage registry"
                )

    assert offences == []


def _iter_application_production_sources() -> tuple[Path, ...]:
    return tuple(
        sorted(path for path in (PROJECT_ROOT / "src/aeat/application").rglob("*.py") if not _is_test_surface(path))
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


def _secure_object_namespace_name(node: ast.Call) -> str | None:
    for keyword in node.keywords:
        if keyword.arg == "namespace" and isinstance(keyword.value, ast.Name):
            return keyword.value.id
    if node.args and isinstance(node.args[0], ast.Name) and _call_name(node.func) in _SECURE_OBJECT_METHODS:
        return node.args[0].id
    return None


def _collect_local_namespace_bindings(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names if alias.name.endswith("_NAMESPACE"))
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.endswith("_NAMESPACE"):
                    names.add(target.id)
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id.endswith("_NAMESPACE")
        ):
            names.add(node.target.id)
    return names


def _collect_registry_namespace_imports(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if not _is_storage_registry_import(node):
            continue
        names.update(alias.asname or alias.name for alias in node.names if alias.name.endswith("_NAMESPACE"))
    return names


def _collect_registry_derived_namespace_bindings(tree: ast.AST, registry_namespaces: set[str]) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        targets: list[ast.expr] = []
        value: ast.expr | None = None
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
            value = node.value
        if not _is_registry_namespace_attribute(value, registry_namespaces):
            continue
        for target in targets:
            if isinstance(target, ast.Name) and target.id.endswith("_NAMESPACE"):
                names.add(target.id)
    return names


def _is_storage_registry_import(node: ast.ImportFrom) -> bool:
    return node.module == "aeat.adapters.persistence.storage" or (
        node.level > 0 and node.module == "adapters.persistence.storage"
    )


def _is_registry_namespace_attribute(node: ast.expr | None, registry_namespaces: set[str]) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "namespace"
        and isinstance(node.value, ast.Name)
        and node.value.id in registry_namespaces
    )


def _is_aeat_namespace_literal(node: ast.AST | None) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.startswith("aeat.")


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""
