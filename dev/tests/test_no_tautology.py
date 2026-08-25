"""Static guard: zero tautological assertions in production tests.

Walks every deterministic test, test-support, and ``conftest.py`` module under
``src/cadrumo/`` via AST and asserts that none contain assertions that are
structurally guaranteed to pass regardless of the code under test.

Tautological patterns detected:
- ``assert True`` / ``assert 1`` / ``assert "x"`` — truthy constants.
- ``assert not False`` / ``assert not None`` — negated falsey constants.
- ``assert [x]`` / ``assert not []`` — literal container truthiness.
- ``assert 1 == 1`` / ``assert "x" == "x"`` — equal constants.
- ``assert 1 != 2`` / ``assert "x" != "y"`` — unequal constants.
- ``assert x == x`` / ``assert x is x`` — identical name on both sides.
- ``assert x in (x,)`` / ``assert x not in ()`` — guaranteed membership results.

Explicitly NOT treated as tautological:
- ``assert False, message`` — intentional unconditional failure idiom
  (equivalent to ``pytest.fail(message)``).
- ``assert x == x.lower()`` / ``assert x == x.strip()`` — the right-hand side
  applies a transform; these are valid property assertions.
- ``assert x is not None`` — meaningful null guard.
- ``assert x`` — meaningful truthiness check on a computed value.

behavior contract enumeration result: zero tautological assertions found in the current
deterministic test-control surface. The test asserts this inventory stays at zero.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path

import pytest

from cadrumo.core.logging import get_logger
from cadrumo.tests import ast_for_path, repo_relative

from ._project_inventory import all_test_control_modules

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_logger = get_logger(__name__)


def _is_tautological_assert(node: ast.AST) -> bool:
    """Return True if *node* is a structurally guaranteed-to-pass assertion.

    Detects:
    - ``assert <truthy constant>``.
    - ``assert not <falsey constant>``.
    - literal container truthiness such as ``assert [value]`` and ``assert not []``.
    - ``assert <constant> == <same constant>``.
    - ``assert <constant> != <different constant>``.
    - ``assert <name> == <name>`` and ``assert <name> is <name>``.

    Does NOT flag:
    - ``assert False, msg`` — intentional unconditional failure.
    - ``assert x == x.method()`` — right-hand side applies a transform.
    """
    if not isinstance(node, ast.Assert):
        return False
    test = node.test

    if _literal_truthiness(test) is True or _is_not_literal_falsey(test) or _is_tautological_boolop(test):
        return True

    if isinstance(test, ast.Compare):
        if _is_tautological_compare_chain(test):
            return True
        if len(test.ops) != 1:
            return False
        left = test.left
        right = test.comparators[0]
        if _is_tautological_membership(left, test.ops[0], right):
            return True

    return False


def _literal_truthiness(node: ast.AST) -> bool | None:
    """Return known literal truthiness, or ``None`` when it depends on runtime values."""
    if isinstance(node, ast.Constant):
        return bool(node.value)
    if isinstance(node, ast.Tuple | ast.List | ast.Set):
        return bool(node.elts)
    if isinstance(node, ast.Dict):
        return bool(node.keys)
    return None


def _is_singleton_constant(node: ast.AST) -> bool:
    """Return True for the constants whose identity semantics are language-defined."""
    return isinstance(node, ast.Constant) and (node.value is None or node.value is True or node.value is False)


def _is_not_literal_falsey(node: ast.AST) -> bool:
    """Return True for ``not`` applied to a literal known to be falsey."""
    return isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not) and _literal_truthiness(node.operand) is False


def _is_tautological_boolop(node: ast.AST) -> bool:
    """Return True when a boolean expression is structurally guaranteed truthy."""
    if not isinstance(node, ast.BoolOp):
        return False
    truthiness = tuple(_literal_truthiness(value) for value in node.values)
    if isinstance(node.op, ast.Or):
        return any(value is True for value in truthiness)
    return isinstance(node.op, ast.And) and all(value is True for value in truthiness)


def _is_tautological_compare(left: ast.expr, op: ast.cmpop, right: ast.expr) -> bool:
    """Return True for one structurally guaranteed-pass comparison."""
    if isinstance(left, ast.Constant) and isinstance(right, ast.Constant):
        if isinstance(op, ast.Eq):
            return left.value == right.value
        if isinstance(op, ast.NotEq):
            return left.value != right.value
        if isinstance(op, ast.Is) and _is_singleton_constant(left) and _is_singleton_constant(right):
            return left.value is right.value
        if isinstance(op, ast.IsNot) and _is_singleton_constant(left) and _is_singleton_constant(right):
            return left.value is not right.value

    if isinstance(left, ast.Name) and isinstance(right, ast.Name) and left.id == right.id:
        return isinstance(op, ast.Eq | ast.Is)

    return False


def _is_tautological_compare_chain(node: ast.Compare) -> bool:
    """Return True when every adjacent comparison is guaranteed to pass."""
    lefts = [node.left, *node.comparators[:-1]]
    return all(
        _is_tautological_compare(left, op, right)
        for left, op, right in zip(lefts, node.ops, node.comparators, strict=True)
    )


def _is_tautological_membership(left: ast.expr, op: ast.cmpop, right: ast.expr) -> bool:
    """Return True for structurally guaranteed-pass literal membership checks."""
    if isinstance(op, ast.NotIn) and _literal_truthiness(right) is False:
        return True
    if not isinstance(op, ast.In) or not isinstance(right, ast.Tuple | ast.List | ast.Set):
        return False
    return any(_same_simple_expression(left, element) for element in right.elts)


def _same_simple_expression(left: ast.expr, right: ast.expr) -> bool:
    """Return True when two simple AST expressions are structurally identical."""
    if isinstance(left, ast.Name) and isinstance(right, ast.Name):
        return left.id == right.id
    if isinstance(left, ast.Constant) and isinstance(right, ast.Constant):
        return left.value == right.value
    return False


def _tautological_sites(
    path: Path,
    tree: ast.AST,
) -> list[tuple[int, str]]:
    """Return ``(lineno, snippet)`` for every tautological assertion in *path*.

    Accepts the cached ``ast.AST`` for *path* and reads raw text only to render
    snippets for the violation message.
    """
    hit_linenos = [
        node.lineno for node in ast.walk(tree) if isinstance(node, ast.Assert) and _is_tautological_assert(node)
    ]
    if not hit_linenos:
        return []

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []

    hits: list[tuple[int, str]] = []
    for lineno in hit_linenos:
        snippet = lines[lineno - 1].strip() if lineno <= len(lines) else "<unknown>"
        hits.append((lineno, snippet))
        _logger.warning(
            "tautological assertion detected: %s:%d %s",
            repo_relative(path),
            lineno,
            snippet,
        )
    return hits


def test_no_tautological_assertions(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """No deterministic test-control module may contain tautological assertions.

    Uses the shared test-control module inventory so the existing fixtures-dir
    exclusion stays intact. The session AST cache amortises parse cost for the
    ``src/cadrumo`` test-control surface; project-level test controls outside that
    tree still fall back to per-path parsing.
    """
    modules = all_test_control_modules()
    violations: list[str] = []

    for module_path in modules:
        relative = repo_relative(module_path)
        tree = ast_for_path(module_path, source_tree_ast)
        if tree is None:
            continue
        for lineno, snippet in _tautological_sites(module_path, tree):
            violations.append(f"{relative}:{lineno}: {snippet}")

    assert not violations, (
        "Tautological assertions found (replace with real behaviour assertions or remove):\n" + "\n".join(violations)
    )


def test_detection_is_non_trivial() -> None:
    """Anti-tautology proof: _is_tautological_assert must correctly classify known shapes.

    This test verifies the detector is not trivially bypassed by confirming it
    flags known-tautological AST nodes and clears known-non-tautological ones.
    """
    flagged = [
        "assert True",
        "assert 1",
        'assert "x"',
        "assert [x]",
        "assert (x,)",
        "assert {x}",
        "assert {'x': value}",
        "assert not False",
        "assert not None",
        "assert not []",
        "assert not ()",
        "assert not {}",
        "assert 1 == 1",
        'assert "x" == "x"',
        "assert 1 != 2",
        'assert "x" != "y"',
        "assert None is None",
        "assert True is not False",
        "assert x == x",
        "assert x is x",
        "assert 1 == 1 == 1",
        "assert 1 != 2 != 1",
        "assert x == x == x",
        "assert True or x",
        'assert x or "fallback"',
        'assert True and 1 and "x"',
        "assert x in (x,)",
        "assert x in [x]",
        "assert x in {x}",
        "assert 'x' in ('x',)",
        "assert x not in ()",
        "assert x not in []",
        "assert x not in {}",
    ]
    not_flagged = [
        "assert False, 'msg'",
        "assert 0",
        "assert not True",
        "assert []",
        "assert not [x]",
        "assert x == x.lower()",
        "assert x == x.strip()",
        "assert x is not None",
        "assert x is y",
        'assert "x" is "x"',
        "assert x",
        "assert x == y",
        "assert x != x",
        "assert x == x == y",
        "assert x != y != x",
        "assert x or y",
        "assert True and x",
        "assert x and 1",
        'assert "x" in haystack or "y" in haystack',
        "assert len(x) == len(y)",
        "assert x in [y]",
        "assert x in values",
        "assert x not in {y}",
        "assert x not in blocked_values",
    ]

    for src in flagged:
        tree = ast.parse(src)
        stmt = tree.body[0]
        assert _is_tautological_assert(stmt), f"Expected tautology detected for: {src!r}"

    for src in not_flagged:
        tree = ast.parse(src)
        stmt = tree.body[0]
        assert not _is_tautological_assert(stmt), f"False positive tautology for: {src!r}"


def test_discovery_found_modules() -> None:
    """Guardrail: the discovery walk must find at least one test module."""
    modules = all_test_control_modules()
    assert modules, "No test modules discovered — check glob roots."
