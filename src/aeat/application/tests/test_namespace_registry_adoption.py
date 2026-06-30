"""Guard: every production secure-object namespace string is registry-declared.

Feature modules may spell a secure-object namespace as an inline string literal
rather than importing its registry constant. The domain repositories deliberately
do so to preserve the lazy-import (json-pipe-safety) contract, which forbids a
module-level ``aeat.adapters.persistence.storage`` import; the literal is
duplicated precisely to avoid eagerly pulling the storage package into every CLI
command's import chain.

This gate therefore does NOT require the constant import. It requires the weaker,
universally-satisfiable invariant that a namespace literal cannot drift from the
authority: every ``aeat.*`` namespace string that is assigned to a ``*_NAMESPACE``
target or passed as a secure-object call's ``namespace`` argument must equal a
namespace value declared in ``STORAGE_NAMESPACE_REGISTRY``. A literal that matches
no registered namespace is an unenrolled or typo'd namespace and fails the gate.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ...adapters.persistence.storage import STORAGE_NAMESPACE_REGISTRY
from ...core.paths import PROJECT_ROOT
from ...tests._inventory import leaf_name

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

#: Production trees whose secure-object namespace literals are cross-checked.
_GUARDED_ROOTS = (
    "src/aeat/application",
    "src/aeat/domain",
    "src/aeat/adapters/outbound",
)


def test_production_secure_object_namespace_literals_match_the_registry() -> None:
    registry_values = _registry_namespace_values()
    offences: list[str] = []
    for path in _iter_guarded_production_sources():
        relative = path.relative_to(PROJECT_ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            for value, lineno in _namespace_literal_usages(node):
                if value not in registry_values:
                    offences.append(
                        f"{relative}:{lineno}: secure-object namespace literal {value!r} "
                        f"is not declared in STORAGE_NAMESPACE_REGISTRY",
                    )

    assert offences == []


def _registry_namespace_values() -> frozenset[str]:
    return frozenset(item.namespace for item in STORAGE_NAMESPACE_REGISTRY.namespaces)


def _iter_guarded_production_sources() -> tuple[Path, ...]:
    return tuple(
        sorted(
            path
            for root in _GUARDED_ROOTS
            for path in (PROJECT_ROOT / root).rglob("*.py")
            if not _is_test_surface(path)
        ),
    )


def _is_test_surface(path: Path) -> bool:
    return path.name.startswith("test_") or path.name == "conftest.py" or "/test_" in path.as_posix()


def _namespace_literal_usages(node: ast.AST) -> list[tuple[str, int]]:
    """Return ``(value, lineno)`` for every ``aeat.*`` namespace literal used as a
    secure-object namespace: assigned to a ``namespace`` / ``*_NAMESPACE`` target or
    passed as a secure-object call's ``namespace`` argument.
    """
    usages: list[tuple[str, int]] = []
    if isinstance(node, ast.Assign):
        if any(_is_namespace_target(target) for target in node.targets):
            _append_literal(usages, node.value)
    elif isinstance(node, ast.AnnAssign):
        if _is_namespace_target(node.target):
            _append_literal(usages, node.value)
    elif isinstance(node, ast.Call):
        for keyword in node.keywords:
            if keyword.arg == "namespace":
                _append_literal(usages, keyword.value)
        if node.args and leaf_name(node.func) in _SECURE_OBJECT_METHODS:
            _append_literal(usages, node.args[0])
    return usages


def _append_literal(usages: list[tuple[str, int]], node: ast.expr | None) -> None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.startswith("aeat."):
        usages.append((node.value, getattr(node, "lineno", -1)))


def _is_namespace_target(node: ast.AST) -> bool:
    if isinstance(node, ast.Name):
        return node.id == "namespace" or node.id.endswith("_NAMESPACE")
    if isinstance(node, ast.Attribute):
        return node.attr == "namespace" or node.attr.endswith("_NAMESPACE")
    return False
