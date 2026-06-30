"""Static guard: no broad exception assertions or suppressions in production tests."""

from __future__ import annotations

import ast
import tokenize
from io import StringIO
from pathlib import Path
from typing import NamedTuple

import pytest

from ._inventory import (
    all_test_control_modules,
    ast_for_path,
    qualified_name,
    repo_relative,
)

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


class _BroadExceptionSites(NamedTuple):
    """Broad exception assertion/suppression line numbers for one AST."""

    pytest_raises: list[int]
    contextlib_suppressions: list[int]


class _BroadExceptionScanInputs(NamedTuple):
    """Alias bindings and call nodes collected from one AST pass."""

    pytest_aliases: set[str]
    raises_aliases: set[str]
    contextlib_aliases: set[str]
    suppress_aliases: set[str]
    broad_exception_names: set[str]
    broad_alias_assignments: list[tuple[str, tuple[str, ...]]]
    call_nodes: list[ast.Call]


class _BroadExceptionInventory(NamedTuple):
    """Formatted broad exception policy violations for the test-control surface."""

    pytest_raises: tuple[str, ...]
    contextlib_suppressions: tuple[str, ...]
    broad_raise_suppressions: tuple[str, ...]


def _broad_pytest_raises_sites(tree: ast.AST) -> list[int]:
    """Return line numbers where ``pytest.raises`` catches a broad exception root."""
    return _broad_exception_sites(tree).pytest_raises


def _broad_contextlib_suppress_sites(tree: ast.AST) -> list[int]:
    """Return line numbers where ``contextlib.suppress`` hides a broad exception root."""
    return _broad_exception_sites(tree).contextlib_suppressions


def _broad_exception_sites(tree: ast.AST) -> _BroadExceptionSites:
    """Return broad pytest.raises and contextlib.suppress line numbers from one tree walk."""
    inputs = _broad_exception_scan_inputs(tree)
    broad_exception_names = _resolve_broad_exception_names(
        inputs.broad_exception_names,
        inputs.broad_alias_assignments,
    )
    pytest_raises: list[int] = []
    contextlib_suppressions: list[int] = []
    for node in inputs.call_nodes:
        call_name = qualified_name(node.func)
        if _is_pytest_raises_call(call_name, inputs.pytest_aliases, inputs.raises_aliases):
            expected_exception = _pytest_raises_expected_exception(node)
            if expected_exception is not None and _contains_broad_exception_root(
                expected_exception,
                broad_exception_names,
            ):
                pytest_raises.append(node.lineno)
        elif _is_contextlib_suppress_call(call_name, inputs.contextlib_aliases, inputs.suppress_aliases) and any(
            _contains_broad_exception_root(arg, broad_exception_names) for arg in node.args
        ):
            contextlib_suppressions.append(node.lineno)
    return _BroadExceptionSites(pytest_raises=pytest_raises, contextlib_suppressions=contextlib_suppressions)


def _broad_exception_scan_inputs(tree: ast.AST) -> _BroadExceptionScanInputs:
    """Collect aliases, broad assignments, and call nodes in one AST pass."""
    pytest_aliases = {"pytest"}
    raises_aliases: set[str] = set()
    contextlib_aliases = {"contextlib"}
    suppress_aliases: set[str] = set()
    broad_exception_names = set(_BROAD_EXCEPTION_NAMES)
    broad_alias_assignments: list[tuple[str, tuple[str, ...]]] = []
    call_nodes: list[ast.Call] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            call_nodes.append(node)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "pytest":
                    pytest_aliases.add(alias.asname or alias.name)
                elif alias.name == "contextlib":
                    contextlib_aliases.add(alias.asname or alias.name)
                elif alias.name == "builtins":
                    builtins_alias = alias.asname or alias.name
                    broad_exception_names.add(f"{builtins_alias}.BaseException")
                    broad_exception_names.add(f"{builtins_alias}.Exception")
        elif isinstance(node, ast.ImportFrom):
            if node.module == "pytest":
                for alias in node.names:
                    if alias.name == "raises":
                        raises_aliases.add(alias.asname or alias.name)
            elif node.module == "contextlib":
                for alias in node.names:
                    if alias.name == "suppress":
                        suppress_aliases.add(alias.asname or alias.name)
            elif node.module == "builtins":
                for alias in node.names:
                    if alias.name in {"BaseException", "Exception"}:
                        broad_exception_names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Assign):
            target_names = tuple(target.id for target in node.targets if isinstance(target, ast.Name))
            if target_names:
                broad_alias_assignments.append((qualified_name(node.value), target_names))
        elif isinstance(node, ast.AnnAssign) and node.value is not None and isinstance(node.target, ast.Name):
            broad_alias_assignments.append((qualified_name(node.value), (node.target.id,)))

    return _BroadExceptionScanInputs(
        pytest_aliases=pytest_aliases,
        raises_aliases=raises_aliases,
        contextlib_aliases=contextlib_aliases,
        suppress_aliases=suppress_aliases,
        broad_exception_names=broad_exception_names,
        broad_alias_assignments=broad_alias_assignments,
        call_nodes=call_nodes,
    )


