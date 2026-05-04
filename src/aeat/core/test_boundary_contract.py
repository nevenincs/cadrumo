"""Boundary checks that protect :mod:`aeat.core` from upward dependencies.

The :mod:`aeat.core` package sits at the bottom of the dependency
graph: the outer layers (:mod:`aeat.adapters`, :mod:`aeat.application`,
:mod:`aeat.domain`, :mod:`aeat.entrypoints`) depend on it, never the
other way round. The tests here parse every production module under
:mod:`aeat.core` and assert that none of them imports anything from
those outer packages. A second test guards against the re-introduction
of the historical ``WorkspaceLockedError`` symbol that was removed
during the storage-foundation cleanup.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]

_CORE_ROOT = Path("src/aeat/core")
_SOURCE_ROOT = Path("src/aeat")
_FORBIDDEN_CORE_PREFIXES = (
    "aeat.adapters",
    "aeat.application",
    "aeat.domain",
    "aeat.entrypoints",
)


def _is_production_module(path: Path) -> bool:
    return not (path.name.startswith("test_") or path.name.startswith("_test_"))


def _absolute_import_name(module: str | None, names: list[ast.alias]) -> str:
    if module is not None:
        return module
    if not names:
        return ""
    return names[0].name


def _resolve_relative_import(path: Path, level: int, module: str | None) -> str:
    package_parts = list(path.with_suffix("").relative_to(Path("src")).parts)
    package_parts = package_parts[:-1] if package_parts[-1] == "__init__" else package_parts[:-1]
    if level:
        package_parts = package_parts[: len(package_parts) - level + 1]
    if module:
        package_parts.extend(module.split("."))
    return ".".join(package_parts)


def _iter_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                imports.append(_resolve_relative_import(path, node.level, node.module))
            else:
                imports.append(_absolute_import_name(node.module, node.names))
    return imports


def test_core_production_modules_do_not_import_outer_layers() -> None:
    """Core production modules must not import from the outer layers."""
    violations: list[str] = []
    for path in sorted(_CORE_ROOT.rglob("*.py")):
        if not _is_production_module(path):
            continue
        for imported in _iter_imports(path):
            if imported.startswith(_FORBIDDEN_CORE_PREFIXES):
                violations.append(f"{path}:{imported}")

    assert violations == []


def test_workspace_locked_error_is_not_present_in_production_sources() -> None:
    """The removed ``WorkspaceLockedError`` symbol must not reappear."""
    removed_error_name = "Workspace" + "LockedError"
    offenders: list[str] = []
    for path in sorted(_SOURCE_ROOT.rglob("*.py")):
        if not _is_production_module(path):
            continue
        if removed_error_name in path.read_text(encoding="utf-8"):
            offenders.append(str(path))

    assert offenders == []
