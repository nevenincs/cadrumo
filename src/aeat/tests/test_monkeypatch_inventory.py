"""Static guard: no monkeypatch use in production tests.

Walks every ``test_*.py`` and ``_test_*.py`` module under ``src/aeat/`` via AST
and rejects pytest ``monkeypatch`` fixture arguments, mutation calls, and
explicit ``pytest.MonkeyPatch`` contexts. Process-global isolation should use
local context managers or injectable runtime boundaries instead.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path

import pytest

from ._inventory import ast_for_path, discover_test_modules, qualified_name, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_MUTATION_VERBS = frozenset({"setattr", "setitem", "delattr", "setenv", "delenv", "chdir", "syspath_prepend"})
_PATCH_CONTEXT_FACTORIES = frozenset(
    {
        "pytest.MonkeyPatch",
        "pytest.MonkeyPatch.context",
        "MonkeyPatch",
        "MonkeyPatch.context",
    },
)


def _target_name_from_args(call_node: ast.Call) -> str | None:
    """Extract the target name from a monkeypatch mutation call.

    Handles both ``monkeypatch.setattr(module, "name", value)`` (positional)
    and single-value forms such as ``monkeypatch.setenv("NAME", value)``.
    """
    args = call_node.args
    if not args:
        return None
    first = args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        # String-path form: "sys.stdout", "pkg.module.name"
        return first.value.split(".")[-1]
    if len(args) >= 2:
        second = args[1]
        if isinstance(second, ast.Constant) and isinstance(second.value, str):
            return second.value
    return None


def _mutation_sites(
    tree: ast.AST,
) -> list[tuple[int, str, str | None]]:
    """Return ``(lineno, method, target)`` for monkeypatch mutation calls in *tree*."""
    hits: list[tuple[int, str, str | None]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue
        if func.attr not in _MUTATION_VERBS:
            continue
        caller = func.value
        if not (isinstance(caller, ast.Name) and caller.id == "monkeypatch"):
            continue
        target = _target_name_from_args(node)
        hits.append((node.lineno, func.attr, target))
    return hits


def _explicit_patch_context_sites(tree: ast.AST) -> list[tuple[int, str]]:
    """Return explicit ``pytest.MonkeyPatch`` factory/context calls."""
    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = qualified_name(node.func)
        if name in _PATCH_CONTEXT_FACTORIES:
            hits.append((node.lineno, name))
    return hits


def _monkeypatch_reference_sites(tree: ast.AST) -> list[tuple[int, str]]:
    """Return explicit monkeypatch fixture/type/name references in *tree*."""
    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.arg) and node.arg == "monkeypatch":
            hits.append((node.lineno, "argument monkeypatch"))
        elif isinstance(node, ast.Name) and node.id == "monkeypatch":
            hits.append((node.lineno, "name monkeypatch"))
        elif isinstance(node, ast.Attribute) and qualified_name(node) in {"pytest.MonkeyPatch", "MonkeyPatch"}:
            hits.append((node.lineno, qualified_name(node)))
    return hits


def test_no_monkeypatch_fixture_or_context_usage(
    source_tree_ast: Mapping[Path, ast.AST],
) -> None:
    """No deterministic production test may use pytest monkeypatch machinery.

    Consumes the session-scoped AST cache; falls back to per-file parse
    for modules absent from the cache.
    """
    modules = discover_test_modules()
    violations: list[str] = []

    for module_path in modules:
        relative = repo_relative(module_path)
        tree = ast_for_path(module_path, source_tree_ast)
        if tree is None:
            continue
        for lineno, method, target in _mutation_sites(tree):
            violations.append(f"{relative}:{lineno}: monkeypatch.{method}(target={target!r})")
        for lineno, name in _explicit_patch_context_sites(tree):
            violations.append(f"{relative}:{lineno}: {name}()")
        for lineno, name in _monkeypatch_reference_sites(tree):
            violations.append(f"{relative}:{lineno}: {name}")

    assert not violations, "Monkeypatch machinery found in deterministic production tests:\n" + "\n".join(violations)


def test_discovery_found_modules() -> None:
    """Guardrail: the discovery walk must find at least one test module."""
    modules = discover_test_modules()
    assert modules, "No test modules discovered — check glob roots."
