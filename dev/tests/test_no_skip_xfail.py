"""Static guard: zero skip / xfail shortcuts in deterministic production tests.

Walks every deterministic test, test-support, and ``conftest.py`` module under
``src/cadrumo/`` via AST and asserts that deterministic modules carry no pytest
skip/xfail markers or shortcut calls. Import-time skips and
``unittest.SkipTest`` raises are forbidden as well, including pytest alias forms.

Live modules are deselected by the default marker expression. Once explicitly
selected, they fail when prerequisites are absent and must never self-skip. No
item may carry both ``unit`` and ``aeat_live`` markers.

See Also:
    :mod:`~tests.test_mock_inventory`
        Companion production-test guard for mock and test-double shortcuts.
    :mod:`~tests.test_monkeypatch_inventory`
        Companion production-test guard for monkeypatch mutation shortcuts.
    :func:`~tests._inventory.discover_test_control_modules`
        Source-tree deterministic test-control surface walked by this gate.
    :func:`~tests._inventory.project_test_control_modules`
        Project-level test-control surface checked for skip and xfail shortcuts.
    :class:`_SkipInventorySites`
        AST-level detector result carrying forbidden sites and unit/live marker
        intersections.
    :class:`_SkipPolicyInventory`
        Formatted policy violation aggregate consumed by the public assertions.
"""

from __future__ import annotations

import ast
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import NamedTuple

import pytest

from cadrumo.tests._inventory import (
    ast_for_path,
    discover_test_control_modules,
    discover_test_modules,
    qualified_name,
    repo_relative,
)

from ._project_inventory import project_test_control_modules

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_FORBIDDEN_MARKERS = frozenset({"skip", "skipif", "xfail"})
_FORBIDDEN_CALL_NAMES = frozenset({"importorskip", "skip", "xfail"})
_FORBIDDEN_CALLS = frozenset({f"pytest.{name}" for name in _FORBIDDEN_CALL_NAMES})
_FORBIDDEN_EXCEPTIONS = frozenset({"SkipTest", "unittest.SkipTest", "unittest.case.SkipTest"})
_LIVE_EXECUTION_MARKER = "aeat_live"
_UNIT_EXECUTION_MARKER = "unit"


def _pytest_name(*parts: str) -> str:
    """Return a pytest dotted name for detector fixture snippets."""
    return ".".join(("pytest", *parts))


class _SkipAliasInventory(NamedTuple):
    pytest_aliases: set[str]
    pytest_mark_aliases: set[str]
    pytest_shortcut_aliases: dict[str, str]
    unittest_aliases: set[str]
    unittest_case_aliases: set[str]
    skiptest_aliases: dict[str, str]


class _SkipInventorySites(NamedTuple):
    forbidden_sites: list[tuple[int, str]]
    unit_live_intersections: list[tuple[int, str]]


class _SkipPolicyInventory(NamedTuple):
    shortcut_violations: list[str]
    unit_live_violations: list[str]


def _forbidden_marker_sites(tree: ast.AST) -> list[tuple[int, str]]:
    """Return ``(lineno, marker_or_call_name)`` for every forbidden shortcut in *tree*."""
    return _skip_inventory_sites(tree).forbidden_sites


