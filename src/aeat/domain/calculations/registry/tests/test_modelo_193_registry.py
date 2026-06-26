"""Modelo 193 registry behaviour for annual Modelo 123 summary links."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.resources import bundled_path
from .....tests.registry_observations import registry_grounded_modelo_observation
from .. import (
    CasillaId,
    RegistryValidator,
    build_snapshot,
    calculate_registry_snapshot,
    load_registry_tree,
    relation_source_requirements,
    resolve_relation_values_from_observations,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat")


def _load_modelo(modelo_id: str):
    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(item for item in modelos if item.id == modelo_id)
    return modelo, catalogues


def test_modelo_193_validates_and_gates_workflow_surfaces_through_snapshot() -> None:
    modelo, catalogues = _load_modelo("193")

    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2025,
        period="0A",
    )

    construct = snapshot.revision.constructs[0]
    linked_surfaces = {
        link.surface for link in snapshot.revision.application_links if link.id in construct.application_links
    }
    assert {
        "calculation",
        "filing",
        "review",
        "verification",
        "approval",
        "reconciliation",
        "extractor",
        "portal",
        "workflow",
    } <= linked_surfaces


def test_modelo_193_relations_resolve_against_modelo_123_registry() -> None:
    modelo, catalogues = _load_modelo("193")
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2025,
        period="0A",
    )
    modelo_123, _ = _load_modelo("123")
    snapshot_123 = build_snapshot(
        modelo_123,
        catalogues,
        source_root=bundled_path(),
        filing_year=2025,
        period="1T",
    )

    modelo_123_outputs = {casilla.id for casilla in snapshot_123.revision.casillas}
    relation_source_casilla_ids = {relation.source_casilla_id for relation in snapshot.revision.relations}
    assert relation_source_casilla_ids <= modelo_123_outputs
    assert {tuple(relation.source_periods) for relation in snapshot.revision.relations} == {("1T", "2T", "3T", "4T")}


def test_modelo_193_calculation_aggregates_modelo_123_quarterly_observations() -> None:
    modelo, catalogues = _load_modelo("193")
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2025,
        period="0A",
    )
    modelo_123, _ = _load_modelo("123")
    snapshot_123 = build_snapshot(
        modelo_123,
        catalogues,
        source_root=bundled_path(),
        filing_year=2025,
        period="1T",
    )
    source_casilla_ids = {casilla.id: casilla for casilla in snapshot_123.revision.casillas}
    requirements = relation_source_requirements(snapshot.revision, filing_year=2025, period="0A")
    observed_by_period: dict[str, dict[CasillaId, Decimal]] = {}
    for requirement in requirements:
        source_casilla = source_casilla_ids[requirement.source_casilla_id]
        for index, period in enumerate(requirement.periods):
            value = _value_for(source_casilla.data_type, index)
            observed_by_period.setdefault(period, {})[requirement.source_casilla_id] = value
    observations = tuple(
        registry_grounded_modelo_observation(
            modelo="123",
            filing_year=2025,
            period=period,
            casilla_values=casilla_values,
        )
        for period, casilla_values in sorted(observed_by_period.items())
    )
    relation_values = resolve_relation_values_from_observations(
        snapshot.revision,
        observations,
        filing_year=2025,
        period="0A",
    )
    result = calculate_registry_snapshot(
        snapshot,
        inputs={},
        date_context={"filing_period": date(2025, 12, 31)},
        relation_values=relation_values,
    )

    entries_by_target = {entry.target_casilla_id: entry for entry in result.entries}
    assert "modelo-193-rel-123-perceptores-anual" in entries_by_target["decl.total-perceptores"].operand_refs
    assert "modelo-193-rel-123-base-anual" in entries_by_target["decl.base-total"].operand_refs
    assert "modelo-193-rel-123-retenciones-anual" in entries_by_target["decl.retenciones-total"].operand_refs


def _value_for(data_type: str, period_index: int) -> Decimal:
    quarter = Decimal(period_index + 1)
    if data_type == "integer":
        return quarter
    return Decimal("10") * quarter
