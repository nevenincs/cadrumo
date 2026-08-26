"""Boundary tests for registry public imports and private module ownership.

The cross-package raw-registry-orchestration check this module carried
(``test_production_code_does_not_import_raw_registry_orchestration``, guarding
``build_snapshot`` / ``load_registry_tree``) is superseded by the
project-wide ratcheting import-hygiene gate,
``src/cadrumo/tests/test_import_hygiene_gate.py`` (backed by
the import-hygiene scanner and its checked-in baseline). Its
former allowlist
(``authority.py``, both package ``__init__.py`` files,
``_imputacion_parameters.py``, ``_recargo_equivalencia.py``) is now empty in
practice: none
of those sites still import the raw orchestration symbols cross-package, and
the general gate now enforces the boundary for every package, not just the
registry. The checks below (positive facade-content assertions and the
absolute-import / intra-package-test-boundary checks) are NOT import-hygiene
duplicates and remain the registry package's own authority.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.ledger_bindings import (
    IvaLedgerObservation,
    OssIossLedgerObservation,
    resolve_ledger_iva_aggregation_binding_values,
    resolve_ledger_oss_aggregation_binding_values,
    validate_ledger_iva_aggregation_binding_definition,
    validate_ledger_oss_aggregation_binding_definition,
)
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaContinuidadEvolutionDefinition
from cadrumo.domain.calculations.registry.validate_cross_revision_advisory import (
    CrossRevisionCasillaDriftSummary,
    summarize_non_overlapping_cross_revision_casilla_drift,
)

from .....core.directory_scan import scan_directory
from .....tests import REPO_ROOT
from ..cross_revision_divergence import CrossRevisionCasillaDivergence
from ..formula_runtime_ops import resolve_keyed_bracket, resolve_parameter
from ..runtime_graph import (
    expression_binding_refs,
    expression_casilla_refs,
    expression_date_binding_refs,
    expression_parameter_refs,
    expression_relation_refs,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PRIVATE_REGISTRY_PREFIX = "cadrumo.domain.calculations.registry._"
_REGISTRY_SOURCE_ROOT = REPO_ROOT / "src" / "cadrumo"
_REGISTRY_TEST_ROOT = REPO_ROOT / "src" / "cadrumo" / "domain" / "calculations" / "registry"
_PROJECT_PYTHON_ROOTS = (REPO_ROOT / "src", REPO_ROOT / "dev")
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
    "CrossRevisionCasillaDriftSummary",
    "summarize_non_overlapping_cross_revision_casilla_drift",
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
    assert {contract.__module__ for contract in contracts} == {"cadrumo.domain.calculations.registry.ledger_bindings"}


def test_registry_casilla_continuity_reports_live_in_their_defining_modules() -> None:
    contracts = (
        CasillaContinuidadEvolutionDefinition,
        CrossRevisionCasillaDivergence,
        CrossRevisionCasillaDriftSummary,
        summarize_non_overlapping_cross_revision_casilla_drift,
    )

    assert tuple(contract.__name__ for contract in contracts) == _CASILLA_CONTINUITY_PUBLIC_NAMES
    assert {contract.__module__ for contract in contracts} == {
        "cadrumo.domain.calculations.registry.schema_surfaces",
        "cadrumo.domain.calculations.registry.cross_revision_divergence",
        "cadrumo.domain.calculations.registry.validate_cross_revision_advisory",
    }


def test_registry_formula_reference_walkers_live_in_their_defining_module() -> None:
    walkers = (
        expression_binding_refs,
        expression_casilla_refs,
        expression_date_binding_refs,
        expression_parameter_refs,
        expression_relation_refs,
    )

    assert tuple(walker.__name__ for walker in walkers) == (
        "expression_binding_refs",
        "expression_casilla_refs",
        "expression_date_binding_refs",
        "expression_parameter_refs",
        "expression_relation_refs",
    )
    assert {walker.__module__ for walker in walkers} == {"cadrumo.domain.calculations.registry.runtime_graph"}


def test_registry_parameter_resolution_lives_in_its_defining_module() -> None:
    resolvers = (resolve_keyed_bracket, resolve_parameter)

    assert tuple(resolver.__name__ for resolver in resolvers) == ("resolve_keyed_bracket", "resolve_parameter")
    assert {resolver.__module__ for resolver in resolvers} == {
        "cadrumo.domain.calculations.registry.formula_runtime_ops"
    }


def test_registry_package_marker_is_inert() -> None:
    registry = importlib.import_module("cadrumo.domain.calculations.registry")

    assert registry.__all__ == []
    assert not any(hasattr(registry, name) for name in _LEDGER_BINDING_PUBLIC_NAMES)


def test_source_tree_does_not_use_absolute_registry_private_imports() -> None:
    offenders = sorted(
        f"{path.relative_to(REPO_ROOT)} imports {module_name}"
        for path in scan_directory(_REGISTRY_SOURCE_ROOT, pattern="*.py", recursive=True)
        for module_name in _absolute_registry_private_imports(path)
    )

    assert offenders == []


def test_project_consumers_do_not_import_the_inert_registry_package_facade() -> None:
    """Every project consumer must name a defining registry module directly."""
    offenders = sorted(
        f"{path.relative_to(REPO_ROOT)} imports the registry package facade"
        for root in _PROJECT_PYTHON_ROOTS
        for path in scan_directory(root, pattern="*.py", recursive=True)
        if _imports_registry_package_facade(path)
    )

    assert offenders == []


def test_modelo_registry_tests_use_public_registry_api_boundaries() -> None:
    offenders = sorted(
        f"{path.name} imports .{module_name}"
        for path in scan_directory(_REGISTRY_TEST_ROOT, pattern="test_modelo_*_registry.py")
        for module_name in _relative_private_imports(path)
        if module_name in _MODELO_REGISTRY_PRIVATE_MODULES
    )

    assert offenders == []


def _absolute_registry_private_imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names if alias.name.startswith(_PRIVATE_REGISTRY_PREFIX))
            continue
        if (
            isinstance(node, ast.ImportFrom)
            and node.level == 0
            and node.module is not None
            and node.module.startswith(_PRIVATE_REGISTRY_PREFIX)
        ):
            imports.append(node.module)
    return tuple(imports)


def _imports_registry_package_facade(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return any(
        (
            isinstance(node, ast.Import)
            and any(alias.name == "cadrumo.domain.calculations.registry" for alias in node.names)
        )
        or (
            isinstance(node, ast.ImportFrom)
            and node.level == 0
            and node.module == "cadrumo.domain.calculations.registry"
        )
        for node in ast.walk(tree)
    )


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
