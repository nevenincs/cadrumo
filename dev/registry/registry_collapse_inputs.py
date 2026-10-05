"""Shared source dependency discovery and snapshot copying."""

from __future__ import annotations

import ast
import shutil
from collections.abc import Iterable
from importlib.util import resolve_name
from pathlib import Path
from tokenize import open as open_python

from dev.registry.compiler.source_evidence_fingerprint import collect_source_evidence_fingerprints

_TOOL_PACKAGE_ROOTS = (
    Path("dev/registry"),
    Path("src/cadrumo/domain/calculations/registry"),
)
_TOOL_ENTRYPOINT = Path("dev/registry/registry_collapse_verification.py")
_SNAPSHOT_SOURCE = Path("src/cadrumo/domain/calculations/registry/snapshot.py")
_SNAPSHOT_DYNAMIC_PROVIDERS = "_CROSS_DOMAIN_CHECK_MODULES"


def _local_module_path(repo_root: Path, module: str) -> Path | None:
    """Resolve an import to a local Python source, without importing it."""
    parts = module.split(".")
    if parts[0] == "dev":
        base = repo_root / "dev"
    elif parts[0] == "cadrumo":
        base = repo_root / "src" / "cadrumo"
    else:
        return None
    module_path = base.joinpath(*parts[1:])
    for candidate in (module_path.with_suffix(".py"), module_path / "__init__.py"):
        if candidate.is_file():
            return candidate
    return None


def _module_package(repo_root: Path, path: Path) -> tuple[str, ...]:
    relative = path.relative_to(repo_root).with_suffix("")
    parts = relative.parts
    if parts[0] == "src":
        parts = parts[1:]
    return parts[:-1]


def _snapshot_dynamic_modules(repo_root: Path, path: Path, tree: ast.Module) -> set[str]:
    """Read the snapshot's own literal provider declaration without importing it."""
    if path != repo_root / _SNAPSHOT_SOURCE:
        return set()
    declarations: list[ast.expr] = []
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == _SNAPSHOT_DYNAMIC_PROVIDERS and node.value is not None:
                declarations.append(node.value)
        elif isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == _SNAPSHOT_DYNAMIC_PROVIDERS for target in node.targets
        ):
            declarations.append(node.value)
    if len(declarations) != 1:
        raise ValueError(f"snapshot must declare one literal {_SNAPSHOT_DYNAMIC_PROVIDERS}")
    try:
        declared = ast.literal_eval(declarations[0])
    except (ValueError, TypeError, SyntaxError) as exc:
        raise ValueError(f"snapshot {_SNAPSHOT_DYNAMIC_PROVIDERS} must be a literal list or tuple") from exc
    if not isinstance(declared, list | tuple) or not declared or not all(isinstance(item, str) for item in declared):
        raise ValueError(f"snapshot {_SNAPSHOT_DYNAMIC_PROVIDERS} must contain module names")
    package = ".".join(_module_package(repo_root, path))
    modules = {resolve_name(name, package) for name in declared}
    if len(modules) != len(declared):
        raise ValueError(f"snapshot {_SNAPSHOT_DYNAMIC_PROVIDERS} repeats a provider")
    for module in modules:
        if _local_module_path(repo_root, module) is None:
            raise FileNotFoundError(f"snapshot declared dynamic provider is missing: {module}")
    return modules


def _imported_local_paths(repo_root: Path, path: Path, module_cache: dict[str, Path | None]) -> set[Path]:
    """Follow local static imports, including package initializers."""
    package = _module_package(repo_root, path)
    with open_python(path) as handle:
        tree = ast.parse(handle.read(), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            prefix = package[: len(package) - node.level + 1] if node.level else ()
            base = ".".join((*prefix, *(node.module.split(".") if node.module else ())))
            if base:
                modules.add(base)
                modules.update(f"{base}.{alias.name}" for alias in node.names if alias.name != "*")
    modules.update(_snapshot_dynamic_modules(repo_root, path, tree))
    imports: set[Path] = set()
    for module in modules:
        parts = module.split(".")
        for length in range(1, len(parts) + 1):
            name = ".".join(parts[:length])
            if name not in module_cache:
                module_cache[name] = _local_module_path(repo_root, name)
            local = module_cache[name]
            if local is not None:
                imports.add(local)
    return imports


def _tool_input_paths(repo_root: Path) -> tuple[Path, ...]:
    """Rediscover registry interpreters and their local import closure.

    The package census catches new or removed helpers, including dynamically
    selected modules. The entrypoint import closure also fingerprints the
    defining helpers it uses outside those packages, without scanning the
    unrelated repository.
    """
    root = repo_root.resolve(strict=True)
    paths = {
        path
        for relative in _TOOL_PACKAGE_ROOTS
        for path in (root / relative).rglob("*.py")
        if not {"tests", "__pycache__"}.intersection(path.relative_to(root).parts)
    }
    pending = [root / _TOOL_ENTRYPOINT, root / _SNAPSHOT_SOURCE]
    visited: set[Path] = set()
    module_cache: dict[str, Path | None] = {}
    while pending:
        path = pending.pop()
        if path in visited or not path.is_file():
            continue
        visited.add(path)
        paths.add(path)
        pending.extend(_imported_local_paths(root, path, module_cache) - visited)
    return tuple(sorted(paths))


def _source_dependency_paths(source_root: Path) -> tuple[Path, ...]:
    """Enumerate every non-registry compiler input that must be isolated."""
    evidence = tuple(
        Path(path) for path, _size, _modified_ns in collect_source_evidence_fingerprints(source_root, use_cache=False)
    )
    profile_root = source_root / "registry" / "cadrumo"
    profiles = tuple(path for path in profile_root.rglob("*") if path.is_file())
    return tuple(sorted(set((*evidence, *profiles))))


def _copy_source_dependencies(paths: Iterable[Path], *, source_root: Path, destination: Path) -> None:
    """Copy exact compiler inputs while retaining source-root-relative paths."""
    resolved_root = source_root.resolve(strict=True)
    for source in paths:
        relative = source.resolve(strict=True).relative_to(resolved_root)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
