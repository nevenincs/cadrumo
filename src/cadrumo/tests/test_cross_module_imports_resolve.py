"""Cross-module import resolution gate.

Importing a module cleanly proves only that its own body runs.  This check
proves the other direction: every concrete ``ImportFrom`` statement under
``src/cadrumo/`` names a runtime-resolvable target.  Architectural ownership
and whether that import surface is permitted remain the responsibility of
``just check-import-boundaries``.

Closes the foreign-WIP failure pattern that surfaced three times in
the linkage integrity regression where a sibling change added an import
to a caller without adding the matching name to the target module. The consumer module then
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
from functools import cache
from importlib.util import find_spec
from pathlib import Path
from typing import NamedTuple

import pytest

from .inventory import SRC_CADRUMO, iter_parsed_sources, iter_statements, package_python_files

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
    if module is not None and module:
        anchor = anchor + module.split(".")
    return ".".join(anchor)


def _walk_import_from(tree: ast.AST) -> Iterator[ast.ImportFrom]:
    """Yield every ``ImportFrom`` node not inside an ``if TYPE_CHECKING:`` block."""
    for node in iter_statements(tree, prune=_is_type_checking_block):
        if isinstance(node, ast.ImportFrom):
            yield node


def _import_triples(source: Path, tree: ast.AST) -> Iterator[tuple[Path, str, str]]:
    """Yield the ``(source_file, module, name)`` triples one module imports.

    Only ``from cadrumo.X import Y`` (absolute) and relative imports
    resolving back into the ``cadrumo.*`` tree are returned. ``import *``
    statements are excluded — they don't pin a specific name and the
    no-wildcard hygiene is a separate concern.
    """
    for node in _walk_import_from(tree):
        resolved = _resolve_relative_module(source, node.level, node.module) if node.level > 0 else node.module
        if not (resolved is not None and resolved) or not resolved.startswith("cadrumo"):
            continue
        for alias in node.names:
            if alias.name != "*":
                yield (source, resolved, alias.name)


class _ImportScan(NamedTuple):
    """Everything the gate needs from the package's trees, which are not retained."""

    triples: tuple[tuple[Path, str, str], ...]
    bound_names: Mapping[Path, frozenset[str]]


@pytest.fixture(scope="module")
def cadrumo_import_scan() -> _ImportScan:
    """Parse the package once, reading imports and bound names from each tree.

    Imports and bindings live in the same files, so reading them in two passes
    parsed the package twice. A module whose text held an undecodable byte is left
    out of the bindings, so that its binding lookup still takes the strict read.
    """
    triples: list[tuple[Path, str, str]] = []
    bound_names: dict[Path, frozenset[str]] = {}
    for source, text, tree in iter_parsed_sources(package_python_files()):
        triples.extend(_import_triples(source, tree))
        if "\ufffd" not in text:
            bound_names[source] = _bound_names(tree)
    return _ImportScan(tuple(triples), bound_names)


def _check_triple(triple: tuple[Path, str, str], bound_names: Mapping[Path, frozenset[str]]) -> str | None:
    """Return None when the triple resolves, or a one-line failure description otherwise.

    Two Python resolution paths are modeled: (a) ``name`` is bound as an
    attribute on the target module, or (b) ``name`` is a submodule importable
    as ``{module}.{name}``
    (the ``from pkg import mod`` shape Python resolves lazily). The
    This check accepts both solely to detect broken runtime imports; it does
    not authorize package forwarding or re-export ownership.
    """
    source, module, name = triple
    target_path = _module_source_path(module)
    if target_path is None:
        return (
            f"{source.relative_to(SRC_CADRUMO.parent).as_posix()}::{module}::{name}  (target module is not importable)"
        )
    if name in (bound_names.get(target_path) or _source_bound_names(target_path)):
        return None
    # Submodule import path — ``from pkg import mod`` succeeds if
    # ``pkg.mod`` is a real importable module, regardless of whether
    # ``pkg.__init__`` binds ``mod`` as an attribute.
    if _module_source_path(f"{module}.{name}") is not None:
        return None
    return f"{source.relative_to(SRC_CADRUMO.parent).as_posix()}::{module}::{name}"


@cache
def _module_source_path(module: str) -> Path | None:
    """Return an importable module's source without executing its module body.

    Cached because the scan asks about the same target modules once per
    imported name, tens of thousands of times.
    """
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
    for node in iter_statements(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Import):
            names.update(alias.asname or alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names if alias.name != "*")
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                # Unpacking binds every name in the target tuple or list.
                names.update(element.id for element in ast.walk(target) if isinstance(element, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.TypeAlias):
            names.add(node.name.id)
    return frozenset(names)


@cache
def _source_bound_names(path: Path) -> frozenset[str]:
    """Parse one target module the package scan did not cover, once."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError):
        return frozenset[str]()
    return _bound_names(tree)


def test_cadrumo_cross_module_imports_resolve(
    cadrumo_import_scan: _ImportScan,
) -> None:
    """Every runtime ``from cadrumo.X import Y`` triple resolves."""
    failures: list[str] = []
    for triple in cadrumo_import_scan.triples:
        failure = _check_triple(triple, cadrumo_import_scan.bound_names)
        if failure is not None:
            failures.append(failure)
    assert not failures, "\nBroken cross-module imports:\n" + "\n".join(sorted(failures))
