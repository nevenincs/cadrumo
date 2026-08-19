"""Static guard: forbidden test-control inventory for production tests.

Walks every deterministic test, test-support, and ``conftest.py`` module under
``src/cadrumo/`` via AST and classifies each ``unittest`` / ``mock`` /
``pytest_mock`` import plus imported, assigned, or locally defined helpers
named like test doubles.

Classification rule:
- Any mock import under deterministic production tests is drift.
- Any pytest-mock ``mocker`` fixture reference is drift.
- Any imported, assigned, or locally defined ``Mock*``, ``Fake*``, ``Stub*``,
  ``Spy*``, or ``Dummy*`` test helper is drift.
- Semantic helper-class names that advertise supplied behavior (recording,
  canned/fixed responses, unavailable/corrupt dependencies, call counting,
  import blocking, or forced exceptions) are also drift. Real loopback HTTP
  endpoint handlers are explicitly exempt because they cross the production
  network boundary.

Current inventory for durable replacement:
  Zero ``unittest``, ``mock``, or ``pytest_mock`` imports found in deterministic
  tests, test-support modules, or conftests under ``src/cadrumo/``.  The codebase
  uses constructor injection with inline callables for boundary-injection sites
  rather than the mock library. Zero imported, assigned, or locally defined
  mock/fake/stub/spy/dummy helper classes or functions.

The tests assert that neither mock imports nor test-double definitions appear.

See Also:
    :mod:`~tests.test_monkeypatch_inventory`
        Companion production-test guard for monkeypatch mutation shortcuts.
    :mod:`~tests.test_no_skip_xfail`
        Companion guard for skip and xfail shortcuts across deterministic tests.
    :func:`~tests._inventory.discover_test_control_modules`
        Shared inventory surface walked by this test-control ratchet.
    :class:`_TestControlInventorySites`
        AST-level site carrier collected for each inspected source tree.
    :class:`_TestControlInventoryViolations`
        Formatted violation aggregate consumed by the public assertions.
"""

from __future__ import annotations

import ast
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Final, NamedTuple

import pytest

from cadrumo.tests._inventory import ast_for_path, repo_relative

from ._project_inventory import all_test_control_modules

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# Import module names that constitute banned test-control usage.
_FORBIDDEN_TEST_CONTROL_IMPORTS = ("unittest.mock", "unittest", "mock", "pytest_mock")
_FORBIDDEN_TEST_DOUBLE_PREFIXES = ("mock", "fake", "stub", "spy", "dummy")
_FORBIDDEN_SEMANTIC_DOUBLE_DEFINITION_TOKENS = (
    "alwaysclosed",
    "alwaysopen",
    "canned",
    "corrupt",
    "counting",
    "dangling",
    "fixedvector",
    "importblocker",
    "nowindows",
    "recording",
    "reconfigurable",
    "refusing",
    "raising",
    "storedobservation",
    "unavailable",
)
#: Class names that MATCH a forbidden token above and are nonetheless real.
#:
#: Every token above describes what a test double advertises, so a class that
#: genuinely delegates to a live boundary and merely observes what crossed it
#: reads as a double by name while being the opposite by behaviour. Each entry
#: states why it is real, because a bare name carries no way to tell the two
#: apart on review, and the liveness check below removes entries whose class or
#: whose token has gone. Read the class before adding one: the question is
#: whether every call reaches the real dependency, not whether the name is
#: inconvenient.
_ALLOWED_REAL_BOUNDARY_DEFINITION_NAMES: Final[Mapping[str, str]] = {
    "recordingtelemetryendpoint": ("delegates to the live telemetry endpoint and records what crossed it"),
    "recordingattachmentstore": (
        "wraps a concrete AttachmentStore so bytes reach real encrypted custody; "
        "the recording only observes the port, and put_file raises rather than "
        "answering, so a filesystem path on that path fails loudly"
    ),
    "refusingattachmentstore": (
        "the recording store above with a real byte-write failure injected, which "
        "is how the suite asks whether a second custody write path exists; the "
        "refusal is the behaviour under test, not a stand-in for one"
    ),
}
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

    test_control_and_pytest_mock_usage: tuple[str, ...]
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

        if (
            isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
            and not node.name.startswith("test_")
            and (
                _is_test_double_name(node.name)
                or (isinstance(node, ast.ClassDef) and _is_semantic_test_double_class_name(node.name))
            )
        ):
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
    elif isinstance(node, ast.AnnAssign | ast.AugAssign | ast.For | ast.AsyncFor | ast.NamedExpr):
        targets = [node.target]
        lineno = node.lineno
    elif isinstance(node, ast.comprehension):
        targets = [node.target]
        lineno = getattr(node.target, "lineno", None)
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
    if isinstance(target, ast.Attribute):
        return [target.attr]
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
    normalized = name.strip("_").lower()
    return any(
        normalized.startswith(prefix) or normalized.endswith(prefix) for prefix in _FORBIDDEN_TEST_DOUBLE_PREFIXES
    )


