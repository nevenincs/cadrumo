"""Static guard: forbidden test-control inventory for production tests.

Walks every deterministic test, test-support, and ``conftest.py`` module under
``src/aeat/`` via AST and classifies each ``unittest`` / ``mock`` /
``pytest_mock`` import plus imported, assigned, or locally defined helpers
named like test doubles.

Classification rule:
- Any mock import under deterministic production tests is drift.
- Any pytest-mock ``mocker`` fixture reference is drift.
- Any imported, assigned, or locally defined ``Mock*``, ``Fake*``, ``Stub*``,
  or ``Dummy*`` test helper is drift; tests must name helpers by the concrete
  behaviour or contract they exercise.

Current inventory for durable replacement:
  Zero ``unittest``, ``mock``, or ``pytest_mock`` imports found in deterministic
  tests, test-support modules, or conftests under ``src/aeat/``.  The codebase
  uses constructor injection with inline callables for boundary-injection sites
  rather than the mock library. Zero imported, assigned, or locally defined
  mock/fake/stub/dummy helper classes or functions.

The tests assert that neither mock imports nor test-double definitions appear.
"""

from __future__ import annotations

import ast
from typing import NamedTuple

import pytest

from ._inventory import all_test_control_modules, ast_for_path, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# Import module names that constitute banned test-control usage.
_FORBIDDEN_TEST_CONTROL_IMPORTS = ("unittest.mock", "unittest", "mock", "pytest_mock")
_FORBIDDEN_TEST_DOUBLE_PREFIXES = ("mock", "fake", "stub", "dummy")
_PYTEST_MOCK_FIXTURE_NAME = "mocker"


class _TestControlInventorySites(NamedTuple):
    """Forbidden mock/test-double sites found in one AST."""

    test_control_imports: list[tuple[int, str]]
    pytest_mock_fixture_refs: list[tuple[int, str]]
    test_double_imports: list[tuple[int, str]]
    test_double_assignments: list[tuple[int, str]]
    test_double_definitions: list[tuple[int, str]]


class _TestControlInventoryViolations(NamedTuple):
    """Formatted mock/test-double policy violations for the test-control surface."""

    test_control_and_pytest_mock: tuple[str, ...]
    test_double_imports: tuple[str, ...]
    test_double_bindings: tuple[str, ...]
    test_double_definitions: tuple[str, ...]


def _test_control_inventory_sites(tree: ast.AST) -> _TestControlInventorySites:
    """Return all forbidden mock/test-double sites from one tree walk."""
    test_control_imports: list[tuple[int, str]] = []
    pytest_mock_fixture_refs: list[tuple[int, str]] = []
    test_double_imports: list[tuple[int, str]] = []
    test_double_assignments: list[tuple[int, str]] = []
    test_double_definitions: list[tuple[int, str]] = []

    for node in ast.walk(tree):
        _add_forbidden_import_sites(node, test_control_imports, test_double_imports)

        if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) and _is_test_double_name(node.name):
            test_double_definitions.append((node.lineno, node.name))

        if isinstance(node, ast.arg):
            if node.arg == _PYTEST_MOCK_FIXTURE_NAME:
                pytest_mock_fixture_refs.append((node.lineno, "argument mocker"))
            if _is_test_double_name(node.arg):
                test_double_assignments.append((node.lineno, node.arg))
        elif isinstance(node, ast.Name) and node.id == _PYTEST_MOCK_FIXTURE_NAME:
            pytest_mock_fixture_refs.append((node.lineno, "name mocker"))

        _add_forbidden_binding_sites(node, test_double_assignments)

    return _TestControlInventorySites(
        test_control_imports=test_control_imports,
        pytest_mock_fixture_refs=pytest_mock_fixture_refs,
        test_double_imports=test_double_imports,
        test_double_assignments=test_double_assignments,
        test_double_definitions=test_double_definitions,
    )


