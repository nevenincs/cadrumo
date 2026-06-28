"""Static guard: no broad exception assertions in production tests."""

from __future__ import annotations

import ast
import tokenize
from collections.abc import Mapping
from io import StringIO
from pathlib import Path

import pytest

from ._inventory import ast_for_path, discover_test_control_modules, qualified_name, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_BROAD_EXCEPTION_NAMES = frozenset(
    {
        "BaseException",
        "Exception",
        "builtins.BaseException",
        "builtins.Exception",
    },
)
_NOQA_TOKEN = "no" + "qa"
_BROAD_RAISES_RULE = "B" + "017"


def _broad_pytest_raises_sites(tree: ast.AST) -> list[int]:
    """Return line numbers where ``pytest.raises`` catches a broad exception root."""
    hits: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if qualified_name(node.func) != "pytest.raises" or not node.args:
            continue
        if _contains_broad_exception_root(node.args[0]):
            hits.append(node.lineno)
    return hits


def _contains_broad_exception_root(node: ast.AST) -> bool:
    """Return True when *node* names Exception/BaseException directly or in a union container."""
    name = qualified_name(node)
    if name in _BROAD_EXCEPTION_NAMES:
        return True
    if isinstance(node, ast.Tuple | ast.List | ast.Set):
        return any(_contains_broad_exception_root(element) for element in node.elts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _contains_broad_exception_root(node.left) or _contains_broad_exception_root(node.right)
    return False


def _b017_suppression_lines(path: Path) -> list[int]:
    """Return source line numbers carrying a broad-raise lint suppression."""
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return [
        token.start[0]
        for token in tokenize.generate_tokens(StringIO(source).readline)
        if token.type == tokenize.COMMENT and _NOQA_TOKEN in token.string and _BROAD_RAISES_RULE in token.string
    ]


def test_no_broad_pytest_raises(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Tests must assert the concrete exception contract they expect."""
    violations: list[str] = []

    for module_path in discover_test_control_modules():
        relative = repo_relative(module_path)
        tree = ast_for_path(module_path, source_tree_ast)
        if tree is None:
            continue
        for lineno in _broad_pytest_raises_sites(tree):
            violations.append(f"{relative}:{lineno}: pytest.raises catches Exception/BaseException")

    assert not violations, "Broad pytest.raises exception assertions found:\n" + "\n".join(violations)


def test_no_broad_raise_suppressions() -> None:
    """Broad-raise lint suppressions must not hide permissive exception contracts."""
    violations: list[str] = []

    for module_path in discover_test_control_modules():
        relative = repo_relative(module_path)
        for lineno in _b017_suppression_lines(module_path):
            violations.append(f"{relative}:{lineno}: {_NOQA_TOKEN} {_BROAD_RAISES_RULE}")

    assert not violations, "Broad exception assertion suppressions found:\n" + "\n".join(violations)


def test_discovery_found_modules() -> None:
    """Guardrail: the discovery walk must find at least one test/control module."""
    modules = discover_test_control_modules()
    assert modules, "No test/control modules discovered -- check glob roots."
