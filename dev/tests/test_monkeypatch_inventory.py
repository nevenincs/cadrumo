"""Static guard: no monkeypatch use in production tests.

Walks every deterministic test, test-support, and ``conftest.py`` module under
``src/cadrumo/`` via AST and rejects pytest ``monkeypatch`` fixture arguments,
mutation calls, and explicit ``pytest.MonkeyPatch`` / ``_pytest.monkeypatch``
imports, references, and contexts. Process-global isolation should use local
context managers or injectable runtime boundaries instead.

See Also:
    :mod:`~tests.test_mock_inventory`
        Companion production-test guard for mock imports and test-double
        helper definitions.
    :mod:`~tests.test_no_skip_xfail`
        Companion guard for skip and xfail shortcuts across deterministic
        tests.
    :func:`~tests._inventory.all_test_control_modules`
        Shared inventory surface walked by this monkeypatch ratchet.
    :class:`_PatchAliasInventory`
        Alias inventory used to detect pytest and internal monkeypatch names.
    :class:`_PatchInventorySites`
        AST-level monkeypatch mutation, context, and reference sites collected
        for each inspected source tree.
"""

from __future__ import annotations

import ast
from collections import Counter
from collections.abc import Iterable, Mapping
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

_MUTATION_VERBS = frozenset({"setattr", "setitem", "delattr", "setenv", "delenv", "chdir", "syspath_prepend"})
_PATCH_CONTEXT_FACTORIES = frozenset(
    {
        "pytest.MonkeyPatch",
        "pytest.MonkeyPatch.context",
        "_pytest.monkeypatch.MonkeyPatch",
        "_pytest.monkeypatch.MonkeyPatch.context",
        "MonkeyPatch",
        "MonkeyPatch.context",
    },
)
_PATCH_REFERENCE_NAMES = frozenset({"pytest.MonkeyPatch", "_pytest.monkeypatch.MonkeyPatch", "MonkeyPatch"})
_PYTEST_INTERNAL_MONKEYPATCH_MODULE = "_pytest.monkeypatch"


class _PatchAliasInventory(NamedTuple):
    pytest_aliases: set[str]
    internal_pytest_aliases: set[str]
    internal_monkeypatch_aliases: set[str]
    direct_patch_aliases: dict[str, str]
    import_sites: list[tuple[int, str]]


class _PatchInventorySites(NamedTuple):
    mutation_sites: list[tuple[int, str, str | None]]
    context_sites: list[tuple[int, str]]
    reference_sites: list[tuple[int, str]]


def _target_name_from_args(call_node: ast.Call) -> str | None:
    """Extract the target name from a monkeypatch mutation call.

    Handles both ``monkeypatch.setattr(module, "name", value)`` (positional)
    and single-value forms such as ``monkeypatch.setenv("NAME", value)``.
    """
    args = call_node.args
    if not args:
        return None
    first = args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        # String-path form: "sys.stdout", "pkg.module.name"
        return first.value.split(".")[-1]
    if len(args) >= 2:
        second = args[1]
        if isinstance(second, ast.Constant) and isinstance(second.value, str):
            return second.value
    return None


def _mutation_sites(
    tree: ast.AST,
) -> list[tuple[int, str, str | None]]:
    """Return ``(lineno, method, target)`` for monkeypatch mutation calls in *tree*."""
    return _patch_inventory_sites(tree).mutation_sites


def _explicit_patch_context_sites(tree: ast.AST) -> list[tuple[int, str]]:
    """Return explicit ``pytest.MonkeyPatch`` factory/context calls."""
    return _patch_inventory_sites(tree).context_sites


def _monkeypatch_reference_sites(tree: ast.AST) -> list[tuple[int, str]]:
    """Return explicit monkeypatch fixture/type/name references in *tree*."""
    return _patch_inventory_sites(tree).reference_sites


