"""Boundary tests for registry public imports and private module ownership."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from aeat.core.paths import PROJECT_ROOT
from aeat.domain.calculations import registry

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_PRIVATE_REGISTRY_PREFIX = "aeat.domain.calculations.registry._"
_REGISTRY_SOURCE_ROOT = PROJECT_ROOT / "src" / "aeat"
_REGISTRY_TEST_ROOT = PROJECT_ROOT / "src" / "aeat" / "domain" / "calculations" / "registry"
_LEDGER_BINDING_PUBLIC_NAMES = (
    "CounterpartAggregationObservation",
    "CounterpartAggregationRequirement",
    "IvaLedgerObservation",
    "OssIossLedgerObservation",
    "counterpart_binding_requirements",
    "resolve_counterpart_binding_row_values",
    "resolve_counterpart_binding_values",
    "resolve_ledger_iva_aggregation_binding_values",
    "resolve_ledger_oss_aggregation_binding_values",
    "validate_counterpart_binding_definition",
    "validate_ledger_iva_aggregation_binding_definition",
    "validate_ledger_oss_aggregation_binding_definition",
)
_REMOVED_INVOICE_BINDING_PUBLIC_NAMES = (
    "InvoiceObservation",
    "InvoiceObservationRequirement",
    "invoice_binding_requirements",
    "resolve_invoice_binding_row_values",
    "resolve_invoice_binding_values",
    "validate_invoice_binding_definition",
)
_MODELO_REGISTRY_PRIVATE_MODULES = ("_bindings", "_errors", "_record_design", "_schema")


def test_registry_ledger_binding_substrate_is_public_api() -> None:
    exported = set(registry.__all__)

    assert all(hasattr(registry, name) for name in _LEDGER_BINDING_PUBLIC_NAMES)
    assert set(_LEDGER_BINDING_PUBLIC_NAMES).issubset(exported)


def test_registry_invoice_binding_compatibility_api_is_removed() -> None:
    exported = set(registry.__all__)

    assert not any(hasattr(registry, name) for name in _REMOVED_INVOICE_BINDING_PUBLIC_NAMES)
    assert exported.isdisjoint(_REMOVED_INVOICE_BINDING_PUBLIC_NAMES)


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