def _is_semantic_test_double_class_name(name: str) -> bool:
    """Return True for class names that advertise supplied dependency behavior."""
    normalized = name.strip("_").lower()
    if normalized in _ALLOWED_REAL_BOUNDARY_DEFINITION_NAMES:
        return False
    return any(token in normalized for token in _FORBIDDEN_SEMANTIC_DOUBLE_DEFINITION_TOKENS)


def test_every_allowed_real_boundary_name_is_still_live() -> None:
    """Each allowed name must still be flaggable and must still name a real class.

    Two failure modes, and an existence check would catch only one. A name that
    no longer matches any forbidden token is redundant -- the detector would not
    flag it anyway -- while a name matching no class in the corpus exempts
    nothing today and silently pre-authorises whatever class later takes it.
    Both leave the entry reading as live coverage, so both are checked.
    """
    defined: set[str] = set()
    for path in all_test_control_modules():
        tree = ast_for_path(path)
        if tree is None:
            continue
        defined.update(node.name.strip("_").lower() for node in ast.walk(tree) if isinstance(node, ast.ClassDef))

    assert len(defined) > 50, (
        f"only {len(defined)} class definitions found across the test-control corpus; the scan "
        "collapsed, so the liveness check below would pass by examining nothing"
    )

    stale: list[str] = []
    for allowed, reason in sorted(_ALLOWED_REAL_BOUNDARY_DEFINITION_NAMES.items()):
        if not any(token in allowed for token in _FORBIDDEN_SEMANTIC_DOUBLE_DEFINITION_TOKENS):
            stale.append(f"{allowed} (matches no forbidden token; the exemption is redundant)")
        if allowed not in defined:
            stale.append(f"{allowed} (no class of this name is defined in the scanned corpus)")
        if len(reason.split()) < 5:
            stale.append(f"{allowed} (states no reason worth reading; say why the class is real)")
    assert not stale, "Stale _ALLOWED_REAL_BOUNDARY_DEFINITION_NAMES entries; remove them:\n" + "\n".join(
        f"  {entry}" for entry in stale
    )


def _test_control_inventory_for_module_trees(
    module_trees: Iterable[tuple[str, ast.AST]],
) -> _TestControlInventoryViolations:
    """Return formatted test-control policy violations for parsed modules."""
    test_control_and_pytest_mock_usage: list[str] = []
    test_double_imports: list[str] = []
    test_double_bindings: list[str] = []
    test_double_definitions: list[str] = []

    for relative, tree in module_trees:
        sites = _test_control_inventory_sites(tree)
        for lineno, banned_module in sites.test_control_imports:
            test_control_and_pytest_mock_usage.append(f"{relative}:{lineno}: import {banned_module}")
        for lineno, reference in sites.pytest_mock_fixture_refs:
            test_control_and_pytest_mock_usage.append(f"{relative}:{lineno}: {reference}")
        for lineno, name in sites.test_double_imports:
            test_double_imports.append(f"{relative}:{lineno}: {name}")
        for lineno, name in sites.test_double_assignments:
            test_double_bindings.append(f"{relative}:{lineno}: {name}")
        for lineno, name in sites.test_double_definitions:
            test_double_definitions.append(f"{relative}:{lineno}: {name}")

    return _TestControlInventoryViolations(
        test_control_and_pytest_mock_usage=tuple(test_control_and_pytest_mock_usage),
        test_double_imports=tuple(test_double_imports),
        test_double_bindings=tuple(test_double_bindings),
        test_double_definitions=tuple(test_double_definitions),
    )


def _test_control_inventory_for_source(relative_path: str, source: str) -> _TestControlInventoryViolations:
    """Return formatted test-control policy violations for one in-memory source module."""
    tree = ast.parse(source, filename=relative_path)
    return _test_control_inventory_for_module_trees(((relative_path, tree),))


def _violation_suffix_counts(violations: Iterable[str]) -> Counter[str]:
    """Return policy violation suffix counts independent of source line numbers."""
    return Counter(violation.rsplit(": ", maxsplit=1)[-1] for violation in violations)


@pytest.fixture(scope="module")
def test_control_inventory(source_tree_ast: Mapping[Path, ast.AST]) -> _TestControlInventoryViolations:
    """Return all mock/test-double policy violations from one test-control inventory pass."""
    module_trees: list[tuple[str, ast.AST]] = []
    for module_path in all_test_control_modules():
        tree = ast_for_path(module_path, source_tree_ast)
        if tree is None:
            continue
        module_trees.append((repo_relative(module_path), tree))
    return _test_control_inventory_for_module_trees(module_trees)