def _skip_inventory_sites(tree: ast.AST) -> _SkipInventorySites:
    """Return skip/xfail shortcut sites and unit/live marker intersections."""
    aliases = _skip_alias_inventory(tree)
    module_markers = _module_execution_markers(tree, aliases)
    forbidden_sites: list[tuple[int, str]] = []
    unit_live_intersections: list[tuple[int, str]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            mark_name = _forbidden_pytest_mark_name(node, aliases.pytest_aliases, aliases.pytest_mark_aliases)
            if mark_name is not None:
                forbidden_sites.append((node.lineno, mark_name))

        if isinstance(node, ast.Call):
            call_name = _canonical_pytest_call_name(
                qualified_name(node.func),
                aliases.pytest_aliases,
                aliases.pytest_shortcut_aliases,
            )
            if call_name in _FORBIDDEN_CALLS:
                forbidden_sites.append((node.lineno, call_name))

        if isinstance(node, ast.Raise) and node.exc is not None:
            exception_expr = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
            exception_name = _canonical_skiptest_exception_name(
                qualified_name(exception_expr),
                aliases.unittest_aliases,
                aliases.unittest_case_aliases,
                aliases.skiptest_aliases,
            )
            if exception_name in _FORBIDDEN_EXCEPTIONS:
                forbidden_sites.append((node.lineno, exception_name))

        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            markers = module_markers | _decorator_execution_markers(node, aliases)
            if {_UNIT_EXECUTION_MARKER, _LIVE_EXECUTION_MARKER} <= markers:
                unit_live_intersections.append((node.lineno, node.name))

    return _SkipInventorySites(
        forbidden_sites=forbidden_sites,
        unit_live_intersections=unit_live_intersections,
    )


def _forbidden_marker_sites_for_path(module_path: Path, tree: ast.AST) -> list[tuple[int, str]]:
    """Return forbidden skip/xfail sites after applying central live-gate exceptions."""
    return _forbidden_marker_sites_for_relative(repo_relative(module_path), tree)


def _forbidden_marker_sites_for_relative(relative_path: str, tree: ast.AST) -> list[tuple[int, str]]:
    """Return forbidden skip/xfail sites for one repo-relative source path."""
    sites = _skip_inventory_sites(tree).forbidden_sites
    return _filter_forbidden_marker_sites_for_relative(relative_path, tree, sites)


def _forbidden_project_marker_sites_for_relative(relative_path: str, tree: ast.AST) -> list[tuple[int, str]]:
    """Return forbidden skip/xfail sites in project tests outside live modules."""
    return _forbidden_marker_sites_for_relative(relative_path, tree)


def _forbidden_unit_marker_sites_for_relative(relative_path: str, tree: ast.AST) -> list[tuple[int, str]]:
    """Return forbidden skip/xfail sites that affect collected unit tests."""
    sites = _forbidden_marker_sites_for_relative(relative_path, tree)
    if not sites:
        return []
    unit_context = _unit_context_by_lineno(tree)
    return [(lineno, marker_or_call_name) for lineno, marker_or_call_name in sites if unit_context.get(lineno, False)]


def _filter_forbidden_marker_sites_for_relative(
    relative_path: str,
    tree: ast.AST,
    sites: list[tuple[int, str]],
) -> list[tuple[int, str]]:
    """Return raw skip/xfail sites; no support-file exception exists."""
    del relative_path, tree
    return sites


def _unit_context_by_lineno(tree: ast.AST) -> dict[int, bool]:
    """Return whether each source line belongs to a unit-selected test context."""
    aliases = _skip_alias_inventory(tree)
    module_is_unit = _UNIT_EXECUTION_MARKER in _module_execution_markers(tree, aliases)
    module_has_unit_items = module_is_unit or any(
        isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
        and _UNIT_EXECUTION_MARKER in _decorator_execution_markers(node, aliases)
        for node in ast.walk(tree)
    )
    context: dict[int, bool] = {}

    def visit(node: ast.AST, inherited_unit: bool, inside_item: bool) -> None:
        lineno = getattr(node, "lineno", None)
        if isinstance(lineno, int):
            context.setdefault(lineno, inherited_unit if inside_item else module_has_unit_items)
        child_unit = inherited_unit
        child_inside_item = inside_item
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            child_unit = inherited_unit or _UNIT_EXECUTION_MARKER in _decorator_execution_markers(node, aliases)
            child_inside_item = True
        for child in ast.iter_child_nodes(node):
            visit(child, child_unit, child_inside_item)

    visit(tree, module_is_unit, False)
    return context


def _forbidden_pytest_mark_name(
    attr_chain: ast.Attribute,
    pytest_aliases: set[str],
    pytest_mark_aliases: set[str],
) -> str | None:
    """Return a forbidden ``pytest.mark`` shortcut name from an attribute chain."""
    if attr_chain.attr not in _FORBIDDEN_MARKERS:
        return None
    mark_attr = attr_chain.value
    if isinstance(mark_attr, ast.Attribute) and mark_attr.attr == "mark":
        mark_root = qualified_name(mark_attr.value)
        if mark_root in pytest_aliases:
            return f"pytest.mark.{attr_chain.attr}"
    if isinstance(mark_attr, ast.Name) and mark_attr.id in pytest_mark_aliases:
        return f"pytest.mark.{attr_chain.attr}"
    return None


def _pytest_module_aliases(tree: ast.AST) -> set[str]:
    """Return local names bound to the pytest module."""
    return _skip_alias_inventory(tree).pytest_aliases


def _pytest_mark_aliases(tree: ast.AST) -> set[str]:
    """Return local names bound to ``pytest.mark``."""
    return _skip_alias_inventory(tree).pytest_mark_aliases


def _pytest_shortcut_aliases(tree: ast.AST) -> dict[str, str]:
    """Return local names imported from pytest skip / xfail shortcut helpers."""
    return _skip_alias_inventory(tree).pytest_shortcut_aliases


def _unittest_module_aliases(tree: ast.AST) -> set[str]:
    """Return local names bound to the unittest module."""
    return _skip_alias_inventory(tree).unittest_aliases


def _skiptest_aliases(tree: ast.AST) -> dict[str, str]:
    """Return local names imported from unittest.SkipTest."""
    return _skip_alias_inventory(tree).skiptest_aliases


def _skip_alias_inventory(tree: ast.AST) -> _SkipAliasInventory:
    """Return pytest/unittest aliases relevant to skip and xfail detection."""
    pytest_aliases = {"pytest"}
    pytest_mark_aliases: set[str] = set()
    pytest_shortcut_aliases: dict[str, str] = {}
    unittest_aliases = {"unittest"}
    unittest_case_aliases: set[str] = set()
    skiptest_aliases: dict[str, str] = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "pytest":
                    pytest_aliases.add(alias.asname or alias.name)
                elif alias.name == "unittest":
                    unittest_aliases.add(alias.asname or alias.name)
                elif alias.name == "unittest.case":
                    unittest_case_aliases.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module == "pytest":
            for alias in node.names:
                if alias.name == "mark":
                    pytest_mark_aliases.add(alias.asname or alias.name)
                elif alias.name in _FORBIDDEN_CALL_NAMES:
                    pytest_shortcut_aliases[alias.asname or alias.name] = f"pytest.{alias.name}"
        elif isinstance(node, ast.ImportFrom) and node.module in {"unittest", "unittest.case"}:
            for alias in node.names:
                if alias.name == "SkipTest":
                    skiptest_aliases[alias.asname or alias.name] = "SkipTest"
                elif node.module == "unittest" and alias.name == "case":
                    unittest_case_aliases.add(alias.asname or alias.name)
        _add_pytest_assignment_aliases(node, pytest_aliases, pytest_mark_aliases, pytest_shortcut_aliases)
        _add_unittest_assignment_aliases(node, unittest_aliases, unittest_case_aliases)
        _add_skiptest_assignment_aliases(node, unittest_aliases, unittest_case_aliases, skiptest_aliases)

    return _SkipAliasInventory(
        pytest_aliases=pytest_aliases,
        pytest_mark_aliases=pytest_mark_aliases,
        pytest_shortcut_aliases=pytest_shortcut_aliases,
        unittest_aliases=unittest_aliases,
        unittest_case_aliases=unittest_case_aliases,
        skiptest_aliases=skiptest_aliases,
    )


def _add_pytest_assignment_aliases(
    node: ast.AST,
    pytest_aliases: set[str],
    pytest_mark_aliases: set[str],
    pytest_shortcut_aliases: dict[str, str],
) -> None:
    """Record aliases assigned from pytest, pytest.mark, or skip/xfail shortcut helpers."""
    if isinstance(node, ast.Assign):
        targets = node.targets
        value = node.value
    elif isinstance(node, ast.AnnAssign) and node.value is not None:
        targets = [node.target]
        value = node.value
    else:
        return
    value_name = qualified_name(value)
    target_names = tuple(target.id for target in targets if isinstance(target, ast.Name))
    if not target_names:
        return
    if value_name in pytest_aliases:
        pytest_aliases.update(target_names)
        return
    if _is_pytest_mark_alias_value(value_name, pytest_aliases, pytest_mark_aliases):
        pytest_mark_aliases.update(target_names)
    shortcut_name = _canonical_pytest_call_name(value_name, pytest_aliases, pytest_shortcut_aliases)
    if shortcut_name in _FORBIDDEN_CALLS:
        pytest_shortcut_aliases.update({target_name: shortcut_name for target_name in target_names})


def _is_pytest_mark_alias_value(
    value_name: str,
    pytest_aliases: set[str],
    pytest_mark_aliases: set[str],
) -> bool:
    """Return True when an expression resolves to pytest.mark."""
    if value_name in pytest_mark_aliases:
        return True
    return any(value_name == f"{alias}.mark" for alias in pytest_aliases)


def _add_unittest_assignment_aliases(
    node: ast.AST,
    unittest_aliases: set[str],
    unittest_case_aliases: set[str],
) -> None:
    """Record aliases assigned from unittest or unittest.case modules."""
    if isinstance(node, ast.Assign):
        targets = node.targets
        value = node.value
    elif isinstance(node, ast.AnnAssign) and node.value is not None:
        targets = [node.target]
        value = node.value
    else:
        return
    target_names = tuple(target.id for target in targets if isinstance(target, ast.Name))
    if not target_names:
        return
    value_name = qualified_name(value)
    if value_name in unittest_aliases:
        unittest_aliases.update(target_names)
    elif _is_unittest_case_alias_value(value_name, unittest_aliases, unittest_case_aliases):
        unittest_case_aliases.update(target_names)


def _is_unittest_case_alias_value(
    value_name: str,
    unittest_aliases: set[str],
    unittest_case_aliases: set[str],
) -> bool:
    """Return True when an expression resolves to unittest.case."""
    if value_name in unittest_case_aliases:
        return True
    return any(value_name == f"{alias}.case" for alias in unittest_aliases)


def _add_skiptest_assignment_aliases(
    node: ast.AST,
    unittest_aliases: set[str],
    unittest_case_aliases: set[str],
    skiptest_aliases: dict[str, str],
) -> None:
    """Record aliases assigned from unittest SkipTest spellings."""
    if isinstance(node, ast.Assign):
        targets = node.targets
        value = node.value
    elif isinstance(node, ast.AnnAssign) and node.value is not None:
        targets = [node.target]
        value = node.value
    else:
        return
    target_names = tuple(target.id for target in targets if isinstance(target, ast.Name))
    if not target_names:
        return
    exception_name = _canonical_skiptest_exception_name(
        qualified_name(value),
        unittest_aliases,
        unittest_case_aliases,
        skiptest_aliases,
    )
    if exception_name in _FORBIDDEN_EXCEPTIONS:
        skiptest_aliases.update({target_name: exception_name for target_name in target_names})


def _canonical_skiptest_exception_name(
    exception_name: str,
    unittest_aliases: set[str],
    unittest_case_aliases: set[str],
    skiptest_aliases: dict[str, str],
) -> str:
    """Return canonical SkipTest exception names for unittest aliases."""
    direct_alias = skiptest_aliases.get(exception_name)
    if direct_alias is not None:
        return direct_alias
    for alias in unittest_aliases:
        if exception_name == f"{alias}.SkipTest":
            return "unittest.SkipTest"
        if exception_name == f"{alias}.case.SkipTest":
            return "unittest.case.SkipTest"
    for alias in unittest_case_aliases:
        if exception_name == f"{alias}.SkipTest":
            return "unittest.case.SkipTest"
    return exception_name


def _canonical_pytest_call_name(
    call_name: str,
    pytest_aliases: set[str],
    pytest_shortcut_aliases: dict[str, str],
) -> str:
    """Return the canonical pytest shortcut call name for aliases."""
    direct_alias = pytest_shortcut_aliases.get(call_name)
    if direct_alias is not None:
        return direct_alias
    for alias in pytest_aliases:
        prefix = alias + "."
        if call_name.startswith(prefix):
            suffix = call_name.removeprefix(prefix)
            if suffix in _FORBIDDEN_CALL_NAMES:
                return f"pytest.{suffix}"
    return call_name


def _pytestmark_assignment_value(node: ast.stmt) -> ast.expr | None:
    """Return the value assigned to module-level pytestmark, if any."""
    if isinstance(node, ast.Assign):
        targets = node.targets
        value = node.value
    elif isinstance(node, ast.AnnAssign | ast.AugAssign):
        targets = [node.target]
        value = node.value
    else:
        return None
    if value is None:
        return None
    if any(isinstance(target, ast.Name) and target.id == "pytestmark" for target in targets):
        return value
    return None


def _module_execution_markers(tree: ast.AST, aliases: _SkipAliasInventory | None = None) -> set[str]:
    """Return module-level execution markers from a ``pytestmark = [...]`` assignment."""
    if aliases is None:
        aliases = _skip_alias_inventory(tree)
    markers: set[str] = set()
    body = tree.body if isinstance(tree, ast.Module) else ()
    for node in body:
        value = _pytestmark_assignment_value(node)
        if value is None:
            continue
        values: list[ast.expr] = list(value.elts) if isinstance(value, ast.List | ast.Tuple) else [value]
        for value in values:
            marker = _execution_marker_name(value, aliases.pytest_aliases, aliases.pytest_mark_aliases)
            if marker is not None:
                markers.add(marker)
    return markers


def _decorator_execution_markers(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
    aliases: _SkipAliasInventory | None = None,
) -> set[str]:
    """Return pytest execution marker names attached directly to a test item."""
    if aliases is None:
        aliases = _skip_alias_inventory(ast.Module(body=[], type_ignores=[]))
    markers: set[str] = set()
    for decorator in node.decorator_list:
        marker = _execution_marker_name(decorator, aliases.pytest_aliases, aliases.pytest_mark_aliases)
        if marker is not None:
            markers.add(marker)
    return markers


def _execution_marker_name(
    expr: ast.expr,
    pytest_aliases: set[str],
    pytest_mark_aliases: set[str],
) -> str | None:
    """Return the pytest marker name from an execution-marker expression."""
    name = qualified_name(expr)
    for alias in pytest_aliases:
        prefix = f"{alias}.mark."
        if name.startswith(prefix):
            return name.removeprefix(prefix)
    for alias in pytest_mark_aliases:
        prefix = f"{alias}."
        if name.startswith(prefix):
            return name.removeprefix(prefix)
    return None


def _unit_live_marker_intersections(tree: ast.AST) -> list[tuple[int, str]]:
    """Return ``(lineno, item_name)`` for tests marked as both unit and live."""
    return _skip_inventory_sites(tree).unit_live_intersections


def _skip_policy_inventory_for_module_trees(
    module_trees: Iterable[tuple[str, ast.AST]],
    *,
    test_module_relatives: frozenset[str] | None = None,
) -> _SkipPolicyInventory:
    """Return formatted skip policy violations for already parsed modules."""
    test_modules = test_module_relatives or frozenset()
    shortcut_violations: list[str] = []
    unit_live_violations: list[str] = []

    for relative, tree in module_trees:
        inventory = _skip_inventory_sites(tree)
        sites = _filter_forbidden_marker_sites_for_relative(relative, tree, inventory.forbidden_sites)
        for lineno, marker_or_call_name in sites:
            shortcut_violations.append(f"{relative}:{lineno}: {marker_or_call_name}")
        if relative in test_modules:
            for lineno, item_name in inventory.unit_live_intersections:
                unit_live_violations.append(f"{relative}:{lineno}: {item_name}")

    return _SkipPolicyInventory(
        shortcut_violations=shortcut_violations,
        unit_live_violations=unit_live_violations,
    )


def _skip_policy_inventory_for_source(
    relative_path: str,
    source: str,
    *,
    is_test_module: bool = False,
) -> _SkipPolicyInventory:
    """Return policy violations for one in-memory source module."""
    tree = ast.parse(source, filename=relative_path)
    test_modules = frozenset({relative_path}) if is_test_module else None
    return _skip_policy_inventory_for_module_trees(((relative_path, tree),), test_module_relatives=test_modules)


def _shortcut_violation_name_counts(violations: Iterable[str]) -> Counter[str]:
    """Return canonical violation names from formatted policy messages."""
    return Counter(violation.rsplit(": ", maxsplit=1)[-1] for violation in violations)


@pytest.fixture(scope="module")
def skip_policy_inventory(source_tree_ast: Mapping[Path, ast.AST]) -> _SkipPolicyInventory:
    """Return skip/xfail and unit/live policy violations for test controls."""
    module_trees: list[tuple[str, ast.AST]] = []
    for module_path in discover_test_control_modules():
        relative = repo_relative(module_path)
        tree = ast_for_path(module_path, source_tree_ast)
        if tree is None:
            continue
        module_trees.append((relative, tree))
    return _skip_policy_inventory_for_module_trees(
        module_trees,
        test_module_relatives=frozenset(repo_relative(path) for path in discover_test_modules()),
    )


def test_no_skip_or_xfail_shortcuts(skip_policy_inventory: _SkipPolicyInventory) -> None:
    """Deterministic production tests and support files must not use skip / xfail shortcuts."""
    violations = skip_policy_inventory.shortcut_violations

    assert not violations, (
        "Undocumented pytest skip / xfail shortcuts found "
        "(remove the shortcut or route live collection opt-in through the central live gate):\n" + "\n".join(violations)
    )


@pytest.mark.parametrize(
    ("source", "expected_violations"),
    (
        pytest.param(
            """
import pytest

pytest.importorskip("optional_dependency")
""",
            Counter({"pytest.importorskip": 1}),
            id="import-time-pytest-skip",
        ),
        pytest.param(
            """
import pytest

pytestmark = [pytest.mark.skip]
""",
            Counter({"pytest.mark.skip": 1}),
            id="module-pytestmark-skip",
        ),
        pytest.param(
            """
import pytest

CASES = [
    pytest.param("skip-case", marks=pytest.mark.skip(reason="shortcut")),
    pytest.param("xfail-case", marks=pytest.mark.xfail(reason="shortcut")),
]
""",
            Counter({"pytest.mark.skip": 1, "pytest.mark.xfail": 1}),
            id="param-level-skip-xfail-marks",
        ),
        pytest.param(
            """
import pytest as pt

def test_alias_shortcut():
    pt.skip("shortcut")

pytestmark = [pt.mark.xfail]
""",
            Counter({"pytest.skip": 1, "pytest.mark.xfail": 1}),
            id="pytest-module-alias",
        ),
        pytest.param(
            """
import pytest

pt = pytest
pt2: object = pt

def test_alias_shortcut():
    pt2.skip("shortcut")

pytestmark = [pt2.mark.xfail]
""",
            Counter({"pytest.skip": 1, "pytest.mark.xfail": 1}),
            id="assigned-pytest-module",
        ),
        pytest.param(
            """
import pytest as pt

pytest_mark = pt.mark
skip_now = pt.skip
xfail_now = pt.xfail

pytestmark = [pytest_mark.skipif(True)]

def test_shortcut_aliases():
    skip_now("shortcut")
    xfail_now("shortcut")
""",
            Counter({"pytest.mark.skipif": 1, "pytest.skip": 1, "pytest.xfail": 1}),
            id="assigned-pytest-mark-and-shortcuts",
        ),
        pytest.param(
            """
import unittest
import unittest.case as unittest_case

UnitSkip = unittest.SkipTest
CaseSkip = unittest_case.SkipTest
DirectSkip = UnitSkip

def test_unit_alias_raise():
    raise UnitSkip("missing dependency")

def test_case_alias_raise():
    raise CaseSkip("missing dependency")

def test_transitive_alias_raise():
    raise DirectSkip("missing dependency")
""",
            Counter({"unittest.SkipTest": 2, "unittest.case.SkipTest": 1}),
            id="assigned-unittest-skiptest",
        ),
        pytest.param(
            """
import unittest

unit = unittest
case_mod = unit.case
case_mod2: object = case_mod

def test_unit_module_alias_raise():
    raise unit.SkipTest("missing dependency")

def test_case_module_alias_raise():
    raise case_mod2.SkipTest("missing dependency")
""",
            Counter({"unittest.SkipTest": 1, "unittest.case.SkipTest": 1}),
            id="assigned-unittest-module",
        ),
        pytest.param(
            """
from pytest import importorskip, skip as pytest_skip

pytest_skip("shortcut")
importorskip("optional_dependency")
""",
            Counter({"pytest.skip": 1, "pytest.importorskip": 1}),
            id="imported-pytest-shortcut-aliases",
        ),
        pytest.param(
            """
from pytest import mark as pytest_mark

pytestmark = [pytest_mark.skipif(True)]
""",
            Counter({"pytest.mark.skipif": 1}),
            id="imported-pytest-mark-alias",
        ),
        pytest.param(
            """
import unittest
from unittest import SkipTest

def test_direct_skiptest_raise():
    raise SkipTest("missing dependency")

def test_qualified_skiptest_raise():
    raise unittest.SkipTest("missing dependency")
""",
            Counter({"SkipTest": 1, "unittest.SkipTest": 1}),
            id="unittest-skiptest-raises",
        ),
        pytest.param(
            """
import unittest as unit_test
from unittest import SkipTest as UnitSkip

def test_direct_skiptest_alias_raise():
    raise UnitSkip("missing dependency")

def test_qualified_skiptest_alias_raise():
    raise unit_test.SkipTest("missing dependency")
""",
            Counter({"SkipTest": 1, "unittest.SkipTest": 1}),
            id="aliased-unittest-skiptest-raises",
        ),
        pytest.param(
            """
import unittest
import unittest.case as unittest_case
from unittest import case as unit_case
from unittest.case import SkipTest as CaseSkip

def test_qualified_unittest_case_raise():
    raise unittest.case.SkipTest("missing dependency")

def test_imported_case_module_raise():
    raise unittest_case.SkipTest("missing dependency")

def test_imported_case_attr_raise():
    raise unit_case.SkipTest("missing dependency")

def test_direct_case_skip_alias_raise():
    raise CaseSkip("missing dependency")
""",
            Counter({"unittest.case.SkipTest": 3, "SkipTest": 1}),
            id="unittest-case-skiptest-raises",
        ),
    ),
)
def test_skip_policy_rejects_forbidden_shortcut_shapes(
    source: str,
    expected_violations: Counter[str],
) -> None:
    """Skip, xfail, and SkipTest shortcuts must fail through the real policy path."""
    inventory = _skip_policy_inventory_for_source("dev/tests/test_forbidden_skip_shapes.py", source)

    assert _shortcut_violation_name_counts(inventory.shortcut_violations) == expected_violations


def test_skip_detector_rejects_support_file_skip_helpers() -> None:
    """Support-file helpers cannot hide selected live-test skips."""
    source = """
import pytest

def requires_live_enabled():
    pytest.skip("live only")

def requires_live_google_enabled():
    pytest.skip("google live only")

def rogue_helper():
    pytest.skip("shortcut")
"""
    inventory = _skip_policy_inventory_for_source("src/cadrumo/tests/live_gate.py", source)

    assert _shortcut_violation_name_counts(inventory.shortcut_violations) == Counter({"pytest.skip": 3})


def test_skip_detector_rejects_live_module_local_skip() -> None:
    """Live test modules are marker-gated; selected live tests must not self-skip."""
    source = """
import pytest

pytestmark = [pytest.mark.aeat_live]

def test_live_service():
    pytest.skip("service unavailable")
"""
    inventory = _skip_policy_inventory_for_source("src/cadrumo/application/live/tests/test_service_live.py", source)

    assert _shortcut_violation_name_counts(inventory.shortcut_violations) == Counter({"pytest.skip": 1})


def test_skip_detector_rejects_collection_live_skip_marker() -> None:
    """Collection hooks cannot turn selected live tests into green skips."""
    source = """
import pytest

def pytest_collection_modifyitems(config, items):
    skip_marker = pytest.mark.skip(reason="live disabled")

def rogue_helper():
    pytestmark = [pytest.mark.skip]
"""
    inventory = _skip_policy_inventory_for_source("conftest.py", source)

    assert _shortcut_violation_name_counts(inventory.shortcut_violations) == Counter({"pytest.mark.skip": 2})


def test_unit_tests_are_not_live_gated(skip_policy_inventory: _SkipPolicyInventory) -> None:
    """Unit tests must not also carry the live opt-in marker."""
    violations = skip_policy_inventory.unit_live_violations

    assert not violations, "Tests cannot be marked both unit and aeat_live:\n" + "\n".join(violations)


def test_unit_live_detector_rejects_pytest_alias_execution_markers() -> None:
    """Aliased pytest execution markers must not hide unit/live intersections."""
    source = """
import pytest as pt

pytestmark = [pt.mark.unit]

@pt.mark.aeat_live
def test_live_unit():
    pass
"""
    inventory = _skip_policy_inventory_for_source("dev/tests/test_live_unit.py", source, is_test_module=True)

    assert _shortcut_violation_name_counts(inventory.unit_live_violations) == Counter({"test_live_unit": 1})


def test_unit_live_detector_rejects_annotated_and_augmented_pytestmark() -> None:
    """Annotated and augmented pytestmark assignments are still module markers."""
    annotated_source = """
import pytest as pt

pytestmark: list[object] = [pt.mark.unit]

@pt.mark.aeat_live
def test_annotated_live_unit():
    pass
"""
    augmented_source = """
import pytest as pt

pytestmark = []
pytestmark += [pt.mark.unit]

@pt.mark.aeat_live
def test_augmented_live_unit():
    pass
"""
    annotated_inventory = _skip_policy_inventory_for_source(
        "dev/tests/test_annotated_live_unit.py",
        annotated_source,
        is_test_module=True,
    )
    augmented_inventory = _skip_policy_inventory_for_source(
        "dev/tests/test_augmented_live_unit.py",
        augmented_source,
        is_test_module=True,
    )

    assert _shortcut_violation_name_counts(annotated_inventory.unit_live_violations) == Counter(
        {"test_annotated_live_unit": 1}
    )
    assert _shortcut_violation_name_counts(augmented_inventory.unit_live_violations) == Counter(
        {"test_augmented_live_unit": 1}
    )


def test_project_tests_outside_source_tree_do_not_skip() -> None:
    """Project tests outside ``src/cadrumo`` must not self-skip or xfail."""
    project_modules = project_test_control_modules()
    # Floor the corpus: this walk covers the project test trees outside
    # ``src/cadrumo`` (the sibling guardrail floors only the in-tree discovery, not
    # this one). A relocation of those roots would empty the walk and pass the
    # self-skip ban vacuously.
    assert len(project_modules) > 20, (
        f"discovered only {len(project_modules)} project test modules outside src/cadrumo; the "
        "scan corpus collapsed (a test-root relocation or rename), so an empty violation list "
        "would mean 'nothing was checked' rather than 'nothing is wrong'"
    )
    violations: list[str] = []
    for module_path in project_modules:
        tree = ast_for_path(module_path)
        if tree is None:
            continue
        relative = repo_relative(module_path)
        for lineno, marker_or_call_name in _forbidden_project_marker_sites_for_relative(relative, tree):
            violations.append(f"{relative}:{lineno}: {marker_or_call_name}")
    assert not violations, "Project tests outside src/cadrumo cannot skip or xfail:\n" + "\n".join(violations)


def test_unit_skip_detector_ignores_integration_only_skip_sites() -> None:
    """An integration-only skip in a mixed module is not selected by ``-m unit``."""
    source = """
import pytest

@pytest.mark.integration
def test_live_service():
    pytest.skip("service unavailable")

@pytest.mark.unit
def test_unit_contract():
    assert compute() == 1
"""
    tree = ast.parse(source)

    assert _forbidden_unit_marker_sites_for_relative("dev/tests/test_mixed.py", tree) == []


def test_unit_skip_detector_rejects_module_level_skip_when_unit_item_exists() -> None:
    """Import-time skips affect unit items even when the module marker is per-test."""
    source = """
import pytest

pytest.importorskip("optional_dependency")

@pytest.mark.unit
def test_unit_contract():
    assert compute() == 1
"""
    tree = ast.parse(source)

    assert Counter(name for _, name in _forbidden_unit_marker_sites_for_relative("dev/tests/test_unit.py", tree)) == (
        Counter({"pytest.importorskip": 1})
    )


def test_unit_skip_detector_rejects_imported_mark_alias_unit_context() -> None:
    """Imported pytest.mark aliases must still mark unit-selected skip sites."""
    source = """
from pytest import mark as pytest_mark

@pytest_mark.unit
def test_unit_contract():
    pytest.skip("service unavailable")
"""
    tree = ast.parse(source)

    assert Counter(name for _, name in _forbidden_unit_marker_sites_for_relative("dev/tests/test_unit.py", tree)) == (
        Counter({"pytest.skip": 1})
    )


def test_discovery_found_modules() -> None:
    """Guardrail: the discovery walk must find at least one test module."""
    modules = discover_test_control_modules()
    assert modules, "No test/control modules discovered — check glob roots."
