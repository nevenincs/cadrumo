"""Static guard: zero skip / xfail shortcuts in deterministic production tests.

Walks every deterministic test, test-support, and ``conftest.py`` module under
``src/aeat/`` via AST and asserts that deterministic modules carry no
``pytest.mark.skip``, ``pytest.mark.skipif``, ``pytest.mark.xfail``,
``pytest.skip()``, or ``pytest.xfail()`` shortcuts. Import-time skips and
``unittest.SkipTest`` raises are forbidden as well, including pytest alias
forms.

Live modules are deselected by marker and collection-level opt-in. Once selected,
they must not self-skip; only the central live gate support may emit skip
markers. No item may carry both ``unit`` and ``aeat_live`` markers.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path
from typing import NamedTuple

import pytest

from ._inventory import (
    ast_for_path,
    discover_test_control_modules,
    discover_test_modules,
    project_test_control_modules,
    qualified_name,
    repo_relative,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_FORBIDDEN_MARKERS = frozenset({"skip", "skipif", "xfail"})
_FORBIDDEN_CALL_NAMES = frozenset({"importorskip", "skip", "xfail"})
_FORBIDDEN_CALLS = frozenset({f"pytest.{name}" for name in _FORBIDDEN_CALL_NAMES})
_FORBIDDEN_EXCEPTIONS = frozenset({"SkipTest", "unittest.SkipTest"})
_LIVE_EXECUTION_MARKER = "aeat_live"
_UNIT_EXECUTION_MARKER = "unit"
_LIVE_GATE_SUPPORT_RELATIVE = "src/aeat/tests/live_gate.py"
_LIVE_GATE_HELPERS = frozenset({"requires_live_enabled", "requires_live_google_enabled"})
_LIVE_CONFTST_RELATIVE = "src/aeat/tests/conftest.py"
_LIVE_COLLECTION_HOOK = "pytest_collection_modifyitems"


class _SkipAliasInventory(NamedTuple):
    pytest_aliases: set[str]
    pytest_mark_aliases: set[str]
    pytest_shortcut_aliases: dict[str, str]
    unittest_aliases: set[str]
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
    module_markers = _module_execution_markers(tree)
    aliases = _skip_alias_inventory(tree)
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
                aliases.skiptest_aliases,
            )
            if exception_name in _FORBIDDEN_EXCEPTIONS:
                forbidden_sites.append((node.lineno, exception_name))

        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            markers = module_markers | _decorator_execution_markers(node)
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
    """Apply central live-gate exceptions to raw skip/xfail sites."""
    if not sites or relative_path not in {_LIVE_GATE_SUPPORT_RELATIVE, _LIVE_CONFTST_RELATIVE}:
        return sites
    function_context = _function_context_by_lineno(tree)
    return [
        (lineno, marker_or_call_name)
        for lineno, marker_or_call_name in sites
        if not _is_allowed_live_skip_support_site(relative_path, lineno, marker_or_call_name, function_context)
    ]


def _function_context_by_lineno(tree: ast.AST) -> dict[int, tuple[str, ...]]:
    """Return lexical function/class context keyed by source line."""
    context: dict[int, tuple[str, ...]] = {}

    def visit(node: ast.AST, stack: tuple[str, ...]) -> None:
        lineno = getattr(node, "lineno", None)
        if isinstance(lineno, int):
            context.setdefault(lineno, stack)
        child_stack = stack
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            child_stack = (*stack, node.name)
        for child in ast.iter_child_nodes(node):
            visit(child, child_stack)

    visit(tree, ())
    return context


def _unit_context_by_lineno(tree: ast.AST) -> dict[int, bool]:
    """Return whether each source line belongs to a unit-selected test context."""
    module_is_unit = _UNIT_EXECUTION_MARKER in _module_execution_markers(tree)
    module_has_unit_items = module_is_unit or any(
        isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
        and _UNIT_EXECUTION_MARKER in _decorator_execution_markers(node)
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
            child_unit = inherited_unit or _UNIT_EXECUTION_MARKER in _decorator_execution_markers(node)
            child_inside_item = True
        for child in ast.iter_child_nodes(node):
            visit(child, child_unit, child_inside_item)

    visit(tree, module_is_unit, False)
    return context


def _is_allowed_live_skip_support_site(
    relative_path: str,
    lineno: int,
    marker_or_call_name: str,
    function_context: Mapping[int, tuple[str, ...]],
) -> bool:
    """Return True for the two central live-test skip mechanisms."""
    context = function_context.get(lineno, ())
    if relative_path == _LIVE_GATE_SUPPORT_RELATIVE and marker_or_call_name == "pytest.skip":
        return any(name in _LIVE_GATE_HELPERS for name in context)
    return (
        relative_path == _LIVE_CONFTST_RELATIVE
        and marker_or_call_name == "pytest.mark.skip"
        and _LIVE_COLLECTION_HOOK in context
    )


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
    skiptest_aliases: dict[str, str] = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "pytest":
                    pytest_aliases.add(alias.asname or alias.name)
                elif alias.name == "unittest":
                    unittest_aliases.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module == "pytest":
            for alias in node.names:
                if alias.name == "mark":
                    pytest_mark_aliases.add(alias.asname or alias.name)
                elif alias.name in _FORBIDDEN_CALL_NAMES:
                    pytest_shortcut_aliases[alias.asname or alias.name] = f"pytest.{alias.name}"
        elif isinstance(node, ast.ImportFrom) and node.module == "unittest":
            for alias in node.names:
                if alias.name == "SkipTest":
                    skiptest_aliases[alias.asname or alias.name] = "SkipTest"

    return _SkipAliasInventory(
        pytest_aliases=pytest_aliases,
        pytest_mark_aliases=pytest_mark_aliases,
        pytest_shortcut_aliases=pytest_shortcut_aliases,
        unittest_aliases=unittest_aliases,
        skiptest_aliases=skiptest_aliases,
    )


def _canonical_skiptest_exception_name(
    exception_name: str,
    unittest_aliases: set[str],
    skiptest_aliases: dict[str, str],
) -> str:
    """Return canonical SkipTest exception names for unittest aliases."""
    direct_alias = skiptest_aliases.get(exception_name)
    if direct_alias is not None:
        return direct_alias
    for alias in unittest_aliases:
        if exception_name == f"{alias}.SkipTest":
            return "unittest.SkipTest"
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
    return _skip_inventory_sites(tree).unit_live_intersections


@pytest.fixture(scope="module")
def skip_policy_inventory() -> _SkipPolicyInventory:
    """Return skip/xfail and unit/live policy violations for test controls."""
    shortcut_violations: list[str] = []
    unit_live_violations: list[str] = []
    test_modules = frozenset(discover_test_modules())
    for module_path in discover_test_control_modules():
        relative = repo_relative(module_path)
        tree = ast_for_path(module_path)
        if tree is None:
            continue
        inventory = _skip_inventory_sites(tree)
        sites = _filter_forbidden_marker_sites_for_relative(relative, tree, inventory.forbidden_sites)
        for lineno, marker_or_call_name in sites:
            shortcut_violations.append(f"{relative}:{lineno}: {marker_or_call_name}")
        if module_path in test_modules:
            for lineno, item_name in inventory.unit_live_intersections:
                unit_live_violations.append(f"{relative}:{lineno}: {item_name}")
    return _SkipPolicyInventory(
        shortcut_violations=shortcut_violations,
        unit_live_violations=unit_live_violations,
    )


def test_no_skip_or_xfail_shortcuts(skip_policy_inventory: _SkipPolicyInventory) -> None:
    """Deterministic production tests and support files must not use skip / xfail shortcuts."""
    violations = skip_policy_inventory.shortcut_violations

    assert not violations, (
        "Undocumented pytest skip / xfail shortcuts found "
        "(remove the shortcut or route live collection opt-in through the central live gate):\n" + "\n".join(violations)
    )


def test_skip_detector_rejects_import_time_pytest_skip() -> None:
    """Import-time dependency skips must not bypass deterministic collection."""
    tree = ast.parse(
        """