def _add_forbidden_import_sites(
    node: ast.AST,
    test_control_imports: list[tuple[int, str]],
    test_double_imports: list[tuple[int, str]],
) -> None:
    """Append forbidden import hits from one AST node."""
    if isinstance(node, ast.Import):
        for alias in node.names:
            hit = _forbidden_import_name(alias.name)
            if hit is not None:
                test_control_imports.append((node.lineno, hit))
            imported_name = _matching_imported_test_double_name(alias.name.rsplit(".", maxsplit=1)[-1], alias.asname)
            if imported_name is not None:
                test_double_imports.append((node.lineno, imported_name))
    elif isinstance(node, ast.ImportFrom):
        module = node.module or ""
        if module == "unittest" and any(alias.name == "mock" for alias in node.names):
            test_control_imports.append((node.lineno, "unittest.mock"))
        else:
            hit = _forbidden_import_name(module)
            if hit is not None:
                test_control_imports.append((node.lineno, hit))
        for alias in node.names:
            imported_name = _matching_imported_test_double_name(alias.name, alias.asname)
            if imported_name is not None:
                test_double_imports.append((node.lineno, imported_name))


def _add_forbidden_binding_sites(node: ast.AST, test_double_assignments: list[tuple[int, str]]) -> None:
    """Append forbidden mock/fake/stub/dummy binding hits from one AST node."""
    targets: list[ast.expr] = []
    lineno: int | None = None
    if isinstance(node, ast.Assign):
        targets = list(node.targets)
        lineno = node.lineno
    elif isinstance(node, ast.AnnAssign | ast.For | ast.AsyncFor):
        targets = [node.target]
        lineno = node.lineno
    for target in targets:
        for name in _target_names(target):
            if lineno is not None and _is_test_double_name(name):
                test_double_assignments.append((lineno, name))

    if isinstance(node, ast.With | ast.AsyncWith):
        for item in node.items:
            if item.optional_vars is None:
                continue
            for name in _target_names(item.optional_vars):
                if _is_test_double_name(name):
                    test_double_assignments.append((node.lineno, name))
    elif isinstance(node, ast.ExceptHandler) and node.name is not None and _is_test_double_name(node.name):
        test_double_assignments.append((node.lineno, node.name))


def _forbidden_test_control_imports(
    tree: ast.AST,
) -> list[tuple[int, str]]:
    """Return ``(lineno, module)`` for every banned test-control import in *tree*."""
    return _test_control_inventory_sites(tree).test_control_imports


def _forbidden_import_name(import_name: str) -> str | None:
    """Return the banned import prefix matched by *import_name*, if any."""
    for prefix in _FORBIDDEN_TEST_CONTROL_IMPORTS:
        if import_name == prefix or import_name.startswith(prefix + "."):
            return prefix
    return None


def _forbidden_test_double_definitions(tree: ast.AST) -> list[tuple[int, str]]:
    """Return ``(lineno, name)`` for locally defined mock/fake/stub/dummy helpers."""
    return _test_control_inventory_sites(tree).test_double_definitions


def _forbidden_test_double_imports(tree: ast.AST) -> list[tuple[int, str]]:
    """Return ``(lineno, name)`` for imported mock/fake/stub/dummy helper names."""
    return _test_control_inventory_sites(tree).test_double_imports


def _matching_imported_test_double_name(original_name: str, alias_name: str | None) -> str | None:
    """Return the imported or alias name that encodes test-double semantics."""
    if _is_test_double_name(original_name):
        return original_name
    if alias_name is not None and _is_test_double_name(alias_name):
        return alias_name
    return None


def _target_names(target: ast.expr) -> list[str]:
    """Return simple names bound by an assignment target."""
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, ast.Tuple | ast.List):
        names: list[str] = []
        for element in target.elts:
            names.extend(_target_names(element))
        return names
    return []


def _forbidden_test_double_assignments(tree: ast.AST) -> list[tuple[int, str]]:
    """Return ``(lineno, name)`` for bound mock/fake/stub/dummy helper names."""
    return _test_control_inventory_sites(tree).test_double_assignments


def _pytest_mock_fixture_sites(tree: ast.AST) -> list[tuple[int, str]]:
    """Return explicit pytest-mock fixture references in *tree*."""
    return _test_control_inventory_sites(tree).pytest_mock_fixture_refs


def _is_test_double_name(name: str) -> bool:
    """Return True for helper names that encode mock/fake/stub/dummy semantics."""
    normalized = name.lstrip("_").lower()
    return any(normalized.startswith(prefix) for prefix in _FORBIDDEN_TEST_DOUBLE_PREFIXES)