def _pytest_module_aliases(tree: ast.AST) -> set[str]:
    """Return local names bound to the pytest module."""
    return _broad_exception_scan_inputs(tree).pytest_aliases


def _contextlib_module_aliases(tree: ast.AST) -> set[str]:
    """Return local names bound to the contextlib module."""
    return _broad_exception_scan_inputs(tree).contextlib_aliases


def _contextlib_suppress_aliases(tree: ast.AST) -> set[str]:
    """Return local names imported from ``contextlib.suppress``."""
    return _broad_exception_scan_inputs(tree).suppress_aliases


def _pytest_raises_aliases(tree: ast.AST) -> set[str]:
    """Return local names imported from ``pytest.raises``."""
    return _broad_exception_scan_inputs(tree).raises_aliases


def _is_contextlib_suppress_call(call_name: str, contextlib_aliases: set[str], suppress_aliases: set[str]) -> bool:
    """Return True for canonical or aliased ``contextlib.suppress`` calls."""
    if call_name in suppress_aliases:
        return True
    return any(call_name == f"{alias}.suppress" for alias in contextlib_aliases)


def _is_pytest_raises_call(call_name: str, pytest_aliases: set[str], raises_aliases: set[str]) -> bool:
    """Return True for canonical or aliased ``pytest.raises`` calls."""
    if call_name in raises_aliases:
        return True
    return any(call_name == f"{alias}.raises" for alias in pytest_aliases)


def _pytest_raises_expected_exception(node: ast.Call) -> ast.AST | None:
    """Return the exception expression supplied to ``pytest.raises``, if present."""
    if node.args:
        return node.args[0]
    for keyword in node.keywords:
        if keyword.arg == "expected_exception":
            return keyword.value
    return None


def _broad_exception_names(tree: ast.AST) -> set[str]:
    """Return local names that resolve to Exception/BaseException."""
    inputs = _broad_exception_scan_inputs(tree)
    return _resolve_broad_exception_names(inputs.broad_exception_names, inputs.broad_alias_assignments)


def _resolve_broad_exception_names(
    names: set[str],
    alias_assignments: list[tuple[str, tuple[str, ...]]],
) -> set[str]:
    """Return broad exception names after resolving local alias assignments."""
    resolved = set(names)
    changed = True
    while changed:
        changed = False
        for value_name, target_names in alias_assignments:
            if value_name not in resolved:
                continue
            for target_name in target_names:
                if target_name not in resolved:
                    resolved.add(target_name)
                    changed = True
    return resolved