def _patch_inventory_sites(tree: ast.AST) -> _PatchInventorySites:
    """Return all monkeypatch-related sites from one alias pass plus one scan."""
    aliases = _patch_alias_inventory(tree)
    mutation_sites: list[tuple[int, str, str | None]] = []
    context_sites: list[tuple[int, str]] = []
    reference_sites: list[tuple[int, str]] = []
    seen: set[tuple[int, str]] = set()

    def add(lineno: int, name: str) -> None:
        hit = (lineno, name)
        if hit not in seen:
            seen.add(hit)
            reference_sites.append(hit)

    for lineno, import_name in aliases.import_sites:
        add(lineno, import_name)

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr in _MUTATION_VERBS:
                caller = func.value
                if _is_monkeypatch_mutation_caller(caller):
                    target = _target_name_from_args(node)
                    mutation_sites.append((node.lineno, func.attr, target))
            name = _canonical_patch_name(
                qualified_name(func),
                aliases.pytest_aliases,
                aliases.internal_pytest_aliases,
                aliases.internal_monkeypatch_aliases,
                aliases.direct_patch_aliases,
            )
            if name in _PATCH_CONTEXT_FACTORIES:
                context_sites.append((node.lineno, name))
        elif isinstance(node, ast.arg) and node.arg == "monkeypatch":
            add(node.lineno, "argument monkeypatch")
        elif isinstance(node, ast.Name):
            if node.id in {"monkeypatch", "MonkeyPatch"}:
                add(node.lineno, f"name {node.id}")
            else:
                name = _canonical_patch_name(
                    node.id,
                    aliases.pytest_aliases,
                    aliases.internal_pytest_aliases,
                    aliases.internal_monkeypatch_aliases,
                    aliases.direct_patch_aliases,
                )
                if name in _PATCH_REFERENCE_NAMES:
                    add(node.lineno, name)
        elif isinstance(node, ast.Attribute):
            name = _canonical_patch_name(
                qualified_name(node),
                aliases.pytest_aliases,
                aliases.internal_pytest_aliases,
                aliases.internal_monkeypatch_aliases,
                aliases.direct_patch_aliases,
            )
            if name in _PATCH_REFERENCE_NAMES:
                add(node.lineno, name)
    return _PatchInventorySites(
        mutation_sites=mutation_sites,
        context_sites=context_sites,
        reference_sites=reference_sites,
    )


def _patch_import_sites(tree: ast.AST) -> list[tuple[int, str]]:
    """Return direct pytest MonkeyPatch and internal monkeypatch imports."""
    return _patch_alias_inventory(tree).import_sites


def _is_monkeypatch_mutation_caller(caller: ast.expr) -> bool:
    """Return True when a mutation verb is invoked on a monkeypatch object."""
    if isinstance(caller, ast.Name):
        return caller.id == "monkeypatch"
    return isinstance(caller, ast.Attribute) and caller.attr == "monkeypatch"