def test_no_mock_imports_or_pytest_mock_fixture_refs(
    test_control_inventory: _TestControlInventoryViolations,
) -> None:
    """No deterministic production test may import mock libraries or use pytest-mock."""
    violations = test_control_inventory.test_control_and_pytest_mock_usage

    assert not violations, "Banned mock-library or pytest-mock fixture usage found:\n" + "\n".join(violations)


@pytest.mark.parametrize(
    (
        "source",
        "expected_usage",
        "expected_imports",
        "expected_bindings",
        "expected_definitions",
    ),
    (
        pytest.param(
            """
import unittest
import unittest.mock as mock_lib
from unittest import mock
import mock
import pytest_mock
""",
            Counter(
                {
                    "import unittest": 1,
                    "import unittest.mock": 2,
                    "import mock": 1,
                    "import pytest_mock": 1,
                }
            ),
            Counter({"mock": 3, "pytest_mock": 1}),
            Counter(),
            Counter(),
            id="banned-mock-imports",
        ),
        pytest.param(
            """
def test_uses_pytest_mock_fixture(mocker):
    mocker.patch("aeat.module.boundary")
""",
            Counter({"argument mocker": 1, "name mocker": 1}),
            Counter(),
            Counter({"mocker": 1}),
            Counter(),
            id="pytest-mock-fixture",
        ),
        pytest.param(
            """
from helpers import MockRepository as ConcreteRepository

MockService = object()
mock_result = object()

def test_argument_binding(mock_client):
    return mock_client

state.mock_client = object()
namespace.fake_service = object()

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
""",
            Counter(),
            Counter({"MockRepository": 1}),
            Counter(
                {
                    "MockService": 1,
                    "mock_result": 1,
                    "mock_client": 2,
                    "fake_service": 1,
                    "mock_row": 1,
                    "mock_resource": 1,
                    "mock_error": 1,
                }
            ),
            Counter({"MockTransport": 1, "mock_response_factory": 1}),
            id="mock-named-helpers",
        ),
        pytest.param(
            """
items = [mock_row for mock_row in rows]
mapping = {fake_key: value for fake_key, value in rows}
total = sum(stub.value for stub in rows)
chosen = next((item for item in rows if (dummy_value := item.value)), None)
""",
            Counter(),
            Counter(),
            Counter({"mock_row": 1, "fake_key": 1, "stub": 1, "dummy_value": 1}),
            Counter(),
            id="comprehension-targets",
        ),
        pytest.param(
            """
mock_count += 1
state.fake_counter += 1
""",
            Counter(),
            Counter(),
            Counter({"mock_count": 1, "fake_counter": 1}),
            Counter(),
            id="augmented-assignment-targets",
        ),
        pytest.param(
            """
from helpers import SpyClient

spy_result = object()
namespace.spy_service = object()

class SpyTransport:
    pass

def spy_response_factory():
    return object()
""",
            Counter(),
            Counter({"SpyClient": 1}),
            Counter({"spy_result": 1, "spy_service": 1}),
            Counter({"SpyTransport": 1, "spy_response_factory": 1}),
            id="spy-named-helpers",
        ),
        pytest.param(
            """
from helpers import ClientFake, Repository_Stub as Repository

client_fake = object()
transportStub = object()
namespace.repository_dummy = object()

class TransportSpy:
    pass

def repositoryMock():
    return object()
""",
            Counter(),
            Counter({"ClientFake": 1, "Repository_Stub": 1}),
            Counter({"client_fake": 1, "transportStub": 1, "repository_dummy": 1}),
            Counter({"TransportSpy": 1, "repositoryMock": 1}),
            id="suffix-named-helpers",
        ),
        pytest.param(
            """
class _CannedOracle:
    pass

class _CountingRepository:
    pass

class _RecordingTelemetryEndpoint:
    pass
""",
            Counter(),
            Counter(),
            Counter(),
            Counter({"_CannedOracle": 1, "_CountingRepository": 1}),
            id="semantic-double-helper-names",
        ),
    ),
)
def test_test_control_policy_rejects_forbidden_test_double_shapes(
    source: str,
    expected_usage: Counter[str],
    expected_imports: Counter[str],
    expected_bindings: Counter[str],
    expected_definitions: Counter[str],
) -> None:
    """Banned mocks and test-double names must fail through the real policy path."""
    inventory = _test_control_inventory_for_source("dev/tests/test_mock_policy.py", source)

    assert _violation_suffix_counts(inventory.test_control_and_pytest_mock_usage) == expected_usage
    assert _violation_suffix_counts(inventory.test_double_imports) == expected_imports
    assert _violation_suffix_counts(inventory.test_double_bindings) == expected_bindings
    assert _violation_suffix_counts(inventory.test_double_definitions) == expected_definitions


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
