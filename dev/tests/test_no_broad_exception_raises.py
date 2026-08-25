"""Static guard: no broad exception assertions or suppressions in production tests."""

from __future__ import annotations

import ast
import tokenize
from collections import Counter
from collections.abc import Iterable, Mapping
from io import StringIO
from pathlib import Path
from typing import NamedTuple

import pytest

from cadrumo.tests import (
    ast_for_path,
    qualified_name,
    repo_relative,
)

from ._project_inventory import all_test_control_modules

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
_BROAD_SITE_MARKER = "# broad:"


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
            for target in node.targets:
                broad_alias_assignments.extend(_broad_alias_assignments_from_target(target, node.value))
        elif isinstance(node, ast.AnnAssign) and node.value is not None and isinstance(node.target, ast.Name):
            broad_alias_assignments.extend(_broad_alias_assignments_from_target(node.target, node.value))

    return _BroadExceptionScanInputs(
        pytest_aliases=pytest_aliases,
        raises_aliases=raises_aliases,
        contextlib_aliases=contextlib_aliases,
        suppress_aliases=suppress_aliases,
        broad_exception_names=broad_exception_names,
        broad_alias_assignments=broad_alias_assignments,
        call_nodes=call_nodes,
    )


def _broad_alias_assignments_from_target(
    target: ast.expr,
    value: ast.expr,
) -> list[tuple[str, tuple[str, ...]]]:
    """Return broad-exception alias assignments from one target/value pair."""
    if isinstance(target, ast.Name):
        if isinstance(value, ast.Tuple | ast.List | ast.Set):
            return [(qualified_name(element), (target.id,)) for element in value.elts]
        return [(qualified_name(value), (target.id,))]
    if isinstance(target, ast.Tuple | ast.List) and isinstance(value, ast.Tuple | ast.List):
        assignments: list[tuple[str, tuple[str, ...]]] = []
        for target_element, value_element in zip(target.elts, value.elts, strict=False):
            if isinstance(target_element, ast.Name):
                assignments.append((qualified_name(value_element), (target_element.id,)))
        return assignments
    return []


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
    if isinstance(node, ast.Starred):
        return _contains_broad_exception_root(node.value, broad_exception_names)
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


def _broad_exception_inventory_for_module_trees(
    module_trees: Iterable[tuple[str, ast.AST]],
) -> _BroadExceptionInventory:
    """Return broad exception policy violations for parsed modules."""
    pytest_raises: list[str] = []
    contextlib_suppressions: list[str] = []

    for relative, tree in module_trees:
        sites = _broad_exception_sites(tree)
        for lineno in sites.pytest_raises:
            pytest_raises.append(f"{relative}:{lineno}: pytest.raises catches Exception/BaseException")
        for lineno in sites.contextlib_suppressions:
            contextlib_suppressions.append(f"{relative}:{lineno}: contextlib.suppress catches Exception/BaseException")

    return _BroadExceptionInventory(
        pytest_raises=tuple(pytest_raises),
        contextlib_suppressions=tuple(contextlib_suppressions),
        broad_raise_suppressions=(),
    )


def _broad_exception_inventory_for_source(relative_path: str, source: str) -> _BroadExceptionInventory:
    """Return broad exception policy violations for one in-memory source module."""
    tree = ast.parse(source, filename=relative_path)
    return _broad_exception_inventory_for_module_trees(((relative_path, tree),))


def _violation_marker_counts(source: str, violations: Iterable[str]) -> Counter[str]:
    """Return source-site marker counts for formatted policy violations."""
    lines = source.splitlines()
    markers: Counter[str] = Counter()
    for violation in violations:
        lineno = int(violation.split(":", maxsplit=2)[1])
        line = lines[lineno - 1] if lineno <= len(lines) else ""
        _, separator, marker = line.partition(_BROAD_SITE_MARKER)
        markers[marker.strip() if separator else "<unmarked>"] += 1
    return markers