def _patch_alias_inventory(tree: ast.AST) -> _PatchAliasInventory:
    """Return pytest/_pytest aliases and direct patch import sites."""
    pytest_aliases = {"pytest"}
    internal_pytest_aliases = {"_pytest"}
    internal_monkeypatch_aliases: set[str] = set()
    direct_patch_aliases: dict[str, str] = {}
    import_sites: list[tuple[int, str]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "pytest":
                    pytest_aliases.add(alias.asname or alias.name)
                elif alias.name == "_pytest":
                    imported_name = alias.asname or alias.name
                    internal_pytest_aliases.add(imported_name)
                    import_sites.append((node.lineno, f"import {imported_name}"))
                elif alias.name == _PYTEST_INTERNAL_MONKEYPATCH_MODULE or alias.name.startswith(
                    _PYTEST_INTERNAL_MONKEYPATCH_MODULE + "."
                ):
                    if alias.name == _PYTEST_INTERNAL_MONKEYPATCH_MODULE and alias.asname is not None:
                        internal_monkeypatch_aliases.add(alias.asname)
                    import_sites.append((node.lineno, f"import {alias.name}"))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                if module == "pytest" and alias.name == "MonkeyPatch":
                    if alias.asname is not None:
                        direct_patch_aliases[alias.asname] = "pytest.MonkeyPatch"
                    import_sites.append((node.lineno, "import pytest.MonkeyPatch"))
                elif module == _PYTEST_INTERNAL_MONKEYPATCH_MODULE:
                    if alias.name == "MonkeyPatch" and alias.asname is not None:
                        direct_patch_aliases[alias.asname] = "_pytest.monkeypatch.MonkeyPatch"
                    import_sites.append((node.lineno, f"import {_PYTEST_INTERNAL_MONKEYPATCH_MODULE}.{alias.name}"))
                elif module == "_pytest" and alias.name == "monkeypatch":
                    internal_monkeypatch_aliases.add(alias.asname or alias.name)
                    import_sites.append((node.lineno, f"import {_PYTEST_INTERNAL_MONKEYPATCH_MODULE}"))
    return _PatchAliasInventory(
        pytest_aliases=pytest_aliases,
        internal_pytest_aliases=internal_pytest_aliases,
        internal_monkeypatch_aliases=internal_monkeypatch_aliases,
        direct_patch_aliases=direct_patch_aliases,
        import_sites=import_sites,
    )


def _pytest_module_aliases(tree: ast.AST) -> set[str]:
    """Return local names bound to the pytest module."""
    return _patch_alias_inventory(tree).pytest_aliases


def _internal_pytest_module_aliases(tree: ast.AST) -> set[str]:
    """Return local names bound to the internal _pytest module."""
    return _patch_alias_inventory(tree).internal_pytest_aliases


def _internal_monkeypatch_module_aliases(tree: ast.AST) -> set[str]:
    """Return local names bound directly to _pytest.monkeypatch."""
    return _patch_alias_inventory(tree).internal_monkeypatch_aliases


def _canonical_patch_name(
    name: str,
    pytest_aliases: set[str],
    internal_pytest_aliases: set[str],
    internal_monkeypatch_aliases: set[str],
    direct_patch_aliases: dict[str, str],
) -> str:
    """Return canonical MonkeyPatch names for pytest and _pytest aliases."""
    for alias, canonical_name in direct_patch_aliases.items():
        if name == alias or name.startswith(alias + "."):
            return canonical_name + name.removeprefix(alias)
    for alias in pytest_aliases:
        prefix = alias + ".MonkeyPatch"
        if name == prefix or name.startswith(prefix + "."):
            return "pytest.MonkeyPatch" + name.removeprefix(prefix)
    for alias in internal_pytest_aliases:
        prefix = alias + ".monkeypatch.MonkeyPatch"
        if name == prefix or name.startswith(prefix + "."):
            return "_pytest.monkeypatch.MonkeyPatch" + name.removeprefix(prefix)
    for alias in internal_monkeypatch_aliases:
        prefix = alias + ".MonkeyPatch"
        if name == prefix or name.startswith(prefix + "."):
            return "_pytest.monkeypatch.MonkeyPatch" + name.removeprefix(prefix)
    return name


def _patch_inventory_for_module_trees(module_trees: Iterable[tuple[str, ast.AST]]) -> list[str]:
    """Return formatted monkeypatch policy violations for parsed modules."""
    violations: list[str] = []
    for relative, tree in module_trees:
        sites = _patch_inventory_sites(tree)
        for lineno, method, target in sites.mutation_sites:
            violations.append(f"{relative}:{lineno}: monkeypatch.{method}(target={target!r})")
        for lineno, name in sites.context_sites:
            violations.append(f"{relative}:{lineno}: {name}()")
        for lineno, name in sites.reference_sites:
            violations.append(f"{relative}:{lineno}: {name}")
    return violations


def _patch_inventory_for_source(relative_path: str, source: str) -> list[str]:
    """Return formatted monkeypatch policy violations for one in-memory source module."""
    tree = ast.parse(source, filename=relative_path)
    return _patch_inventory_for_module_trees(((relative_path, tree),))


def _patch_violation_suffix_counts(violations: Iterable[str]) -> Counter[str]:
    """Return policy violation suffix counts independent of source line numbers."""
    return Counter(violation.rsplit(": ", maxsplit=1)[-1] for violation in violations)


@pytest.fixture(scope="module")
def patch_inventory(source_tree_ast: Mapping[Path, ast.AST]) -> list[str]:
    """Return monkeypatch machinery violations from deterministic test controls."""
    module_trees: list[tuple[str, ast.AST]] = []
    for module_path in all_test_control_modules():
        tree = ast_for_path(module_path, source_tree_ast)
        if tree is None:
            continue
        module_trees.append((repo_relative(module_path), tree))
    return _patch_inventory_for_module_trees(module_trees)


def test_no_monkeypatch_fixture_or_context_usage(
    patch_inventory: list[str],
) -> None:
    """No deterministic production test may use pytest monkeypatch machinery."""
    assert not patch_inventory, "Monkeypatch machinery found in deterministic production tests:\n" + "\n".join(
        patch_inventory
    )


@pytest.mark.parametrize(
    ("source", "expected_violations"),
    (
        pytest.param(
            """
def test_attr_mutation(monkeypatch):
    monkeypatch.setattr(service_module, "settings", object())
    monkeypatch.setattr("pkg.module.factory", object())
""",
            Counter(
                {
                    "argument monkeypatch": 1,
                    "name monkeypatch": 2,
                    "monkeypatch.setattr(target='settings')": 1,
                    "monkeypatch.setattr(target='factory')": 1,
                }
            ),
            id="fixture-mutation-targets",
        ),
        pytest.param(
            """
class MutatingHarness:
    def test_env_mutation(self):
        self.monkeypatch.setenv("AEAT_TEST_SETTING", "1")
""",
            Counter({"monkeypatch.setenv(target='AEAT_TEST_SETTING')": 1}),
            id="stored-fixture-mutation",
        ),
        pytest.param(
            """
from pytest import MonkeyPatch
from _pytest.monkeypatch import MonkeyPatch as PytestMonkeyPatch
from _pytest.monkeypatch import notset
from _pytest import monkeypatch as internal_monkeypatch
import _pytest.monkeypatch as monkeypatch_module
import _pytest as private_pytest
import pytest

def test_type_references(context: MonkeyPatch, qualified: pytest.MonkeyPatch):
    pass
""",
            Counter(
                {
                    "import pytest.MonkeyPatch": 1,
                    "import _pytest.monkeypatch.MonkeyPatch": 1,
                    "import _pytest.monkeypatch.notset": 1,
                    "import _pytest.monkeypatch": 2,
                    "import private_pytest": 1,
                    "name MonkeyPatch": 1,
                    "pytest.MonkeyPatch": 1,
                }
            ),
            id="imports-and-type-references",
        ),
        pytest.param(
            """
import pytest

def test_context_factory():
    with pytest.MonkeyPatch.context():
        pass
""",
            Counter({"pytest.MonkeyPatch.context()": 1, "pytest.MonkeyPatch": 1}),
            id="public-context-factory",
        ),
        pytest.param(
            """
import pytest as pt

def test_context_factory():
    with pt.MonkeyPatch.context():
        pass
""",
            Counter({"pytest.MonkeyPatch.context()": 1, "pytest.MonkeyPatch": 1}),
            id="public-alias-context-factory",
        ),
        pytest.param(
            """
from _pytest import monkeypatch as internal_monkeypatch
import _pytest as private_pytest
import _pytest.monkeypatch as monkeypatch_module

def test_context_factory():
    with private_pytest.monkeypatch.MonkeyPatch.context():
        with internal_monkeypatch.MonkeyPatch.context():
            with monkeypatch_module.MonkeyPatch.context():
                pass
""",
            Counter(
                {
                    "import _pytest.monkeypatch": 2,
                    "import private_pytest": 1,
                    "_pytest.monkeypatch.MonkeyPatch.context()": 3,
                    "_pytest.monkeypatch.MonkeyPatch": 3,
                }
            ),
            id="internal-context-factories",
        ),
        pytest.param(
            """
from pytest import MonkeyPatch as PublicPatch
from _pytest.monkeypatch import MonkeyPatch as InternalPatch

def test_context_factory(public: PublicPatch, internal: InternalPatch):
    with PublicPatch.context():
        with InternalPatch.context():
            pass
""",
            Counter(
                {
                    "import pytest.MonkeyPatch": 1,
                    "import _pytest.monkeypatch.MonkeyPatch": 1,
                    "pytest.MonkeyPatch.context()": 1,
                    "_pytest.monkeypatch.MonkeyPatch.context()": 1,
                    "pytest.MonkeyPatch": 2,
                    "_pytest.monkeypatch.MonkeyPatch": 2,
                }
            ),
            id="direct-alias-context-factories",
        ),
    ),
)
def test_monkeypatch_policy_rejects_forbidden_patch_shapes(
    source: str,
    expected_violations: Counter[str],
) -> None:
    """MonkeyPatch machinery must fail through the same policy path as real files."""
    violations = _patch_inventory_for_source("dev/tests/test_monkeypatch_policy.py", source)

    assert _patch_violation_suffix_counts(violations) == expected_violations


def test_discovery_found_modules() -> None:
    """Guardrail: the discovery walk must find at least one test module."""
    modules = all_test_control_modules()
    assert modules, "No test modules discovered — check glob roots."