import pytest

pytest.importorskip("optional_dependency")
"""
    )

    assert _forbidden_marker_sites(tree) == [(4, "pytest.importorskip")]


def test_skip_detector_rejects_module_level_pytestmark_skip() -> None:
    """Module-level pytestmark skips must not bypass decorator detection."""
    tree = ast.parse(
        """
import pytest

pytestmark = [pytest.mark.skip]
"""
    )

    assert _forbidden_marker_sites(tree) == [(4, "pytest.mark.skip")]


def test_skip_detector_rejects_param_level_skip_or_xfail_marks() -> None:
    """Parametrized case marks are still deterministic skip / xfail shortcuts."""
    tree = ast.parse(
        """
import pytest

CASES = [
    pytest.param("skip-case", marks=pytest.mark.skip(reason="shortcut")),
    pytest.param("xfail-case", marks=pytest.mark.xfail(reason="shortcut")),
]
"""
    )

    assert _forbidden_marker_sites(tree) == [(5, "pytest.mark.skip"), (6, "pytest.mark.xfail")]


def test_skip_detector_rejects_pytest_module_alias_shortcuts() -> None:
    """Aliasing pytest must not hide skip / xfail shortcuts."""
    tree = ast.parse(
        """
import pytest as pt

def test_alias_shortcut():
    pt.skip("shortcut")

pytestmark = [pt.mark.xfail]
"""
    )

    assert _forbidden_marker_sites(tree) == [(5, "pytest.skip"), (7, "pytest.mark.xfail")]


def test_skip_detector_rejects_pytest_imported_shortcut_aliases() -> None:
    """Directly imported pytest shortcuts must not bypass dotted-name detection."""
    tree = ast.parse(
        """
from pytest import importorskip, skip as pytest_skip

pytest_skip("shortcut")
importorskip("optional_dependency")
"""
    )

    assert _forbidden_marker_sites(tree) == [(4, "pytest.skip"), (5, "pytest.importorskip")]


def test_skip_detector_rejects_imported_pytest_mark_aliases() -> None:
    """Imported pytest.mark aliases must still reject skip and xfail marks."""
    tree = ast.parse(
        """