@pytest.fixture(scope="module")
def test_control_inventory() -> _TestControlInventoryViolations:
    """Return all mock/test-double policy violations from one test-control inventory pass."""
    test_control_and_pytest_mock: list[str] = []
    test_double_imports: list[str] = []
    test_double_bindings: list[str] = []
    test_double_definitions: list[str] = []

    for module_path in all_test_control_modules():
        relative = repo_relative(module_path)
        tree = ast_for_path(module_path)
        if tree is None:
            continue
        sites = _test_control_inventory_sites(tree)
        for lineno, banned_module in sites.test_control_imports:
            test_control_and_pytest_mock.append(f"{relative}:{lineno}: import {banned_module}")
        for lineno, reference in sites.pytest_mock_fixture_refs:
            test_control_and_pytest_mock.append(f"{relative}:{lineno}: {reference}")
        for lineno, name in sites.test_double_imports:
            test_double_imports.append(f"{relative}:{lineno}: {name}")
        for lineno, name in sites.test_double_assignments:
            test_double_bindings.append(f"{relative}:{lineno}: {name}")
        for lineno, name in sites.test_double_definitions:
            test_double_definitions.append(f"{relative}:{lineno}: {name}")

    return _TestControlInventoryViolations(
        test_control_and_pytest_mock=tuple(test_control_and_pytest_mock),
        test_double_imports=tuple(test_double_imports),
        test_double_bindings=tuple(test_double_bindings),
        test_double_definitions=tuple(test_double_definitions),
    )


def test_no_mock_imports_or_pytest_mock_fixture_refs(
    test_control_inventory: _TestControlInventoryViolations,
) -> None:
    """No deterministic production test may import mock libraries or use pytest-mock."""
    violations = test_control_inventory.test_control_and_pytest_mock

    assert not violations, "Banned mock-library or pytest-mock fixture usage found:\n" + "\n".join(violations)


def test_pytest_mock_fixture_detector_rejects_mocker_argument_and_usage() -> None:
    """The mock inventory must catch pytest-mock usage that has no import site."""
    tree = ast.parse(
        """
def test_uses_pytest_mock_fixture(mocker):
    mocker.patch("aeat.module.boundary")
"""
    )

    assert _pytest_mock_fixture_sites(tree) == [(2, "argument mocker"), (3, "name mocker")]


def test_test_double_name_detector_rejects_mock_named_helpers() -> None:
    """Mock-named helpers are test doubles even without importing a mock library."""
    tree = ast.parse(
        """
from helpers import MockRepository as ConcreteRepository

MockService = object()
mock_result = object()

def test_argument_binding(mock_client):
    return mock_client

for mock_row in (1,):
    pass

with resource() as mock_resource:
    pass

try:
    raise RuntimeError("boom")
except RuntimeError as mock_error:
    pass

class MockTransport:
    pass

def mock_response_factory():
    return object()
"""
    )

    assert _forbidden_test_double_imports(tree) == [(2, "MockRepository")]
    assert set(_forbidden_test_double_assignments(tree)) == {
        (4, "MockService"),
        (5, "mock_result"),
        (7, "mock_client"),
        (10, "mock_row"),
        (13, "mock_resource"),
        (18, "mock_error"),
    }
    assert _forbidden_test_double_definitions(tree) == [(21, "MockTransport"), (24, "mock_response_factory")]


def test_no_fake_stub_or_dummy_imports(
    test_control_inventory: _TestControlInventoryViolations,
) -> None:
    """No deterministic production test may import fake/stub/dummy helpers."""
    violations = test_control_inventory.test_double_imports

    assert not violations, "Banned fake/stub/dummy test helper imports found:\n" + "\n".join(violations)


def test_no_mock_fake_stub_or_dummy_bindings(
    test_control_inventory: _TestControlInventoryViolations,
) -> None:
    """No deterministic production test may bind mock/fake/stub/dummy helper names."""
    violations = test_control_inventory.test_double_bindings

    assert not violations, "Banned mock/fake/stub/dummy test helper bindings found:\n" + "\n".join(violations)


def test_no_fake_stub_or_dummy_definitions(
    test_control_inventory: _TestControlInventoryViolations,
) -> None:
    """No deterministic production test may define fake/stub/dummy helpers."""
    violations = test_control_inventory.test_double_definitions

    assert not violations, "Banned fake/stub/dummy test helper definitions found:\n" + "\n".join(violations)


def test_discovery_found_modules() -> None:
    """Guardrail: the discovery walk must find at least one test module."""
    modules = all_test_control_modules()
    assert modules, "No test modules discovered — check glob roots."