@pytest.fixture(scope="module")
def broad_exception_inventory(source_tree_ast: Mapping[Path, ast.AST]) -> _BroadExceptionInventory:
    """Return all broad exception policy violations from one test-control inventory pass."""
    module_trees: list[tuple[str, ast.AST]] = []
    broad_raise_suppressions: list[str] = []

    for module_path in all_test_control_modules():
        relative = repo_relative(module_path)
        tree = ast_for_path(module_path, source_tree_ast)
        if tree is not None:
            module_trees.append((relative, tree))
        for lineno in _b017_suppression_lines(module_path):
            broad_raise_suppressions.append(f"{relative}:{lineno}: {_NOQA_TOKEN} {_BROAD_RAISES_RULE}")
    inventory = _broad_exception_inventory_for_module_trees(module_trees)

    return _BroadExceptionInventory(
        pytest_raises=inventory.pytest_raises,
        contextlib_suppressions=inventory.contextlib_suppressions,
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


@pytest.mark.parametrize(
    ("source", "expected_pytest_markers", "expected_suppress_markers"),
    (
        pytest.param(
            """
import pytest

with pytest.raises(Exception):  # broad:positional
    pass

with pytest.raises(expected_exception=BaseException):  # broad:keyword
    pass

with pytest.raises(ValueError | Exception):  # broad:union
    pass

with pytest.raises(ValueError):
    pass
""",
            Counter({"positional": 1, "keyword": 1, "union": 1}),
            Counter(),
            id="pytest-raises-call-shapes",
        ),
        pytest.param(
            """
import pytest as pt
from pytest import raises as pytest_raises

with pt.raises(Exception):  # broad:pytest-module-alias
    pass

with pytest_raises(expected_exception=BaseException):  # broad:pytest-raises-alias
    pass

with pt.raises(ValueError):
    pass
""",
            Counter({"pytest-module-alias": 1, "pytest-raises-alias": 1}),
            Counter(),
            id="pytest-aliases",
        ),
        pytest.param(
            """
import builtins as py_builtins
from builtins import Exception as BroadException
import pytest

RaisedException = BroadException

with pytest.raises(py_builtins.BaseException):  # broad:builtins-module-alias
    pass

with pytest.raises(RaisedException):  # broad:assigned-broad-alias
    pass

with pytest.raises(ValueError):
    pass
""",
            Counter({"builtins-module-alias": 1, "assigned-broad-alias": 1}),
            Counter(),
            id="broad-exception-aliases",
        ),
        pytest.param(
            """
import builtins
import pytest

ErrorAlias, NarrowAlias = Exception, ValueError
BaseAlias, OtherAlias = builtins.BaseException, RuntimeError

with pytest.raises(ErrorAlias):  # broad:tuple-exception-alias
    pass

with pytest.raises(BaseAlias):  # broad:tuple-base-alias
    pass

with pytest.raises(NarrowAlias):
    pass
""",
            Counter({"tuple-exception-alias": 1, "tuple-base-alias": 1}),
            Counter(),
            id="tuple-assigned-broad-aliases",
        ),
        pytest.param(
            """
import contextlib
import pytest

with pytest.raises(*(ValueError, Exception)):  # broad:starred-raises-container
    pass

with pytest.raises(*(ValueError,)):
    pass

with contextlib.suppress(*(RuntimeError, BaseException)):  # broad:starred-suppress-container
    pass

with contextlib.suppress(*(RuntimeError,)):
    pass
""",
            Counter({"starred-raises-container": 1}),
            Counter({"starred-suppress-container": 1}),
            id="starred-exception-containers",
        ),
        pytest.param(
            """
import contextlib
import pytest

ExpectedErrors = (ValueError, Exception)
SuppressedErrors = [RuntimeError, BaseException]
NarrowErrors = (ValueError, RuntimeError)

with pytest.raises(ExpectedErrors):  # broad:assigned-raises-container
    pass

with pytest.raises(NarrowErrors):
    pass

with contextlib.suppress(*SuppressedErrors):  # broad:assigned-suppress-container
    pass
""",
            Counter({"assigned-raises-container": 1}),
            Counter({"assigned-suppress-container": 1}),
            id="assigned-exception-containers",
        ),
        pytest.param(
            """
import contextlib
import contextlib as ctx
from contextlib import suppress as ignored
from builtins import Exception as BroadException

SuppressedException = BroadException

with contextlib.suppress(Exception):  # broad:contextlib-direct
    pass

with ctx.suppress(BaseException):  # broad:contextlib-module-alias
    pass

with ignored(ValueError, SuppressedException):  # broad:contextlib-call-alias
    pass

with ignored(ValueError):
    pass
""",
            Counter(),
            Counter({"contextlib-direct": 1, "contextlib-module-alias": 1, "contextlib-call-alias": 1}),
            id="contextlib-aliases",
        ),
    ),
)
def test_broad_exception_policy_rejects_permissive_exception_shapes(
    source: str,
    expected_pytest_markers: Counter[str],
    expected_suppress_markers: Counter[str],
) -> None:
    """Broad exception assertions must fail through the real policy path."""
    inventory = _broad_exception_inventory_for_source("dev/tests/test_broad_exceptions.py", source)

    assert _violation_marker_counts(source, inventory.pytest_raises) == expected_pytest_markers
    assert _violation_marker_counts(source, inventory.contextlib_suppressions) == expected_suppress_markers


def test_discovery_found_modules() -> None:
    """Guardrail: the discovery walk must find at least one test/control module."""
    modules = all_test_control_modules()
    assert modules, "No test/control modules discovered -- check glob roots."
