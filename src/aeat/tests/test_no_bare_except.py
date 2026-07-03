"""Structural gate: no bare-except patterns in the test surface.

A bare ``except:`` (no exception class) silently swallows every exception
including ``KeyboardInterrupt``, ``SystemExit``, and assertion errors
themselves.  ``except Exception: pass`` and aliased broad variants are equally
opaque when the body is only a no-op statement — they mask real failures and
defeat the quality-gate purpose of the test.

This test walks every ``test_*.py`` file under ``src/aeat/``,
parses the AST, and fails if it finds either shape.  Adding a bare
``except`` to a test file is blocked immediately by the CI gate;
the fix is always to replace it with a specific exception assertion.

The enumeration also covers
:mod:`aeat.entrypoints.cli.test_stdio` to confirm no workaround
for the behavior contract stream-reconfigure tests landed there.
"""

from __future__ import annotations

import ast
from typing import NamedTuple

import pytest

from ._inventory import ast_for_path, discover_test_modules, project_test_control_modules, qualified_name, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_BROAD_EXCEPTION_NAMES = frozenset(
    {
        "BaseException",
        "Exception",
        "builtins.BaseException",
        "builtins.Exception",
    },
)


class _BareExceptInventory(NamedTuple):
    broad_names: set[str]
    try_nodes: list[ast.Try]


def _bare_except_locations() -> list[tuple[str, int, str]]:
    """Return (file, lineno, shape) for every bare-except in test files.

    Uses the shared test-module inventory so fixtures stay outside this ratchet.
    """
    findings: list[tuple[str, int, str]] = []
    for path in sorted(set(discover_test_modules()) | set(project_test_control_modules())):
        tree = ast_for_path(path)
        if tree is None:
            continue
        findings.extend(_bare_except_locations_for_tree(repo_relative(path), tree))
    return findings


def _bare_except_locations_for_tree(display_path: str, tree: ast.AST) -> list[tuple[str, int, str]]:
    """Return no-op broad exception handlers from a parsed test module."""
    inventory = _bare_except_inventory(tree)
    findings: list[tuple[str, int, str]] = []
    for node in inventory.try_nodes:
        for handler in node.handlers:
            if handler.type is None:
                findings.append((display_path, handler.lineno, "bare except:"))
            elif _contains_broad_exception_root(handler.type, inventory.broad_names) and _is_noop_handler_body(
                handler.body
            ):
                handler_name = qualified_name(handler.type) or "broad exception"
                findings.append((display_path, handler.lineno, f"except {handler_name}: pass"))
    return findings


def _broad_exception_names(tree: ast.AST) -> set[str]:
    """Return local names that resolve to Exception/BaseException."""
    return _bare_except_inventory(tree).broad_names


def _bare_except_inventory(tree: ast.AST) -> _BareExceptInventory:
    """Collect broad exception aliases and try blocks with one AST walk."""
    names = set(_BROAD_EXCEPTION_NAMES)
    alias_assignments: list[tuple[str, tuple[str, ...]]] = []
    try_nodes: list[ast.Try] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            try_nodes.append(node)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "builtins":
                    root = alias.asname or alias.name
                    names.add(f"{root}.BaseException")
                    names.add(f"{root}.Exception")
        elif isinstance(node, ast.ImportFrom) and node.module == "builtins":
            for alias in node.names:
                if alias.name in {"BaseException", "Exception"}:
                    names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Assign):
            target_names = tuple(target.id for target in node.targets if isinstance(target, ast.Name))
            if target_names:
                alias_assignments.append((qualified_name(node.value), target_names))
        elif isinstance(node, ast.AnnAssign) and node.value is not None and isinstance(node.target, ast.Name):
            alias_assignments.append((qualified_name(node.value), (node.target.id,)))

    changed = True
    while changed:
        changed = False
        for value_name, target_names in alias_assignments:
            if value_name not in names:
                continue
            for target_name in target_names:
                if target_name not in names:
                    names.add(target_name)
                    changed = True
    return _BareExceptInventory(broad_names=names, try_nodes=try_nodes)


def _contains_broad_exception_root(node: ast.AST, broad_names: set[str]) -> bool:
    """Return True when an except handler names a broad exception root."""
    if qualified_name(node) in broad_names:
        return True
    if isinstance(node, ast.Tuple):
        return any(_contains_broad_exception_root(element, broad_names) for element in node.elts)
    return False


def _is_noop_handler_body(body: list[ast.stmt]) -> bool:
    """Return True when an exception handler body does no work."""
    return len(body) == 1 and (
        isinstance(body[0], ast.Pass)
        or (
            isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and body[0].value.value in {None, Ellipsis}
        )
    )


def test_no_bare_except_in_test_surface() -> None:
    """Zero bare-except or ``except Exception: pass`` shapes in test files.

    Every test file under ``src/aeat/`` is parsed with the standard AST
    module; no subprocess, no mock, no skip.  Failures name the exact
    file and line number so the author can replace the bare handler with
    a specific exception assertion.

    Uses the shared per-file AST cache so the parse cost is amortised across
    the full ratchet suite.
    """
    findings = _bare_except_locations()

    if findings:
        lines = "\n".join(f"  {path}:{lineno}  [{shape}]" for path, lineno, shape in findings)
        raise AssertionError(
            f"Found {len(findings)} bare-except pattern(s) in test surface:\n{lines}\n"
            "Replace each with a specific exception assertion or a documented "
            "controlled-failure helper.",
        )


def test_detector_rejects_alias_noop_broad_exception_handlers() -> None:
    """Aliased broad no-op handlers must not bypass the structural gate."""
    tree = ast.parse(
        """
import builtins as py_builtins
from builtins import Exception as BroadException

AliasedException = BroadException

try:
    raise RuntimeError("boom")
except:
    pass

try:
    raise RuntimeError("boom")
except py_builtins.BaseException:
    ...

try:
    raise RuntimeError("boom")
except (ValueError, AliasedException):
    None
"""
    )

    assert [shape for _, _, shape in _bare_except_locations_for_tree("snippet.py", tree)] == [
        "bare except:",
        "except py_builtins.BaseException: pass",
        "except broad exception: pass",
    ]


def test_detector_allows_non_noop_broad_handlers_that_fail_later() -> None:
    """Broad handlers that record diagnostics for a later assertion are not no-op swallows."""
    tree = ast.parse(
        """
errors = []

try:
    raise RuntimeError("boom")
except Exception as exc:
    errors.append(exc)
"""
    )

    assert _bare_except_locations_for_tree("snippet.py", tree) == []
