"""Fixed-point gates for public core defining-module relocations."""

from __future__ import annotations

import ast
import importlib
from functools import cache
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
_TARGET_OWNER = {name: module for module, names in _TARGETS.items() for name in names}
_TARGET_MODULES = frozenset(_TARGETS)
_REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
_FIRST_PARTY_DIRECTORIES = ("src", "dev", "packaging", "docs")
_TEXT_SUFFIXES = frozenset({".json", ".md", ".rst", ".toml", ".txt", ".yaml", ".yml"})
_IGNORED_DIRECTORY_NAMES = frozenset(
    {".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".venv", "__pycache__", "_build", "build", "dist"}
)

# Build retired paths from components so this gate cannot accidentally satisfy
# its own string-remnant census by embedding the forbidden spellings.
_CORE_PACKAGE = ".".join(("cadrumo", "core"))
_RETIRED_QUALIFIED_REFERENCES = frozenset(
    f"{_CORE_PACKAGE}.{name}" for name in ("assess_profile_password", "scan_directory")
)
_RETIRED_PRIVATE_MODULES = frozenset(f"{_CORE_PACKAGE}.{name}" for name in ("_credentials", "_directory_scan"))
_CANONICAL_REFERENCES = frozenset(
    f"{_CORE_PACKAGE}.{module}.{name}"
    for module, names in _TARGETS.items()
    for name in names
)
_EXPORT_CONTAINER_NAMES = frozenset({"__all__", "_EXPORTS", "_EXPORT_MAP", "_LAZY_EXPORTS"})


@cache
def _python_files() -> tuple[Path, ...]:
    """Return every first-party Python file, including repository-root files."""
    root_files = tuple(path for path in _REPOSITORY_ROOT.glob("*.py") if path.is_file())
    nested_files = tuple(
        path
        for directory in _FIRST_PARTY_DIRECTORIES
        for path in (_REPOSITORY_ROOT / directory).rglob("*.py")
        if _is_live_path(path)
    )
    return tuple(sorted({*root_files, *nested_files}, key=lambda path: path.as_posix()))


@cache
def _text_files() -> tuple[Path, ...]:
    """Return first-party source and documentation text files for string census."""
    root_files = tuple(
        path for path in _REPOSITORY_ROOT.iterdir() if path.is_file() and path.suffix.lower() in _TEXT_SUFFIXES
    )
    nested_files = tuple(
        path
        for directory in _FIRST_PARTY_DIRECTORIES
        for path in (_REPOSITORY_ROOT / directory).rglob("*")
        if path.is_file() and path.suffix.lower() in _TEXT_SUFFIXES and _is_live_path(path)
    )
    return tuple(sorted({*root_files, *nested_files}, key=lambda path: path.as_posix()))


def _is_live_path(path: Path) -> bool:
    """Exclude generated/build trees from the live first-party census."""
    return not any(part in _IGNORED_DIRECTORY_NAMES for part in path.parts)


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


def _import_source(node: ast.ImportFrom) -> str:
    """Return an import-from source with relative dots retained."""
    return "." * node.level + (node.module or "")


def _module_aliases(tree: ast.Module) -> dict[str, str]:
    """Resolve aliases that can hide a package-facade qualified access."""
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname and alias.name.startswith(_CORE_PACKAGE):
                    aliases[alias.asname] = alias.name
                elif alias.name == _CORE_PACKAGE:
                    aliases["cadrumo"] = "cadrumo"
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            module = node.module or ""
            for alias in node.names:
                if module == "cadrumo" and alias.name == "core":
                    aliases[alias.asname or alias.name] = _CORE_PACKAGE
                elif module == _CORE_PACKAGE and alias.name in _TARGET_MODULES:
                    aliases[alias.asname or alias.name] = f"{_CORE_PACKAGE}.{alias.name}"
    return aliases


def _constant_string(node: ast.AST) -> str | None:
    """Resolve a static string expression used by a dynamic import/access."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _constant_string(node.left)
        right = _constant_string(node.right)
        if left is not None and right is not None:
            return left + right
    return None


def _qualified_expression(node: ast.AST, aliases: dict[str, str]) -> str | None:
    """Resolve static and common dynamic qualified expressions."""
    if isinstance(node, ast.Name):
        return aliases.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        base = _qualified_expression(node.value, aliases)
        return f"{base}.{node.attr}" if base else None
    if not isinstance(node, ast.Call):
        return None
    function = _qualified_expression(node.func, aliases)
    if function in {"importlib.import_module", "__import__"} and node.args:
        return _constant_string(node.args[0])
    if function in {"getattr", "setattr", "delattr"} and len(node.args) >= 2:
        base = _qualified_expression(node.args[0], aliases)
        attribute = _constant_string(node.args[1])
        return f"{base}.{attribute}" if base and attribute else None
    return None


def _literal_names(node: ast.AST) -> set[str]:
    """Return string members from a literal export container."""
    if not isinstance(node, (ast.List, ast.Set, ast.Tuple)):
        return set()
    return {item.value for item in node.elts if isinstance(item, ast.Constant) and isinstance(item.value, str)}


def _owner_path(module_name: str) -> Path:
    """Return the canonical source path for a relocated authority."""
    return _REPOSITORY_ROOT / "src" / "cadrumo" / "core" / f"{module_name}.py"


def _import_violations(path: Path, tree: ast.Module) -> list[str]:
    """Find facade, private-module, wildcard, and aliased target imports."""
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in _RETIRED_PRIVATE_MODULES:
                    violations.append(f"{path}:{node.lineno}: retired module import {alias.name}")
            continue
        if not isinstance(node, ast.ImportFrom):
            continue
        source = _import_source(node)
        module = node.module or ""
        if module in {"_credentials", "_directory_scan"} or module.endswith(("._credentials", "._directory_scan")):
            violations.append(f"{path}:{node.lineno}: retired relative module import {source}")
        for alias in node.names:
            if alias.name == "*" and (
                source == _CORE_PACKAGE or source.endswith(tuple(f".{name}" for name in _TARGET_MODULES))
            ):
                violations.append(f"{path}:{node.lineno}: wildcard import from {source}")
            if alias.name in _TARGET_MODULES and source == _CORE_PACKAGE:
                violations.append(f"{path}:{node.lineno}: module facade import {source}.{alias.name}")
            if alias.name in _TARGET_OWNER:
                expected = _TARGET_OWNER[alias.name]
                if not source.endswith(f".{expected}"):
                    violations.append(f"{path}:{node.lineno}: {source} -> {alias.name}")
                if alias.asname:
                    violations.append(f"{path}:{node.lineno}: aliased target import {alias.name} as {alias.asname}")
    return violations


def _binding_violations(path: Path, tree: ast.Module) -> list[str]:
    """Find target aliases and package export/re-export containers."""
    owner = path.resolve()
    allowed_owner_paths = {_owner_path(module).resolve() for module in _TARGETS}
    violations: list[str] = []
    aliases = _module_aliases(tree)
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
        target_names = {target.id for target in targets if isinstance(target, ast.Name)}
        if target_names & _ALL_TARGETS and owner not in allowed_owner_paths:
            violations.append(f"{path}:{node.lineno}: target binding {sorted(target_names & _ALL_TARGETS)}")
        if target_names & _EXPORT_CONTAINER_NAMES:
            exported = _literal_names(node.value)
            if exported & _ALL_TARGETS and owner not in allowed_owner_paths:
                violations.append(f"{path}:{node.lineno}: target re-export {sorted(exported & _ALL_TARGETS)}")
        value_name = _qualified_expression(node.value, aliases)
        if value_name in _ALL_TARGETS and target_names - _ALL_TARGETS:
            violations.append(f"{path}:{node.lineno}: target alias {value_name}")
    return violations


def _qualified_violations(path: Path, tree: ast.Module) -> list[str]:
    """Find retired facade paths and non-direct canonical-module attribute access."""
    aliases = _module_aliases(tree)
    owner = path.resolve()
    allowed_owner_paths = {_owner_path(module).resolve() for module in _TARGETS}
    violations: list[str] = []
    expressions: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Attribute, ast.Call)):
            expression = _qualified_expression(node, aliases)
            if expression:
                expressions.add(expression)
    for expression in expressions:
        if expression in _RETIRED_QUALIFIED_REFERENCES or expression in _RETIRED_PRIVATE_MODULES:
            violations.append(f"{path}: retired qualified expression {expression}")
        elif expression in _CANONICAL_REFERENCES and owner not in allowed_owner_paths:
            violations.append(f"{path}: qualified target access {expression}")
    return violations


def _string_violations(path: Path) -> list[str]:
    """Find retired qualified paths in first-party source/document text."""
    text = path.read_text(encoding="utf-8", errors="replace")
    return [
        f"{path}: retired string {value}"
        for value in (*_RETIRED_QUALIFIED_REFERENCES, *_RETIRED_PRIVATE_MODULES)
        if value in text
    ]


def test_each_relocated_symbol_has_one_public_definition() -> None:
    """The move leaves one definition in the public module and no old files."""
    core_root = _REPOSITORY_ROOT / "src" / "cadrumo" / "core"
    python_files = set(_python_files())
    assert set(_REPOSITORY_ROOT.glob("*.py")) <= python_files
    assert _REPOSITORY_ROOT / "conftest.py" in python_files
    assert not (core_root / "_credentials.py").exists()
    assert not (core_root / "_directory_scan.py").exists()

    definitions: dict[str, list[str]] = {name: [] for name in _ALL_TARGETS}
    for path in python_files:
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
        violations.extend(_import_violations(path, tree))
    assert violations == []


def test_no_qualified_alias_or_string_remnants_survive() -> None:
    """Qualified access, dynamic imports, aliases, re-exports, and strings stay absent."""
    violations: list[str] = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        violations.extend(_qualified_violations(path, tree))
        violations.extend(_binding_violations(path, tree))
    for path in _text_files():
        violations.extend(_string_violations(path))
    assert violations == []


def test_fixed_point_helpers_reject_legacy_shapes() -> None:
    """The strengthened census has positive controls for every forbidden shape."""
    synthetic_path = _REPOSITORY_ROOT / "synthetic_public_authority_cutover.py"
    retired_private_module = next(iter(_RETIRED_PRIVATE_MODULES))
    samples = (
        f"import {_CORE_PACKAGE} as core\ncore.scan_directory\n",
        f"from {_CORE_PACKAGE} import scan_directory as local_scan\n",
        f"import importlib\nimportlib.import_module({retired_private_module!r})\n",
        f"import importlib\ngetattr(importlib.import_module({_CORE_PACKAGE!r}), 'scan_directory')\n",
        "exports = scan_directory\n",
        "__all__ = ['scan_directory']\n",
    )
    for source in samples:
        tree = ast.parse(source)
        findings = _import_violations(synthetic_path, tree)
        findings.extend(_qualified_violations(synthetic_path, tree))
        findings.extend(_binding_violations(synthetic_path, tree))
        assert findings, source
