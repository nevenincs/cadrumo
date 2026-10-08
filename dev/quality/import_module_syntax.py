"""Module syntax for the subordinate import checker."""

from __future__ import annotations

import ast
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

from .import_check_models import RootPackage, SourceModule


def is_type_checking_guard(node: ast.AST) -> bool:
    """Recognize the conventional static-only import guard."""
    if isinstance(node, ast.Name):
        return node.id == "TYPE_CHECKING"
    if isinstance(node, ast.Attribute):
        return node.attr == "TYPE_CHECKING"
    if isinstance(node, ast.BoolOp):
        return any(is_type_checking_guard(value) for value in node.values)
    return False


def matches_any_module(module: str, prefixes: Sequence[str]) -> bool:
    """Match a module against the declared namespace prefixes."""
    return any(module == prefix or module.startswith(f"{prefix}.") for prefix in prefixes)


def module_name(path: Path, root: RootPackage) -> str:
    """Return the canonical dotted name below the configured source root."""
    relative = path.relative_to(root.source_root)
    parts = list(relative.parts)
    if parts[-1] == "__init__.py":
        parts.pop()
    else:
        parts[-1] = parts[-1][:-3]
    return ".".join(parts)


def assigned_names(targets: Iterable[ast.expr]) -> tuple[str, ...]:
    """Collect names bound by direct assignment targets."""
    names: list[str] = []
    for target in targets:
        if isinstance(target, ast.Name):
            names.append(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            names.extend(assigned_names(target.elts))
    return tuple(names)


def is_import_alias(node: ast.AST, imported: set[str]) -> bool:
    """Return true for a direct imported-name or imported-attribute alias."""
    if isinstance(node, ast.Name):
        return node.id in imported
    if isinstance(node, ast.Attribute):
        return is_import_alias(node.value, imported)
    return False


def module_package(name: str, modules: Mapping[str, SourceModule], root_names: frozenset[str]) -> str:
    """Find the nearest declared or parsed package that owns a module."""
    parts = name.split(".")
    for index in range(len(parts), 0, -1):
        candidate = ".".join(parts[:index])
        if candidate in root_names:
            return candidate
        record = modules.get(candidate)
        if record is not None and record.is_package:
            return candidate
    return name.rpartition(".")[0]


def is_descendant(module: str, owner: str) -> bool:
    """Check whether a module belongs to a nonempty owner namespace."""
    return bool(owner) and (module == owner or module.startswith(f"{owner}."))


def is_package(name: str, modules: Mapping[str, SourceModule], root_names: frozenset[str]) -> bool:
    """Recognize configured roots and parsed package modules."""
    return name in root_names or (name in modules and modules[name].is_package)


def is_first_party(name: str, root_names: frozenset[str]) -> bool:
    """Check whether a target belongs to a configured first-party root."""
    return any(name == root or name.startswith(f"{root}.") for root in root_names)


def resolve_from(importer: str, importer_is_package: bool, level: int, module: str | None) -> str | None:
    """Resolve relative import spelling without importing any module."""
    if level == 0:
        return module
    parts = importer.split(".")
    base = parts if importer_is_package else parts[:-1]
    strip = level - 1
    if strip > len(base):
        return None
    if strip:
        base = base[: len(base) - strip]
    if module:
        return ".".join((*base, *module.split(".")))
    return ".".join(base) if base else None


def qualified_name(node: ast.AST) -> str | None:
    """Read the dotted spelling of a name or attribute expression."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = qualified_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return None
