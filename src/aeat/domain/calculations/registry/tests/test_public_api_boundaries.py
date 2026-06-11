"""Boundary tests for registry public imports and private module ownership."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from .....core.paths import PROJECT_ROOT
from ... import registry

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PRIVATE_REGISTRY_PREFIX = "aeat.domain.calculations.registry._"
_REGISTRY_SOURCE_ROOT = PROJECT_ROOT / "src" / "aeat"
_REGISTRY_TEST_ROOT = PROJECT_ROOT / "src" / "aeat" / "domain" / "calculations" / "registry"
_RAW_REGISTRY_ORCHESTRATION_NAMES = frozenset({"build_snapshot", "load_registry_tree"})
_RAW_REGISTRY_ORCHESTRATION_MODULES = frozenset(
    {
        "aeat.domain.calculations.registry._loader",
        "aeat.domain.calculations.registry._snapshot",
        "aeat.domain.calculations.registry",
        "aeat.domain.calculations",
    },
)
_RAW_REGISTRY_ORCHESTRATION_IMPORT_ALLOWLIST = frozenset(
    {
        Path("src/aeat/domain/calculations/registry/_authority.py"),
        Path("src/aeat/domain/calculations/registry/__init__.py"),
        Path("src/aeat/domain/calculations/__init__.py"),
        Path("src/aeat/core/resources/_repos/legal_parameters.py"),
        Path("src/aeat/domain/fincas/_imputacion_parameters.py"),
        Path("src/aeat/domain/iva/_recargo_equivalencia.py"),
    },
)
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
_CASILLA_CONTINUITY_PRIVATE_NAMES = (
    "_iter_cross_revision_casilla_divergences",
    "_validate_cross_revision_casilla_consistency",
    "validate_cross_revision_casilla_consistency",
)
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


def test_source_tree_does_not_use_absolute_registry_private_imports() -> None:
    offenders = sorted(
        f"{path.relative_to(PROJECT_ROOT)} imports {module_name}"
        for path in _REGISTRY_SOURCE_ROOT.rglob("*.py")
        for module_name in _absolute_registry_private_imports(path)
    )

    assert offenders == []


def test_modelo_registry_tests_use_public_registry_api_boundaries() -> None:
    offenders = sorted(
        f"{path.name} imports .{module_name}"
        for path in _REGISTRY_TEST_ROOT.glob("test_modelo_*_registry.py")
        for module_name in _relative_private_imports(path)
        if module_name in _MODELO_REGISTRY_PRIVATE_MODULES
    )

    assert offenders == []


def test_production_code_does_not_import_raw_registry_orchestration() -> None:
    offenders = sorted(
        f"{path.relative_to(PROJECT_ROOT)} imports {name}"
        for path in _REGISTRY_SOURCE_ROOT.rglob("*.py")
        if not _is_test_source(path)
        if path.relative_to(PROJECT_ROOT) not in _RAW_REGISTRY_ORCHESTRATION_IMPORT_ALLOWLIST
        for name in _raw_registry_orchestration_imports(path)
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


def _raw_registry_orchestration_imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[str] = []
    module_name = _module_name_for(path)
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.module is None:
            continue
        imported_names = {alias.name for alias in node.names}
        raw_names = sorted(imported_names.intersection(_RAW_REGISTRY_ORCHESTRATION_NAMES))
        if not raw_names:
            continue
        resolved_module = _resolve_import_module(module_name, node.level, node.module)
        if resolved_module in _RAW_REGISTRY_ORCHESTRATION_MODULES:
            imports.extend(raw_names)
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


def _is_test_source(path: Path) -> bool:
    return path.name.startswith("test_") or path.name == "conftest.py" or "tests" in path.parts


def _module_name_for(path: Path) -> str:
    relative = path.relative_to(PROJECT_ROOT / "src").with_suffix("")
    return ".".join(relative.parts)


def _resolve_import_module(current_module: str, level: int, module: str) -> str:
    if level == 0:
        return module
    package_parts = current_module.split(".")[:-1]
    base_parts = package_parts[: len(package_parts) - level + 1]
    return ".".join((*base_parts, module))
