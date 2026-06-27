"""Static guard: zero tautological assertions in production tests.

Walks every ``test_*.py`` and ``_test_*.py`` module under ``src/aeat/`` via AST
and asserts that none contain assertions that are structurally guaranteed to
pass regardless of the code under test.

Tautological patterns detected:
- ``assert True`` — always passes, asserts nothing about production behaviour.
- ``assert 1 == 1`` / ``assert "x" == "x"`` — same constant on both sides.
- ``assert x == x`` — identical name on both sides without any transform.

Explicitly NOT treated as tautological:
- ``assert False, message`` — intentional unconditional failure idiom
  (equivalent to ``pytest.fail(message)``).
- ``assert x == x.lower()`` / ``assert x == x.strip()`` — the right-hand side
  applies a transform; these are valid property assertions.
- ``assert x is not None`` — meaningful null guard.
- ``assert x`` — meaningful truthiness check on a computed value.

behavior contract enumeration result: zero tautological assertions found in the current
production test surface.  The test asserts this inventory stays at zero.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path

import pytest

from ..core.logging import get_logger
from ._inventory import ast_for_path, discover_test_modules, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_logger = get_logger(__name__)


def _is_tautological_assert(node: ast.AST) -> bool:
    """Return True if *node* is a structurally guaranteed-to-pass assertion.

    Detects:
    - ``assert True`` (the ``True`` boolean singleton, not a variable).
    - ``assert <literal> == <same literal>`` (same constant on both sides).
    - ``assert <name> == <name>`` (identical identifier, no transform).

    Does NOT flag:
    - ``assert False, msg`` — intentional unconditional failure.
    - ``assert x == x.method()`` — right-hand side applies a transform.
    """
    if not isinstance(node, ast.Assert):
        return False
    test = node.test

    # assert True  (the constant singleton True — always passes)
    if isinstance(test, ast.Constant) and test.value is True:
        return True

    if isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.ops[0], ast.Eq):
        left = test.left
        right = test.comparators[0]
        # assert <constant> == <same constant>
        if isinstance(left, ast.Constant) and isinstance(right, ast.Constant) and left.value == right.value:
            return True
        # assert <name> == <name>  (no method call on either side)
        if isinstance(left, ast.Name) and isinstance(right, ast.Name) and left.id == right.id:
            return True

    return False


def _tautological_sites(
    path: Path,
    tree: ast.AST,
) -> list[tuple[int, str]]:
    """Return ``(lineno, snippet)`` for every tautological assertion in *path*.

    Accepts the cached ``ast.AST`` for *path* from the session fixture
    rather than parsing the file again. Reads the file's raw text only
    to render snippets for the violation message.
    """
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []

    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if _is_tautological_assert(node):
            assert isinstance(node, ast.Assert)
            lineno = node.lineno
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
    """No production test module may contain structurally tautological assertions.

    Consumes the session-scoped ``source_tree_ast`` cache for the parsed
    AST and uses :func:`_discover_test_modules` as the per-test filter
    so the existing fixtures-dir exclusion stays intact. Modules absent
    from the cache (e.g. files that failed to parse at fixture-build
    time) fall back to a per-test ``ast.parse`` so the ratchet remains
    truthful for malformed files.
    """
    modules = discover_test_modules()
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
        "assert 1 == 1",
        'assert "x" == "x"',
        "assert x == x",
    ]
    not_flagged = [
        "assert False, 'msg'",
        "assert x == x.lower()",
        "assert x == x.strip()",
        "assert x is not None",
        "assert x",
        "assert x == y",
        "assert len(x) == len(y)",
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
    modules = discover_test_modules()
    assert modules, "No test modules discovered — check glob roots."
