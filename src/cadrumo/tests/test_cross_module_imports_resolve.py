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
import importlib
from collections.abc import Iterator, Mapping
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
    try:
        target = importlib.import_module(module)
    except ImportError as exc:
        return (
            f"{source.relative_to(SRC_CADRUMO.parent).as_posix()}::{module}::{name}  "
            f"(target module raised ImportError: {exc})"
        )
    if hasattr(target, name):
        return None
    # Submodule import path — ``from pkg import mod`` succeeds if
    # ``pkg.mod`` is a real importable module, regardless of whether
    # ``pkg.__init__`` binds ``mod`` as an attribute.
    try:
        importlib.import_module(f"{module}.{name}")
        return None
    except ImportError:
        pass
    return f"{source.relative_to(SRC_CADRUMO.parent).as_posix()}::{module}::{name}"


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
