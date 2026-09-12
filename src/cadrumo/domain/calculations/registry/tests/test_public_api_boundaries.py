"""Registry ownership proofs not covered by the repository import gate.

Repository-wide dependency direction, private cross-package access, package
facades, and aliases are owned by ``just check-import-boundaries``.  The checks
here retain registry-specific defining-module and test-boundary guarantees.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

from .....core.directory_scan import scan_directory
from .....tests.inventory import REPO_ROOT
from ..cross_revision_divergence import CrossRevisionCasillaDivergence
from ..formula_runtime_ops import resolve_keyed_bracket, resolve_parameter
from ..ledger_iva_bindings import (
    IvaLedgerObservation,
    resolve_ledger_iva_aggregation_binding_values,
    validate_ledger_iva_aggregation_binding_definition,
)
from ..ledger_oss_bindings import (
    OssIossLedgerObservation,
    resolve_ledger_oss_aggregation_binding_values,
    validate_ledger_oss_aggregation_binding_definition,
)
from ..runtime_graph import (
    expression_binding_refs,
    expression_casilla_refs,
    expression_date_binding_refs,
    expression_parameter_refs,
)
from ..schema_surfaces import CasillaContinuidadEvolutionDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: The directory the modelo registry TESTS live in. It named the registry
#: package instead, and `scan_directory` is non-recursive by default, so the
#: census below matched 0 files where it should match 40 -- a boundary gate
#: passing without reading one of its subjects.
#: The registry PACKAGE, whose modules the re-export sweep reads.
_REGISTRY_PACKAGE_ROOT = REPO_ROOT / "src" / "cadrumo" / "domain" / "calculations" / "registry"

#: The directory the modelo registry TESTS live in. One constant used to serve
#: both meanings, and the boundary census below took the package -- which
#: `scan_directory` does not descend by default -- so it matched 0 files where
#: it should match 40. The module sweep at the foot of this file wanted the
#: package and was correct; only the census was wrong, so the two are now
#: named apart rather than one being bent to fit the other.
_REGISTRY_TEST_ROOT = _REGISTRY_PACKAGE_ROOT / "tests"

#: Floor for that census. An empty scan and a compliant tree report the same
#: green, which is precisely how this sat unnoticed.
_MINIMUM_MODELO_REGISTRY_TESTS = 30
_LEDGER_BINDING_PUBLIC_NAMES = (
    "IvaLedgerObservation",
    "OssIossLedgerObservation",
    "resolve_ledger_iva_aggregation_binding_values",
    "resolve_ledger_oss_aggregation_binding_values",
    "validate_ledger_iva_aggregation_binding_definition",
    "validate_ledger_oss_aggregation_binding_definition",
)
_CASILLA_CONTINUITY_PUBLIC_NAMES = (
    "CasillaContinuidadEvolutionDefinition",
    "CrossRevisionCasillaDivergence",
)
_MODELO_REGISTRY_PRIVATE_MODULES = ("_bindings", "_errors", "_record_design", "_schema")


def test_registry_ledger_binding_substrate_lives_in_its_defining_module() -> None:
    contracts = (
        IvaLedgerObservation,
        OssIossLedgerObservation,
        resolve_ledger_iva_aggregation_binding_values,
        resolve_ledger_oss_aggregation_binding_values,
        validate_ledger_iva_aggregation_binding_definition,
        validate_ledger_oss_aggregation_binding_definition,
    )

    assert tuple(contract.__name__ for contract in contracts) == _LEDGER_BINDING_PUBLIC_NAMES
    assert {contract.__module__ for contract in contracts} == {
        "cadrumo.domain.calculations.registry.ledger_iva_bindings",
        "cadrumo.domain.calculations.registry.ledger_oss_bindings",
    }


def test_registry_casilla_continuity_reports_live_in_their_defining_modules() -> None:
    contracts = (
        CasillaContinuidadEvolutionDefinition,
        CrossRevisionCasillaDivergence,
    )

    assert tuple(contract.__name__ for contract in contracts) == _CASILLA_CONTINUITY_PUBLIC_NAMES
    assert {contract.__module__ for contract in contracts} == {
        "cadrumo.domain.calculations.registry.schema_surfaces",
        "cadrumo.domain.calculations.registry.cross_revision_divergence",
    }


def test_registry_formula_reference_walkers_live_in_their_defining_module() -> None:
    walkers = (
        expression_binding_refs,
        expression_casilla_refs,
        expression_date_binding_refs,
        expression_parameter_refs,
    )

    assert tuple(walker.__name__ for walker in walkers) == (
        "expression_binding_refs",
        "expression_casilla_refs",
        "expression_date_binding_refs",
        "expression_parameter_refs",
    )
    assert {walker.__module__ for walker in walkers} == {"cadrumo.domain.calculations.registry.runtime_graph"}


def test_registry_parameter_resolution_lives_in_its_defining_module() -> None:
    resolvers = (resolve_keyed_bracket, resolve_parameter)

    assert tuple(resolver.__name__ for resolver in resolvers) == ("resolve_keyed_bracket", "resolve_parameter")
    assert {resolver.__module__ for resolver in resolvers} == {
        "cadrumo.domain.calculations.registry.formula_runtime_ops"
    }


def test_registry_package_marker_is_inert() -> None:
    registry = importlib.import_module("..", package=__package__)

    assert registry.__all__ == []
    assert not any(hasattr(registry, name) for name in _LEDGER_BINDING_PUBLIC_NAMES)


def test_modelo_registry_tests_use_public_registry_api_boundaries() -> None:
    scanned = scan_directory(_REGISTRY_TEST_ROOT, pattern="test_modelo_*_registry.py", require_root=True)
    assert len(scanned) >= _MINIMUM_MODELO_REGISTRY_TESTS, (
        f"the boundary census reached only {len(scanned)} modelo registry test(s) under "
        f"{_REGISTRY_TEST_ROOT}; a scan that matches nothing cannot find an offender"
    )
    offenders = sorted(
        f"{path.name} imports .{module_name}"
        for path in scanned
        for module_name in _relative_private_imports(path)
        if module_name in _MODELO_REGISTRY_PRIVATE_MODULES
    )

    assert offenders == []


def _relative_private_imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return tuple(
        node.module
        for node in ast.walk(tree)
        if (
            isinstance(node, ast.ImportFrom)
            and node.level == 1
            and node.module is not None
            and node.module.startswith("_")
        )
    )


def _locally_bound_names(tree: ast.Module) -> set[str]:
    """Every name a module binds itself, imports excluded.

    ``ast.TypeAlias`` carries PEP 695 ``type X = ...`` statements. Omitting it
    reports a locally defined alias as borrowed, which manufactures findings.
    """
    bound: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            bound.add(node.name)
        elif isinstance(node, ast.Assign):
            bound.update(target.id for target in node.targets if isinstance(target, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            bound.add(node.target.id)
        elif isinstance(node, ast.TypeAlias) and isinstance(node.name, ast.Name):
            bound.add(node.name.id)
    return bound


def _declared_exports(tree: ast.Module) -> list[str] | None:
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and any(getattr(t, "id", "") == "__all__" for t in node.targets)
            and isinstance(node.value, ast.List | ast.Tuple)
        ):
            return [e.value for e in node.value.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
    return None


def test_no_registry_module_exports_a_symbol_it_does_not_define() -> None:
    """A module's public surface is its own contract, never a borrowed one.

    Re-exporting another module's symbol makes two import paths for one name,
    so a consumer can bind to a module that merely forwards it. The owner is
    then free to move while the forwarder still resolves, and the boundary the
    export list appears to describe is not the one imports actually cross.
    """
    modules = sorted(p for p in _REGISTRY_PACKAGE_ROOT.glob("*.py") if p.name != "__init__.py")
    assert len(modules) > 50, f"registry module sweep collapsed to {len(modules)} files"

    borrowed: dict[str, list[str]] = {}
    for path in modules:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        exports = _declared_exports(tree)
        if exports is None:
            continue
        bound = _locally_bound_names(tree)
        if outside := sorted(name for name in exports if name not in bound):
            borrowed[path.name] = outside

    assert borrowed == {}, f"registry modules exporting borrowed symbols: {borrowed}"
