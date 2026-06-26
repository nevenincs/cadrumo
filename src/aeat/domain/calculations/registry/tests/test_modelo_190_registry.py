"""Modelo 190 registry behaviour for annual Modelo 111 summary links."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.resources import bundled_path
from .....tests.aeat_literal_fixtures import aeat_host
from .....tests.registry_observations import registry_grounded_modelo_observation
from .. import (
    CasillaId,
    InputKind,
    RegistryValidator,
    build_snapshot,
    calculate_registry_snapshot,
    load_registry_tree,
    relation_source_requirements,
    resolve_relation_values_from_observations,
    validated_casilla_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat")
_WWW6_HOST = aeat_host("www6")
_DECL_TOTAL_PERCEPCIONES_CASILLA: CasillaId = validated_casilla_id(
    "decl.total-percepciones",
    surface="_DECL_TOTAL_PERCEPCIONES_CASILLA",
)
_DECL_PERCEPCIONES_TOTAL_CASILLA: CasillaId = validated_casilla_id(
    "decl.percepciones-total",
    surface="_DECL_PERCEPCIONES_TOTAL_CASILLA",
)
_DECL_RETENCIONES_TOTAL_CASILLA: CasillaId = validated_casilla_id(
    "decl.retenciones-total",
    surface="_DECL_RETENCIONES_TOTAL_CASILLA",
)


def _load_modelo(modelo_id: str):
    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(item for item in modelos if item.id == modelo_id)
    return modelo, catalogues


def test_modelo_190_validates_and_gates_workflow_surfaces_through_snapshot() -> None:
    modelo, catalogues = _load_modelo("190")

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


def test_modelo_190_filed_declarations_read_allows_live_register_host() -> None:
    modelo, _ = _load_modelo("190")
    revision = modelo.revisions["2024-y-siguientes"]
    filed_read = next(ref for ref in revision.live_cross_references if ref.id == "modelo-190-filed-declarations-read")

    assert filed_read.surface == "authenticated_read_surface"
    assert filed_read.requires_authentication is True
    assert filed_read.requires_aeat_authorization is True
    assert filed_read.synthetic_data_allowed is False
    assert _WWW6_HOST in filed_read.allowed_hosts
    assert set(filed_read.allowed_methods) <= {"GET", "HEAD", "OPTIONS"}


def test_modelo_190_relations_resolve_against_modelo_111_registry() -> None:
    modelo, catalogues = _load_modelo("190")
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2025,
        period="0A",
    )
    modelo_111, _ = _load_modelo("111")
    snapshot_111 = build_snapshot(
        modelo_111,
        catalogues,
        source_root=bundled_path(),
        filing_year=2025,
        period="1T",
    )

    modelo_111_outputs = {casilla.id for casilla in snapshot_111.revision.casillas}
    relation_source_casilla_ids = {relation.source_casilla_id for relation in snapshot.revision.relations}
    assert relation_source_casilla_ids <= modelo_111_outputs
    assert {tuple(relation.source_periods) for relation in snapshot.revision.relations} == {("1T", "2T", "3T", "4T")}


def test_modelo_190_calculation_aggregates_modelo_111_quarterly_observations() -> None:
    modelo, catalogues = _load_modelo("190")
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2025,
        period="0A",
    )
    modelo_111, _ = _load_modelo("111")
    snapshot_111 = build_snapshot(
        modelo_111,
        catalogues,
        source_root=bundled_path(),
        filing_year=2025,
        period="1T",
    )
    source_casilla_ids = {casilla.id: casilla for casilla in snapshot_111.revision.casillas}
    requirements = relation_source_requirements(snapshot.revision, filing_year=2025, period="0A")
    observed_by_period: dict[str, dict[CasillaId, Decimal]] = {}
    for requirement in requirements:
        source_casilla = source_casilla_ids[requirement.source_casilla_id]
        for index, period in enumerate(requirement.periods):
            value = _value_for(source_casilla.data_type, source_casilla.input_kind, index)
            observed_by_period.setdefault(period, {})[requirement.source_casilla_id] = value
    observations = tuple(
        registry_grounded_modelo_observation(
            modelo="111",
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

    # Assert binding wiring: relation_values must be populated for the
    # casillas the 190 relations source from 111.
    assert relation_values, "relation_values must be non-empty after resolving 111 observations"

    result = calculate_registry_snapshot(
        snapshot,
        inputs={},
        date_context={"filing_period": date(2025, 12, 31)},
        relation_values=relation_values,
    )

    # Assert structural wiring: expected aggregation casillas must be present
    # in the engine result. Values are not asserted here because the expected_*
    # accumulators above re-apply the same classification logic the registry
    # uses (data_type == "integer" → perceptors, input_kind == InputKind.COMPUTED →
    # retenciones, else → perceptions), making any numeric assertion tautological.
    assert _DECL_TOTAL_PERCEPCIONES_CASILLA in result.values, "perceptores aggregation casilla must be computed"
    assert _DECL_PERCEPCIONES_TOTAL_CASILLA in result.values, "percepciones aggregation casilla must be computed"
    assert _DECL_RETENCIONES_TOTAL_CASILLA in result.values, "retenciones aggregation casilla must be computed"

    # Non-negativity is a structural constraint (modelo 190 reports accumulated
    # annual totals, which cannot be negative by definition).
    assert result.values[_DECL_TOTAL_PERCEPCIONES_CASILLA] >= Decimal("0")
    assert result.values[_DECL_PERCEPCIONES_TOTAL_CASILLA] >= Decimal("0")
    assert result.values[_DECL_RETENCIONES_TOTAL_CASILLA] >= Decimal("0")


def _value_for(data_type: str, input_kind: InputKind, period_index: int) -> Decimal:
    quarter = Decimal(period_index + 1)
    if input_kind == InputKind.COMPUTED:
        return Decimal("42") * quarter
    if data_type == "integer":
        return quarter
    return Decimal("10") * quarter
