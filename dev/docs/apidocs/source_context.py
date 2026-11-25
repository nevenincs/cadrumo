"""Inspect lexical source imports and locate their defining modules."""

from __future__ import annotations

import ast
import importlib.util
from functools import lru_cache
from pathlib import Path

from cadrumo.core.external_constants import UTF_8_ENCODING

_UTF_8 = UTF_8_ENCODING


def dotted_expression(value: ast.expr) -> tuple[str, ...] | None:
    """Return the dotted components of a name or attribute expression."""
    parts: list[str] = []
    while isinstance(value, ast.Attribute):
        parts.append(value.attr)
        value = value.value
    if not isinstance(value, ast.Name):
        return None
    return (value.id, *reversed(parts))


@lru_cache(maxsize=4096)
def module_import_context(
    path: Path,
    modified_ns: int,
    size: int,
) -> tuple[tuple[tuple[str, str, str | None, bool], ...], frozenset[str]]:
    """Cache direct imports and shadowed names from one source module."""
    del modified_ns, size  # The stat values participate in the cache key.
    try:
        tree = ast.parse(path.read_text(encoding=_UTF_8), filename=str(path))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return (), frozenset[str]()

    imports: list[tuple[str, str, str | None, bool]] = []
    shadowed: set[str] = set()

    for statement in tree.body:
        _collect_import(statement, path, imports)
        _collect_shadowed(statement, shadowed)

    return tuple(imports), frozenset(shadowed)


def _collect_import(statement: ast.stmt, path: Path, imports: list[tuple[str, str, str | None, bool]]) -> None:
    if isinstance(statement, ast.Import):
        for alias in statement.names:
            local_name = alias.asname or alias.name.split(".", maxsplit=1)[0]
            module_name = alias.name if alias.asname is not None else alias.name.split(".", maxsplit=1)[0]
            imports.append((local_name, module_name, None, alias.asname is not None))
    elif isinstance(statement, ast.ImportFrom):
        _collect_from_import(statement, path, imports)


def _collect_from_import(
    statement: ast.ImportFrom, path: Path, imports: list[tuple[str, str, str | None, bool]]
) -> None:
    root = source_package_root(path)
    package = source_module_name(root, path) if root is not None else ""
    package = package if path.name == "__init__.py" else package.rpartition(".")[0]
    if statement.module is None:
        module_name = package
    else:
        try:
            module_name = importlib.util.resolve_name(f"{'.' * statement.level}{statement.module}", package)
        except ImportError:
            return
    for alias in statement.names:
        if alias.name != "*":
            imports.append((alias.asname or alias.name, module_name, alias.name, True))


def _collect_shadowed(statement: ast.stmt, shadowed: set[str]) -> None:
    if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        shadowed.add(statement.name)
    elif isinstance(statement, ast.Assign | ast.AnnAssign) and (
        isinstance(statement, ast.Assign) or statement.value is not None
    ):
        targets = statement.targets if isinstance(statement, ast.Assign) else (statement.target,)
        for target in targets:
            _add_target_names(target, shadowed)
    elif isinstance(statement, (ast.For, ast.AsyncFor)):
        _add_target_names(statement.target, shadowed)
    elif isinstance(statement, (ast.With, ast.AsyncWith)):
        _with_targets(statement, shadowed)


def _with_targets(statement: ast.With | ast.AsyncWith, shadowed: set[str]) -> None:
    for item in statement.items:
        if item.optional_vars is not None:
            _add_target_names(item.optional_vars, shadowed)


def _add_target_names(target: ast.expr, shadowed: set[str]) -> None:
    if isinstance(target, ast.Name):
        shadowed.add(target.id)
    elif isinstance(target, (ast.Tuple, ast.List)):
        for item in target.elts:
            _add_target_names(item, shadowed)


def source_import_binding(path: Path, name: str) -> tuple[str, str, str | None, bool] | None:
    """Resolve an unshadowed top-level name to its import statement."""
    try:
        stat = path.stat()
    except OSError:
        return None
    imports, shadowed = module_import_context(path, stat.st_mtime_ns, stat.st_size)
    if name in shadowed:
        return None
    matches = {binding for binding in imports if binding[0] == name}
    return next(iter(matches)) if len(matches) == 1 else None


def source_name_is_shadowed(path: Path, name: str) -> bool:
    """Return whether a top-level declaration shadows an imported or builtin name."""
    try:
        stat = path.stat()
    except OSError:
        return False
    _, shadowed = module_import_context(path, stat.st_mtime_ns, stat.st_size)
    return name in shadowed


def source_package_root(path: Path) -> Path | None:
    """Find the ``src/<package>`` root containing *path*, including fixtures."""
    return next((parent for parent in path.parents if parent.parent.name == "src"), None)


def source_module_name(source_root: Path, path: Path) -> str:
    """Return the importable module name for a Python source path."""
    relative = path.relative_to(source_root).with_suffix("")
    parts = relative.parts[:-1] if relative.name == "__init__" else relative.parts
    return ".".join((source_root.name, *parts))


def module_source_path(source_root: Path, module_name: str) -> Path | None:
    """Resolve a module inside the source cohort containing *source_root*."""
    module_path = source_root.parent.joinpath(*module_name.split("."))
    source_path = module_path.with_suffix(".py")
    package_path = module_path / "__init__.py"
    if source_path.is_file():
        return source_path
    if package_path.is_file():
        return package_path
    return None
