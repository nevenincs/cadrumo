"""Modelo 115 registry behaviour for quarterly rental withholding filings."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.resources import bundled_path
from .. import InputKind, RegistryValidator, build_snapshot, resolve_bound_inputs_by_casilla_id
from .._formula_runtime import calculate_registry_snapshot
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_modelo_115_validated_snapshot_owns_workflow_surfaces() -> None:
    modelo, catalogues = _committed_modelo("115")

    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2026,
        period="1T",
    )

    assert snapshot.revision.orden_aplicabilidad == ("orden-2000-11-20:apartado-primero",)
    construct = snapshot.revision.constructs[0]
    linked_by_surface = {
        link.surface: link for link in snapshot.revision.application_links if link.id in construct.application_links
    }
    assert {
        "calculation",
        "filing",
        "export",
        "verification",
        "review",
        "approval",
        "reconciliation",
        "extractor",
        "portal",
        "deadline",
        "workflow",
    } <= set(linked_by_surface)
    assert all(link.requires_snapshot for link in linked_by_surface.values())


def test_modelo_115_binds_retenciones_aggregation_and_calculates_rent_withholding() -> None:
    """M115 count/base come from retenciones aggregation; retención remains the registry formula."""

    modelo, catalogues = _committed_modelo("115")
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2026,
        period="1T",
    )
    casillas = {casilla.id: casilla for casilla in snapshot.revision.casillas}
    bindings = {binding.id: binding for binding in snapshot.revision.bindings}

    assert casillas["01"].input_kind is InputKind.BOUND
    assert casillas["01"].binding == "modelo-115-perceptores"
    assert bindings["modelo-115-perceptores"].source == "retenciones_aggregation"
    assert casillas["02"].input_kind is InputKind.BOUND
    assert casillas["02"].binding == "modelo-115-base-retenciones"
    assert bindings["modelo-115-base-retenciones"].source == "retenciones_aggregation"

    binding_values = {
        "modelo-115-perceptores": Decimal("1"),
        "modelo-115-base-retenciones": Decimal("2700.00"),
    }
    inputs = {
        **resolve_bound_inputs_by_casilla_id(snapshot.revision, binding_values),
        "04": Decimal("0"),
    }
    result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        date_context={"filing_period": date(2026, 3, 31)},
        binding_values=binding_values,
    )

    assert result.values["01"] == Decimal("1")
    assert result.values["02"] == Decimal("2700.00")
    assert result.values["03"] == Decimal("513.00")
    assert result.values["05"] == Decimal("513.00")
