"""Static guard: zero skip / xfail shortcuts in deterministic production tests.

Walks every ``test_*.py`` and ``_test_*.py`` module under ``src/aeat/`` via AST
and asserts that deterministic modules carry no ``pytest.mark.skip``,
``pytest.mark.skipif``, ``pytest.mark.xfail``, ``pytest.skip()``, or
``pytest.xfail()`` shortcuts.

Live modules may use ``pytest.skip()`` only after carrying the ``aeat_live``
execution marker; deterministic unit tests have no skip / xfail exception set.
No item may carry both ``unit`` and ``aeat_live`` markers.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path

import pytest

from ._inventory import ast_for_path, discover_test_modules, qualified_name, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_FORBIDDEN_MARKERS = frozenset({"skip", "skipif", "xfail"})
_FORBIDDEN_CALLS = frozenset({"pytest.skip", "pytest.xfail"})
_LIVE_EXECUTION_MARKER = "aeat_live"
_UNIT_EXECUTION_MARKER = "unit"


def _forbidden_marker_sites(tree: ast.AST) -> list[tuple[int, str]]:
    """Return ``(lineno, marker_or_call_name)`` for every forbidden shortcut in *tree*."""
    live_module = _LIVE_EXECUTION_MARKER in _module_execution_markers(tree)
    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        decorators: list[ast.expr] = []
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            decorators = node.decorator_list

        for dec in decorators:
            # Accept both ``@pytest.mark.skip`` and ``@pytest.mark.skip(...)``
            attr_chain = dec.func if isinstance(dec, ast.Call) else dec
            if not isinstance(attr_chain, ast.Attribute):
                continue
            if attr_chain.attr not in _FORBIDDEN_MARKERS:
                continue
            mark_attr = attr_chain.value
            if not isinstance(mark_attr, ast.Attribute) or mark_attr.attr != "mark":
                continue
            mark_root = mark_attr.value
            if not isinstance(mark_root, ast.Name) or mark_root.id != "pytest":
                continue
            hits.append((dec.lineno, f"pytest.mark.{attr_chain.attr}"))

        if isinstance(node, ast.Call):
            call_name = qualified_name(node.func)
            if call_name not in _FORBIDDEN_CALLS:
                continue
            if call_name == "pytest.skip" and live_module:
                continue
            hits.append((node.lineno, call_name))
    return hits


def _module_execution_markers(tree: ast.AST) -> set[str]:
    """Return module-level execution markers from a ``pytestmark = [...]`` assignment."""
    markers: set[str] = set()
    body = tree.body if isinstance(tree, ast.Module) else ()
    for node in body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "pytestmark" for target in node.targets):
            continue
        values: list[ast.expr] = list(node.value.elts) if isinstance(node.value, ast.List | ast.Tuple) else [node.value]
        for value in values:
            name = qualified_name(value)
            if name.startswith("pytest.mark."):
                markers.add(name.removeprefix("pytest.mark."))
    return markers


def _decorator_execution_markers(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> set[str]:
    """Return pytest execution marker names attached directly to a test item."""
    markers: set[str] = set()
    for decorator in node.decorator_list:
        name = qualified_name(decorator)
        if name.startswith("pytest.mark."):
            markers.add(name.removeprefix("pytest.mark."))
    return markers


def _unit_live_marker_intersections(tree: ast.AST) -> list[tuple[int, str]]:
    """Return ``(lineno, item_name)`` for tests marked as both unit and live."""
    module_markers = _module_execution_markers(tree)
    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue
        markers = module_markers | _decorator_execution_markers(node)
        if {_UNIT_EXECUTION_MARKER, _LIVE_EXECUTION_MARKER} <= markers:
            hits.append((node.lineno, node.name))
    return hits


def test_no_skip_or_xfail_shortcuts(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Deterministic production test modules must not use skip / xfail shortcuts."""
    modules = discover_test_modules()
    violations: list[str] = []

    for module_path in modules:
        relative = repo_relative(module_path)
        tree = ast_for_path(module_path, source_tree_ast)
        if tree is None:
            continue
        sites = _forbidden_marker_sites(tree)
        for lineno, marker_or_call_name in sites:
            violations.append(f"{relative}:{lineno}: {marker_or_call_name}")

    assert not violations, (
        "Undocumented pytest skip / xfail shortcuts found "
        "(remove the shortcut or mark the module aeat_live when it is genuinely live-only):\n" + "\n".join(violations)
    )


def test_unit_tests_are_not_live_gated(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Unit tests must not also carry the live opt-in marker."""
    modules = discover_test_modules()
    violations: list[str] = []

    for module_path in modules:
        relative = repo_relative(module_path)
        tree = ast_for_path(module_path, source_tree_ast)
        if tree is None:
            continue
        for lineno, item_name in _unit_live_marker_intersections(tree):
            violations.append(f"{relative}:{lineno}: {item_name}")

    assert not violations, "Tests cannot be marked both unit and aeat_live:\n" + "\n".join(violations)


def test_discovery_found_modules() -> None:
    """Guardrail: the discovery walk must find at least one test module."""
    modules = discover_test_modules()
    assert modules, "No test modules discovered — check glob roots."