def _contains_broad_exception_root(node: ast.AST, broad_exception_names: set[str]) -> bool:
    """Return True when *node* names Exception/BaseException directly or in a union container."""
    name = qualified_name(node)
    if name in broad_exception_names:
        return True
    if isinstance(node, ast.Tuple | ast.List | ast.Set):
        return any(_contains_broad_exception_root(element, broad_exception_names) for element in node.elts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _contains_broad_exception_root(node.left, broad_exception_names) or _contains_broad_exception_root(
            node.right,
            broad_exception_names,
        )
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


@pytest.fixture(scope="module")
def broad_exception_inventory() -> _BroadExceptionInventory:
    """Return all broad exception policy violations from one test-control inventory pass."""
    pytest_raises: list[str] = []
    contextlib_suppressions: list[str] = []
    broad_raise_suppressions: list[str] = []

    for module_path in all_test_control_modules():
        relative = repo_relative(module_path)
        tree = ast_for_path(module_path)
        if tree is not None:
            sites = _broad_exception_sites(tree)
            for lineno in sites.pytest_raises:
                pytest_raises.append(f"{relative}:{lineno}: pytest.raises catches Exception/BaseException")
            for lineno in sites.contextlib_suppressions:
                contextlib_suppressions.append(
                    f"{relative}:{lineno}: contextlib.suppress catches Exception/BaseException"
                )
        for lineno in _b017_suppression_lines(module_path):
            broad_raise_suppressions.append(f"{relative}:{lineno}: {_NOQA_TOKEN} {_BROAD_RAISES_RULE}")

    return _BroadExceptionInventory(
        pytest_raises=tuple(pytest_raises),
        contextlib_suppressions=tuple(contextlib_suppressions),
        broad_raise_suppressions=tuple(broad_raise_suppressions),
    )


def test_no_broad_pytest_raises(broad_exception_inventory: _BroadExceptionInventory) -> None:
    """Tests must assert the concrete exception contract they expect."""
    violations = broad_exception_inventory.pytest_raises

    assert not violations, "Broad pytest.raises exception assertions found:\n" + "\n".join(violations)


def test_no_broad_contextlib_suppressions(broad_exception_inventory: _BroadExceptionInventory) -> None:
    """Tests must not hide arbitrary failures behind broad contextlib.suppress."""
    violations = broad_exception_inventory.contextlib_suppressions

    assert not violations, "Broad contextlib.suppress exception handlers found:\n" + "\n".join(violations)


def test_no_broad_raise_suppressions(broad_exception_inventory: _BroadExceptionInventory) -> None:
    """Broad-raise lint suppressions must not hide permissive exception contracts."""
    violations = broad_exception_inventory.broad_raise_suppressions

    assert not violations, "Broad exception assertion suppressions found:\n" + "\n".join(violations)


def test_broad_raises_detector_rejects_keyword_and_union_shapes() -> None:
    """Broad exception contracts must be caught across pytest.raises shapes."""
    tree = ast.parse(
        """
import pytest

with pytest.raises(Exception):
    pass

with pytest.raises(expected_exception=BaseException):
    pass

with pytest.raises(ValueError | Exception):
    pass

with pytest.raises(ValueError):
    pass
"""
    )

    assert _broad_pytest_raises_sites(tree) == [4, 7, 10]


def test_broad_raises_detector_rejects_pytest_alias_shapes() -> None:
    """Aliasing pytest must not hide broad exception assertions."""
    tree = ast.parse(
        """
import pytest as pt
from pytest import raises as pytest_raises

with pt.raises(Exception):
    pass

with pytest_raises(expected_exception=BaseException):
    pass

with pt.raises(ValueError):
    pass
"""
    )

    assert _broad_pytest_raises_sites(tree) == [5, 8]


def test_broad_raises_detector_rejects_builtins_exception_aliases() -> None:
    """Aliasing broad exception roots must not hide permissive assertions."""
    tree = ast.parse(
        """
import builtins as py_builtins
from builtins import Exception as BroadException
import pytest

RaisedException = BroadException

with pytest.raises(py_builtins.BaseException):
    pass

with pytest.raises(RaisedException):
    pass

with pytest.raises(ValueError):
    pass
"""
    )

    assert _broad_pytest_raises_sites(tree) == [8, 11]


def test_broad_suppress_detector_rejects_contextlib_alias_shapes() -> None:
    """Broad contextlib.suppress calls must be caught across alias forms."""
    tree = ast.parse(
        """
import contextlib
import contextlib as ctx
from contextlib import suppress as ignored
from builtins import Exception as BroadException

SuppressedException = BroadException

with contextlib.suppress(Exception):
    pass

with ctx.suppress(BaseException):
    pass

with ignored(ValueError, SuppressedException):
    pass

with ignored(ValueError):
    pass
"""
    )

    assert _broad_contextlib_suppress_sites(tree) == [9, 12, 15]


def test_discovery_found_modules() -> None:
    """Guardrail: the discovery walk must find at least one test/control module."""
    modules = all_test_control_modules()
    assert modules, "No test/control modules discovered -- check glob roots."
