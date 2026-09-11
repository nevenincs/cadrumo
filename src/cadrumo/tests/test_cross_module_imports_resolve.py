"""Cross-module import resolution gate.

Importing a package cleanly proves only that its own module body runs.
This gate proves the other direction: every
``from cadrumo.X import {name}`` statement under ``src/cadrumo/`` resolves
to an attribute that actually exists on ``cadrumo.X``.

Closes the foreign-WIP failure pattern that surfaced three times in
the linkage integrity regression where a sibling change added an import
to a caller without adding the matching name to the target package's
``__init__.py`` imports / ``__all__``. The consumer module then
raises ``ImportError`` the next time any test collection walks it,
breaking the whole suite at collection time even though the target
package itself imports cleanly.

The scan walks every ``.py`` file under ``src/cadrumo/``, parses each
via :mod:`ast`, collects every ``ImportFrom`` statement that targets
the in-repo ``cadrumo.*`` namespace (absolute or relative), resolves
the target package, and asserts every imported name is
attribute-accessible after :func:`importlib.import_module`. Conditional
imports inside ``if TYPE_CHECKING:`` blocks are skipped because their
names are never bound at runtime; everything else is in scope.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator, Mapping
from importlib.util import find_spec
from pathlib import Path

import pytest

from .inventory import SRC_CADRUMO, package_ast_items

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _is_type_checking_block(node: ast.AST) -> bool:
    """Return True when ``node`` is an ``if TYPE_CHECKING:`` guard."""
    if not isinstance(node, ast.If):
        return False
    test = node.test
    if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
        return True
    return isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"


def _resolve_relative_module(source: Path, level: int, module: str | None) -> str | None:
    """Resolve ``from .module import X`` against ``source``'s package path.

    Python's relative-import semantics: ``level=1`` means *the package
    that contains this module*; ``level=2`` means that package's
    parent; and so on. For a non-``__init__`` file at
    ``cadrumo/sub/mod.py`` the containing package is ``cadrumo.sub``; for
    ``cadrumo/sub/__init__.py`` the file IS the package ``cadrumo.sub`` and
    the containing package is still ``cadrumo.sub``.

    Returns the absolute dotted module name (e.g. ``cadrumo.domain.modelos``)
    or ``None`` if the source file lives outside ``src/cadrumo`` (which
    would be a project layout violation; not this gate's concern).
    """
    try:
        relative = source.relative_to(SRC_CADRUMO.parent)
    except ValueError:
        return None
    parts = list(relative.with_suffix("").parts)
    # Whether ``source`` is an ``__init__.py`` (the package itself) or a
    # regular module (living inside its containing package), the package's
    # dotted path is recovered the same way: drop the trailing element.
    package_parts = parts[:-1]
    # ``level=1`` keeps every element; each additional level walks one
    # package up.
    if level - 1 > len(package_parts):
        return None
    anchor = package_parts[: len(package_parts) - (level - 1)] if level > 1 else package_parts
    if module:
        anchor = anchor + module.split(".")
    return ".".join(anchor)


def _walk_import_from(tree: ast.AST) -> Iterator[ast.ImportFrom]:
    """Yield every ``ImportFrom`` node not inside an ``if TYPE_CHECKING:`` block."""
    skip: set[int] = set()
    for node in ast.walk(tree):
        if _is_type_checking_block(node):
            for child in ast.walk(node):
                skip.add(id(child))
    for node in ast.walk(tree):
        if id(node) in skip:
            continue
        if isinstance(node, ast.ImportFrom):
            yield node


def _collect_import_pairs(source_tree_ast: Mapping[Path, ast.AST] | None = None) -> list[tuple[Path, str, str]]:
    """Walk every Cadrumo source and yield ``(source_file, module, name)`` import triples.

    Only ``from cadrumo.X import Y`` (absolute) and relative imports
    resolving back into the ``cadrumo.*`` tree are returned. ``import *``
    statements are excluded — they don't pin a specific name and the
    no-wildcard hygiene is a separate concern.
    """
    triples: list[tuple[Path, str, str]] = []
    for source, tree in package_ast_items(source_tree_ast, include_data=True):
        for node in _walk_import_from(tree):
            resolved = _resolve_relative_module(source, node.level, node.module) if node.level > 0 else node.module
            if not resolved or not resolved.startswith("cadrumo"):
                continue
            for alias in node.names:
                if alias.name == "*":
                    continue
                triples.append((source, resolved, alias.name))
    return triples


@pytest.fixture(scope="module")
def cadrumo_import_triples(source_tree_ast: Mapping[Path, ast.AST]) -> list[tuple[Path, str, str]]:
    """Collect import triples once per module from the shared package AST cache."""
    return _collect_import_pairs(source_tree_ast)


def _check_triple(triple: tuple[Path, str, str]) -> str | None:
    """Return None when the triple resolves, or a one-line failure description otherwise.

    Two resolution paths: (a) ``name`` is bound as an attribute on the
    target package (the canonical ``__init__.py`` re-export pattern),
    or (b) ``name`` is a submodule importable as ``{module}.{name}``
    (the ``from pkg import mod`` shape Python resolves lazily). The
    gate must accept both — only a triple that fails both paths is a
    true broken-import finding.
    """
    source, module, name = triple
    target_path = _module_source_path(module)
    if target_path is None:
        return (
            f"{source.relative_to(SRC_CADRUMO.parent).as_posix()}::{module}::{name}  (target module is not importable)"
        )
    if _module_exports(target_path, name, module=module):
        return None
    # Submodule import path — ``from pkg import mod`` succeeds if
    # ``pkg.mod`` is a real importable module, regardless of whether
    # ``pkg.__init__`` binds ``mod`` as an attribute.
    if _module_source_path(f"{module}.{name}") is not None:
        return None
    return f"{source.relative_to(SRC_CADRUMO.parent).as_posix()}::{module}::{name}"


def _module_source_path(module: str) -> Path | None:
    """Return an importable module's source without executing its module body."""
    try:
        spec = find_spec(module)
    except (ImportError, ModuleNotFoundError, ValueError):
        return None
    origin = None if spec is None else spec.origin
    if origin is None or origin in {"built-in", "frozen"}:
        return None
    path = Path(origin)
    return path if path.is_file() else None


def _bound_names(tree: ast.AST) -> frozenset[str]:
    """Return names statically bound by a module, including conditional imports."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Import):
            names.update(alias.asname or alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names if alias.name != "*")
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return frozenset(names)


def _literal_string(node: ast.AST) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _lazy_export_targets(tree: ast.AST) -> dict[str, tuple[str, str | None]]:
    """Read a PEP 562 export map, retaining its module-and-symbol contract."""
    maps: dict[str, dict[str, tuple[str, str | None]]] = {}
    for node in tree.body if isinstance(tree, ast.Module) else ():
        value: ast.AST | None = None
        target: ast.AST | None = None
        if isinstance(node, ast.Assign):
            value = node.value
            target = node.targets[0] if len(node.targets) == 1 else None
        elif isinstance(node, ast.AnnAssign):
            value = node.value
            target = node.target
        if not isinstance(target, ast.Name) or not isinstance(value, ast.Dict):
            continue
        entries: dict[str, tuple[str, str | None]] = {}
        for key, item in zip(value.keys, value.values, strict=False):
            name = _literal_string(key)
            if name is None:
                continue
            if isinstance(item, (ast.Tuple, ast.List)) and item.elts:
                module = _literal_string(item.elts[0])
                symbol = _literal_string(item.elts[1]) if len(item.elts) > 1 else None
            else:
                module, symbol = _literal_string(item), None
            if module is not None:
                entries[name] = (module, symbol)
        if entries:
            maps[target.id] = entries

    lazy_names = (
        {
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "__getattr__"
        }
        if isinstance(tree, ast.Module)
        else set()
    )
    if not lazy_names:
        return {}
    referenced = {
        name.id
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "__getattr__"
        for name in ast.walk(node)
        if isinstance(name, ast.Name) and isinstance(name.ctx, ast.Load)
    }
    result: dict[str, tuple[str, str | None]] = {}
    for map_name in referenced:
        result.update(maps.get(map_name, {}))
    return result


def _module_exports(path: Path, name: str, *, module: str, seen: frozenset[str] = frozenset()) -> bool:
    """Resolve a module attribute from source bindings or its declared lazy map."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError):
        return False
    if name in _bound_names(tree):
        return True
    if module in seen:
        return False
    lazy = _lazy_export_targets(tree).get(name)
    if lazy is None:
        return False
    target_module, target_name = lazy
    if target_module.startswith("."):
        package = module if path.name == "__init__.py" else module.rpartition(".")[0]
        from importlib.util import resolve_name

        target_module = resolve_name(target_module, package)
    target_path = _module_source_path(target_module)
    if target_path is None:
        return False
    return target_name is None or _module_exports(target_path, target_name, module=target_module, seen=seen | {module})


def test_cadrumo_cross_module_imports_resolve(
    cadrumo_import_triples: list[tuple[Path, str, str]],
) -> None:
    """Every runtime ``from cadrumo.X import Y`` triple resolves."""
    failures: list[str] = []
    for triple in cadrumo_import_triples:
        failure = _check_triple(triple)
        if failure is not None:
            failures.append(failure)
    assert not failures, "\nBroken cross-module imports:\n" + "\n".join(sorted(failures))
