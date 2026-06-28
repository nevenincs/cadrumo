"""Static guard: forbidden test-control inventory for production tests.

Walks every deterministic test, test-support, and ``conftest.py`` module under
``src/aeat/`` via AST and classifies each ``unittest`` / ``mock`` /
``pytest_mock`` import plus locally defined classes/functions named like test
doubles.

Classification rule:
- Any mock import under deterministic production tests is drift.
- Any locally defined ``Fake*``, ``Stub*``, or ``Dummy*`` test helper is drift;
  tests must name helpers by the concrete behaviour or contract they exercise.

Current inventory for durable replacement:
  Zero ``unittest``, ``mock``, or ``pytest_mock`` imports found in deterministic
  tests, test-support modules, or conftests under ``src/aeat/``.  The codebase
  uses constructor injection with inline callables for boundary-injection sites
  rather than the mock library. Zero locally defined fake/stub/dummy helper
  classes or functions.

The tests assert that neither mock imports nor test-double definitions appear.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path

import pytest

from ._inventory import ast_for_path, discover_test_control_modules, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# Import module names that constitute banned test-control usage.
_FORBIDDEN_TEST_CONTROL_IMPORTS = ("unittest.mock", "unittest", "mock", "pytest_mock")
_FORBIDDEN_TEST_DOUBLE_PREFIXES = ("fake", "stub", "dummy")


def _forbidden_test_control_imports(
    tree: ast.AST,
) -> list[tuple[int, str]]:
    """Return ``(lineno, module)`` for every banned test-control import in *tree*."""
    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                hit = _forbidden_import_name(alias.name)
                if hit is not None:
                    hits.append((node.lineno, hit))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "unittest" and any(alias.name == "mock" for alias in node.names):
                hits.append((node.lineno, "unittest.mock"))
                continue
            hit = _forbidden_import_name(module)
            if hit is not None:
                hits.append((node.lineno, hit))
    return hits


def _forbidden_import_name(import_name: str) -> str | None:
    """Return the banned import prefix matched by *import_name*, if any."""
    for prefix in _FORBIDDEN_TEST_CONTROL_IMPORTS:
        if import_name == prefix or import_name.startswith(prefix + "."):
            return prefix
    return None


def _forbidden_test_double_definitions(tree: ast.AST) -> list[tuple[int, str]]:
    """Return ``(lineno, name)`` for locally defined fake/stub/dummy helpers."""
    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) and _is_test_double_name(node.name):
            hits.append((node.lineno, node.name))
    return hits


def _is_test_double_name(name: str) -> bool:
    """Return True for helper names that encode fake/stub/dummy semantics."""
    normalized = name.lstrip("_").lower()
    return any(normalized.startswith(prefix) for prefix in _FORBIDDEN_TEST_DOUBLE_PREFIXES)


def test_no_mock_imports(
    source_tree_ast: Mapping[Path, ast.AST],
) -> None:
    """No deterministic production test may import mock libraries.

    Consumes the session-scoped AST cache; falls back to per-file parse
    for modules absent from the cache (e.g. unparseable files).
    """
    modules = discover_test_control_modules()
    violations: list[str] = []

    for module_path in modules:
        relative = repo_relative(module_path)
        tree = ast_for_path(module_path, source_tree_ast)
        if tree is None:
            continue
        for lineno, mock_module in _forbidden_test_control_imports(tree):
            violations.append(f"{relative}:{lineno}: import {mock_module}")

    assert not violations, "Banned test-control imports found (remove mock-library usage):\n" + "\n".join(violations)


def test_no_fake_stub_or_dummy_definitions(
    source_tree_ast: Mapping[Path, ast.AST],
) -> None:
    """No deterministic production test may define fake/stub/dummy helpers."""
    modules = discover_test_control_modules()
    violations: list[str] = []

    for module_path in modules:
        relative = repo_relative(module_path)
        tree = ast_for_path(module_path, source_tree_ast)
        if tree is None:
            continue
        for lineno, name in _forbidden_test_double_definitions(tree):
            violations.append(f"{relative}:{lineno}: {name}")

    assert not violations, "Banned fake/stub/dummy test helper definitions found:\n" + "\n".join(violations)


def test_discovery_found_modules() -> None:
    """Guardrail: the discovery walk must find at least one test module."""
    modules = discover_test_control_modules()
    assert modules, "No test modules discovered — check glob roots."
