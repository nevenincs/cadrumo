"""Boundary tests for registry public imports and private module ownership.

The cross-package raw-registry-orchestration check this module carried
(``test_production_code_does_not_import_raw_registry_orchestration``, guarding
``build_snapshot`` / ``load_registry_tree``) is superseded by the
project-wide ratcheting import-hygiene gate,
``src/cadrumo/tests/test_import_hygiene_gate.py`` (backed by
the import-hygiene scanner and its checked-in baseline). Its
former allowlist
(``_authority.py``, both package ``__init__.py`` files,
``legal_parameters.py``, ``_imputacion_parameters.py``,
``_recargo_equivalencia.py``) is now empty in practice: none
of those sites still import the raw orchestration symbols cross-package, and
the general gate now enforces the boundary for every package, not just the
registry. The checks below (positive facade-content assertions and the
absolute-import / intra-package-test-boundary checks) are NOT import-hygiene
duplicates and remain the registry package's own authority.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from .....core import scan_directory
from .....tests import REPO_ROOT
from ... import registry

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PRIVATE_REGISTRY_PREFIX = "cadrumo.domain.calculations.registry._"
_REGISTRY_SOURCE_ROOT = REPO_ROOT / "src" / "cadrumo"
_REGISTRY_TEST_ROOT = REPO_ROOT / "src" / "cadrumo" / "domain" / "calculations" / "registry"
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
    "ContinuidadId",
    "CrossRevisionCasillaDivergence",
    "CrossRevisionCasillaDriftSummary",
    "summarize_non_overlapping_cross_revision_casilla_drift",
)
_CASILLA_CONTINUITY_PRIVATE_NAMES = (
    "_iter_cross_revision_casilla_divergences",
    "_validate_cross_revision_casilla_consistency",
    "validate_cross_revision_casilla_consistency",
)
_FORMULA_REFERENCE_PUBLIC_NAMES = (
    "expression_binding_refs",
    "expression_casilla_refs",
    "expression_date_binding_refs",
    "expression_parameter_refs",
    "expression_relation_refs",
)
_PARAMETER_RESOLUTION_PUBLIC_NAMES = ("resolve_keyed_bracket", "resolve_parameter")
_MODELO_REGISTRY_PRIVATE_MODULES = ("_bindings", "_errors", "_record_design", "_schema")


def test_registry_ledger_binding_substrate_is_public_api() -> None:
    exported = set(registry.__all__)

    assert all(hasattr(registry, name) for name in _LEDGER_BINDING_PUBLIC_NAMES)
    assert set(_LEDGER_BINDING_PUBLIC_NAMES).issubset(exported)


def test_registry_casilla_continuity_reports_are_public_api() -> None:
    exported = set(registry.__all__)

    assert all(hasattr(registry, name) for name in _CASILLA_CONTINUITY_PUBLIC_NAMES)
    assert set(_CASILLA_CONTINUITY_PUBLIC_NAMES).issubset(exported)
    assert not any(hasattr(registry, name) for name in _CASILLA_CONTINUITY_PRIVATE_NAMES)
    assert exported.isdisjoint(_CASILLA_CONTINUITY_PRIVATE_NAMES)


def test_registry_formula_reference_walkers_are_public_api() -> None:
    exported = set(registry.__all__)

    assert all(hasattr(registry, name) for name in _FORMULA_REFERENCE_PUBLIC_NAMES)
    assert set(_FORMULA_REFERENCE_PUBLIC_NAMES).issubset(exported)


def test_registry_parameter_resolution_is_public_api() -> None:
    exported = set(registry.__all__)

    assert all(hasattr(registry, name) for name in _PARAMETER_RESOLUTION_PUBLIC_NAMES)
    assert set(_PARAMETER_RESOLUTION_PUBLIC_NAMES).issubset(exported)


def test_source_tree_does_not_use_absolute_registry_private_imports() -> None:
    offenders = sorted(
        f"{path.relative_to(REPO_ROOT)} imports {module_name}"
        for path in scan_directory(_REGISTRY_SOURCE_ROOT, pattern="*.py", recursive=True)
        for module_name in _absolute_registry_private_imports(path)
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
