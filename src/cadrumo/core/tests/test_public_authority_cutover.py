"""Fixed-point gates for public core defining-module relocations."""

from __future__ import annotations

import ast
import importlib
from functools import cache
from pathlib import Path

import pytest
from dev.quality.import_hygiene_scan import tracked_live_files

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
_TEXT_SUFFIXES = frozenset({".cfg", ".ini", ".json", ".md", ".rst", ".toml", ".txt", ".yaml", ".yml"})
_IGNORED_DIRECTORY_NAMES = frozenset(
    {".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".venv", ".vault", "__pycache__", "_build", "build", "dist"}
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
def _tracked_files() -> tuple[Path, ...]:
    """Return the authoritative tracked inventory, excluding only history/build output."""
    return tracked_live_files()


@cache
def _python_files() -> tuple[Path, ...]:
    """Return every tracked live Python surface, including stubs and root files."""
    return tuple(path for path in _tracked_files() if path.suffix.lower() in {".py", ".pyi"})


@cache
def _text_files() -> tuple[Path, ...]:
    """Return first-party source and documentation text files for string census."""
    return tuple(path for path in _tracked_files() if path.suffix.lower() in _TEXT_SUFFIXES)


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
                if alias.name == "importlib":
                    aliases[alias.asname or alias.name] = "importlib"
                if alias.asname and alias.name.startswith(_CORE_PACKAGE):
                    aliases[alias.asname] = alias.name
                elif alias.name == _CORE_PACKAGE:
                    aliases["cadrumo"] = "cadrumo"
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            module = node.module or ""
            for alias in node.names:
                if module == "importlib" and alias.name in {"import_module"}:
                    aliases[alias.asname or alias.name] = f"importlib.{alias.name}"
                if module == "cadrumo" and alias.name == "core":
                    aliases[alias.asname or alias.name] = _CORE_PACKAGE
                elif module == _CORE_PACKAGE and alias.name in _TARGET_MODULES:
                    aliases[alias.asname or alias.name] = f"{_CORE_PACKAGE}.{alias.name}"
    return aliases


def _module_constants(tree: ast.Module) -> dict[str, str]:
    """Resolve simple module-level string constants used by dynamic imports."""
    constants: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = _constant_string(node.value, constants)
        if value is None:
            continue
        targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
        for target in targets:
            if isinstance(target, ast.Name):
                constants[target.id] = value
    return constants


def _constant_string(node: ast.AST, constants: dict[str, str] | None = None) -> str | None:
    """Resolve a static string expression used by a dynamic import/access."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name) and constants is not None:
        return constants.get(node.id)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _constant_string(node.left, constants)
        right = _constant_string(node.right, constants)
        if left is not None and right is not None:
            return left + right
    return None


def _qualified_expression(
    node: ast.AST, aliases: dict[str, str], constants: dict[str, str] | None = None
) -> str | None:
    """Resolve static and common dynamic qualified expressions."""
    if isinstance(node, ast.Name):
        return aliases.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        base = _qualified_expression(node.value, aliases, constants)
        return f"{base}.{node.attr}" if base else None
    if not isinstance(node, ast.Call):
        return None
    function = _qualified_expression(node.func, aliases, constants)
    if function in {"importlib.import_module", "__import__"} and node.args:
        return _constant_string(node.args[0], constants)
    if function in {"getattr", "setattr", "delattr"} and len(node.args) >= 2:
        base = _qualified_expression(node.args[0], aliases, constants)
        attribute = _constant_string(node.args[1], constants)
        return f"{base}.{attribute}" if base and attribute else None
    return None


def _literal_names(node: ast.AST, bindings: dict[str, ast.AST] | None = None, seen: set[str] | None = None) -> set[str]:
    """Return string members from a literal export container."""
    bindings = bindings or {}
    seen = seen or set()
    if isinstance(node, ast.Name) and node.id in bindings and node.id not in seen:
        return _literal_names(bindings[node.id], bindings, {*seen, node.id})
    if isinstance(node, (ast.List, ast.Set, ast.Tuple)):
        return {value for item in node.elts for value in _literal_names(item, bindings, seen)}
    if isinstance(node, ast.Dict):
        return {
            value
            for item in (*node.keys, *node.values)
            if item is not None
            for value in _literal_names(item, bindings, seen)
        }
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "dict":
        return {
            value
            for argument in node.args
            for value in _literal_names(argument, bindings, seen)
        } | {
            value
            for keyword in node.keywords
            for value in (
                ({keyword.arg} if keyword.arg is not None else set())
                | _literal_names(keyword.value, bindings, seen)
            )
        }
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return {node.value}
    return set()


def _literal_bindings(tree: ast.Module) -> dict[str, ast.AST]:
    bindings: dict[str, ast.AST] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    bindings[target.id] = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            bindings[node.target.id] = node.value
    return bindings


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
                if _resolve_import_module(path, node) != f"{_CORE_PACKAGE}.{expected}":
                    violations.append(f"{path}:{node.lineno}: {source} -> {alias.name}")
                if alias.asname:
                    violations.append(f"{path}:{node.lineno}: aliased target import {alias.name} as {alias.asname}")
    return violations


def _resolve_import_module(path: Path, node: ast.ImportFrom) -> str:
    """Resolve an ImportFrom to its absolute module name for exact matching."""
    if node.level == 0:
        return node.module or ""
    try:
        relative = path.resolve().relative_to((_REPOSITORY_ROOT / "src").resolve())
    except ValueError:
        return _import_source(node)
    package = relative.parent.parts
    keep = len(package) - node.level + 1
    if keep <= 0:
        return _import_source(node)
    return ".".join((*package[:keep], *(node.module or "").split(".")))


def _binding_violations(path: Path, tree: ast.Module) -> list[str]:
    """Find target aliases and package export/re-export containers."""
    owner = path.resolve()
    allowed_owner_paths = {_owner_path(module).resolve() for module in _TARGETS}
    violations: list[str] = []
    aliases = _module_aliases(tree)
    constants = _module_constants(tree)
    bindings = _literal_bindings(tree)
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
        target_names = {target.id for target in targets if isinstance(target, ast.Name)}
        if target_names & _ALL_TARGETS and owner not in allowed_owner_paths:
            violations.append(f"{path}:{node.lineno}: target binding {sorted(target_names & _ALL_TARGETS)}")
        if target_names & _EXPORT_CONTAINER_NAMES:
            exported = _literal_names(node.value, bindings)
            if exported & _ALL_TARGETS and owner not in allowed_owner_paths:
                violations.append(f"{path}:{node.lineno}: target re-export {sorted(exported & _ALL_TARGETS)}")
        value_name = _qualified_expression(node.value, aliases, constants)
        if value_name in _ALL_TARGETS and target_names - _ALL_TARGETS:
            violations.append(f"{path}:{node.lineno}: target alias {value_name}")
    return violations


def _qualified_violations(path: Path, tree: ast.Module) -> list[str]:
    """Find retired facade paths and non-direct canonical-module attribute access."""
    aliases = _module_aliases(tree)
    constants = _module_constants(tree)
    owner = path.resolve()
    allowed_owner_paths = {_owner_path(module).resolve() for module in _TARGETS}
    violations: list[str] = []
    expressions: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Attribute, ast.Call)):
            expression = _qualified_expression(node, aliases, constants)
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
        if not path.is_file():
            continue
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
        if not path.is_file():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        violations.extend(_import_violations(path, tree))
    assert violations == []


def test_no_qualified_alias_or_string_remnants_survive() -> None:
    """Qualified access, dynamic imports, aliases, re-exports, and strings stay absent."""
    violations: list[str] = []
    for path in _python_files():
        if not path.is_file():
            continue
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
        f"import importlib\nmodule_name = {retired_private_module!r}\nimportlib.import_module(module_name)\n",
        f"import importlib\ngetattr(importlib.import_module({_CORE_PACKAGE!r}), 'scan_directory')\n",
        "from unrelated.directory_scan import scan_directory\n",
        "exports = scan_directory\n",
        "__all__ = ['scan_directory']\n",
        "_LAZY_EXPORTS = {'scan_directory': '.directory_scan'}\n",
        "lazy = {'scan_directory': '.directory_scan'}\n_LAZY_EXPORTS = lazy\n",
        "_LAZY_EXPORTS = dict(scan_directory='.directory_scan')\n",
        f"import importlib as il\nname = {retired_private_module!r}\nil.import_module(name)\n",
        f"from importlib import import_module as load\nname = {retired_private_module!r}\nload(name)\n",
        f"def local():\n    name = {retired_private_module!r}\n    return importlib.import_module(name)\n",
    )
    for source in samples:
        tree = ast.parse(source)
        findings = _import_violations(synthetic_path, tree)
        findings.extend(_qualified_violations(synthetic_path, tree))
        findings.extend(_binding_violations(synthetic_path, tree))
        assert findings, source
