"""Fixed-point gates for public core defining-module relocations."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_TARGETS = {
    "credentials": {
        "LENGTH_ALONE_IS_STRONG",
        "LENGTH_FAIR_FLOOR",
        "PROFILE_PASSWORD_MAX_SCALARS",
        "PROFILE_PASSWORD_MAX_UTF8_BYTES",
        "PROFILE_PASSWORD_MIN_SCALARS",
        "PassphraseStrength",
        "ProfilePasswordAssessment",
        "ProfilePasswordRefusalReason",
        "assess_passphrase_strength",
        "assess_profile_password",
    },
    "directory_scan": {"DirectoryEntryKind", "iter_directory", "scan_directory"},
}
_ALL_TARGETS = frozenset().union(*_TARGETS.values())
_REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


def _python_files() -> tuple[Path, ...]:
    """Return every production, test, development, and packaging Python file."""
    roots = tuple(_REPOSITORY_ROOT / name for name in ("src", "dev", "packaging"))
    return tuple(
        path
        for root in roots
        if root.is_dir()
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts
    )


def _module_definitions(tree: ast.Module, names: set[str]) -> set[str]:
    """Return real top-level definitions, excluding local aliases to an authority."""
    found: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            found.add(node.name)
            continue
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if isinstance(value, ast.Attribute):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
        found.update(target.id for target in targets if isinstance(target, ast.Name) and target.id in names)
    return found


def test_each_relocated_symbol_has_one_public_definition() -> None:
    """The move leaves one definition in the public module and no old files."""
    core_root = _REPOSITORY_ROOT / "src" / "cadrumo" / "core"
    assert not (core_root / "_credentials.py").exists()
    assert not (core_root / "_directory_scan.py").exists()

    definitions: dict[str, list[str]] = {name: [] for name in _ALL_TARGETS}
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for name in _module_definitions(tree, _ALL_TARGETS):
            definitions[name].append(path.relative_to(_REPOSITORY_ROOT).as_posix())

    for module_name, names in _TARGETS.items():
        module = importlib.import_module(f"cadrumo.core.{module_name}")
        expected = set(names)
        assert set(module.__all__) == expected
        for name in names:
            assert definitions[name] == [f"src/cadrumo/core/{module_name}.py"]
            value = getattr(module, name)
            if hasattr(value, "__module__"):
                assert value.__module__ == module.__name__


def test_core_namespace_has_no_relocated_bindings() -> None:
    """The package facade cannot resolve either relocated authority."""
    core = importlib.import_module("cadrumo.core")
    assert not _ALL_TARGETS & set(core.__all__)
    for name in _ALL_TARGETS:
        assert not hasattr(core, name)


def test_every_consumer_imports_the_public_defining_module() -> None:
    """The import census stays at the direct-module fixed point."""
    violations: list[str] = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            imported = {alias.name for alias in node.names} & _ALL_TARGETS
            if not imported:
                continue
            source = "." * node.level + (node.module or "")
            expected = "credentials" if imported & _TARGETS["credentials"] else "directory_scan"
            if not source.endswith(f".{expected}"):
                violations.append(f"{path}:{node.lineno}: {source} -> {sorted(imported)}")
    assert violations == []