from pytest import mark as pytest_mark

pytestmark = [pytest_mark.skipif(True)]
"""
    )

    assert _forbidden_marker_sites(tree) == [(4, "pytest.mark.skipif")]


def test_skip_detector_rejects_unittest_skiptest_raises() -> None:
    """SkipTest raises must not bypass the pytest skip shortcut guard."""
    tree = ast.parse(
        """
import unittest
from unittest import SkipTest

def test_direct_skiptest_raise():
    raise SkipTest("missing dependency")

def test_qualified_skiptest_raise():
    raise unittest.SkipTest("missing dependency")
"""
    )

    assert _forbidden_marker_sites(tree) == [(6, "SkipTest"), (9, "unittest.SkipTest")]


def test_skip_detector_rejects_aliased_unittest_skiptest_raises() -> None:
    """Aliased unittest.SkipTest raises are still deterministic skips."""
    tree = ast.parse(
        """
import unittest as unit_test
from unittest import SkipTest as UnitSkip

def test_direct_skiptest_alias_raise():
    raise UnitSkip("missing dependency")

def test_qualified_skiptest_alias_raise():
    raise unit_test.SkipTest("missing dependency")
"""
    )

    assert _forbidden_marker_sites(tree) == [(6, "SkipTest"), (9, "unittest.SkipTest")]


def test_skip_detector_scans_support_files_but_allows_central_live_gate_only() -> None:
    """Support-file skips are allowed only in the central live-gate helper functions."""
    tree = ast.parse(
        """
import pytest

def requires_live_enabled():
    pytest.skip("live only")

def requires_live_google_enabled():
    pytest.skip("google live only")

def rogue_helper():
    pytest.skip("shortcut")
"""
    )

    assert _forbidden_marker_sites_for_relative(_LIVE_GATE_SUPPORT_RELATIVE, tree) == [(11, "pytest.skip")]


def test_skip_detector_rejects_live_module_local_skip() -> None:
    """Live test modules are marker-gated; selected live tests must not self-skip."""
    tree = ast.parse(
        """
import pytest

pytestmark = [pytest.mark.aeat_live]

def test_live_service():
    pytest.skip("service unavailable")
"""
    )

    assert _forbidden_marker_sites(tree) == [(7, "pytest.skip")]


def test_skip_detector_allows_only_collection_live_skip_marker() -> None:
    """The collection hook may mark aeat_live items skipped; other support skips fail."""
    tree = ast.parse(
        """
import pytest

def pytest_collection_modifyitems(config, items):
    skip_marker = pytest.mark.skip(reason="live disabled")

def rogue_helper():
    pytestmark = [pytest.mark.skip]
"""
    )

    assert _forbidden_marker_sites_for_relative(_LIVE_CONFTST_RELATIVE, tree) == [(8, "pytest.mark.skip")]


def test_unit_tests_are_not_live_gated(skip_policy_inventory: _SkipPolicyInventory) -> None:
    """Unit tests must not also carry the live opt-in marker."""
    violations = skip_policy_inventory.unit_live_violations

    assert not violations, "Tests cannot be marked both unit and aeat_live:\n" + "\n".join(violations)


def test_project_tests_outside_source_tree_do_not_skip() -> None:
    """Project tests outside ``src/aeat`` must not self-skip or xfail."""
    violations: list[str] = []
    for module_path in project_test_control_modules():
        tree = ast_for_path(module_path)
        if tree is None:
            continue
        relative = repo_relative(module_path)
        for lineno, marker_or_call_name in _forbidden_project_marker_sites_for_relative(relative, tree):
            violations.append(f"{relative}:{lineno}: {marker_or_call_name}")
    assert not violations, "Project tests outside src/aeat cannot skip or xfail:\n" + "\n".join(violations)


def test_unit_skip_detector_ignores_integration_only_skip_sites() -> None:
    """An integration-only skip in a mixed module is not selected by ``-m unit``."""
    tree = ast.parse(
        """
import pytest

@pytest.mark.integration
def test_live_service():
    pytest.skip("service unavailable")

@pytest.mark.unit
def test_unit_contract():
    assert compute() == 1
"""
    )

    assert _forbidden_unit_marker_sites_for_relative("dev/tests/test_mixed.py", tree) == []


def test_unit_skip_detector_rejects_module_level_skip_when_unit_item_exists() -> None:
    """Import-time skips affect unit items even when the module marker is per-test."""
    tree = ast.parse(
        """
import pytest

pytest.importorskip("optional_dependency")

@pytest.mark.unit
def test_unit_contract():
    assert compute() == 1
"""
    )

    assert _forbidden_unit_marker_sites_for_relative("dev/tests/test_unit.py", tree) == [
        (4, "pytest.importorskip"),
    ]


def test_discovery_found_modules() -> None:
    """Guardrail: the discovery walk must find at least one test module."""
    modules = discover_test_control_modules()
    assert modules, "No test/control modules discovered — check glob roots."
