"""Modelo 190 registry behaviour for annual Modelo 111 monetary links and withholding count."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.resources import bundled_path
from .....tests.aeat_literal_fixtures import aeat_host
from .....tests.registry_observations import registry_grounded_modelo_observation
from .. import (
    CasillaId,
    RegistryValidator,
    WithholdingObservation,
    build_snapshot,
    calculate_registry_snapshot,
    load_registry_tree,
    relation_source_requirements,
    resolve_bound_inputs_by_casilla_id,
    resolve_relation_values_from_observations,
    resolve_withholding_binding_values,
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
_M111_IMPORTE_SOURCE_CASILLAS: tuple[CasillaId, ...] = tuple(
    validated_casilla_id(value, surface="_M111_IMPORTE_SOURCE_CASILLAS")
    for value in ("02", "05", "08", "11", "14", "17", "20", "23", "26")
)
_M111_RETENCIONES_TOTAL_CASILLA: CasillaId = validated_casilla_id(
    "28",
    surface="_M111_RETENCIONES_TOTAL_CASILLA",
)
_RETIRED_M111_PERCEPCIONES_SOURCE_CASILLAS: frozenset[CasillaId] = frozenset(
    validated_casilla_id(value, surface="_RETIRED_M111_PERCEPCIONES_SOURCE_CASILLAS")
    for value in ("01", "04", "07", "10", "13", "16", "19", "22", "25")
)
_M190_PERCEPCIONES_BINDING = "modelo-190-percepciones-anual"


def _load_modelo(modelo_id: str):
    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(item for item in modelos if item.id == modelo_id)
    return modelo, catalogues


def _withholding_observation(source_id: str, nif: str, clave: str) -> WithholdingObservation:
    return WithholdingObservation(
        source_id=source_id,
        perceptor_tax_id=nif,
        transaction_date=date(2025, 6, 1),
        clave=clave,
        percibido_dinerario=Decimal("1000"),
        retencion_practicada=Decimal("190"),
    )


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
    assert relation_source_casilla_ids.isdisjoint(_RETIRED_M111_PERCEPCIONES_SOURCE_CASILLAS)
    expected_relation_source_casilla_ids = (*_M111_IMPORTE_SOURCE_CASILLAS, _M111_RETENCIONES_TOTAL_CASILLA)
    assert tuple(sorted(relation_source_casilla_ids)) == expected_relation_source_casilla_ids
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
    requirements = relation_source_requirements(snapshot.revision, filing_year=2025, period="0A")
    source_values: dict[CasillaId, tuple[Decimal, ...]] = {
        _M111_IMPORTE_SOURCE_CASILLAS[0]: (Decimal("1000"), Decimal("2000"), Decimal("1500"), Decimal("2500")),
        _M111_IMPORTE_SOURCE_CASILLAS[1]: (Decimal("100"), Decimal("0"), Decimal("0"), Decimal("50")),
        _M111_IMPORTE_SOURCE_CASILLAS[2]: (Decimal("800"), Decimal("900"), Decimal("850"), Decimal("950")),
        _M111_IMPORTE_SOURCE_CASILLAS[3]: (Decimal("120"), Decimal("0"), Decimal("0"), Decimal("0")),
        _M111_IMPORTE_SOURCE_CASILLAS[4]: (Decimal("200"), Decimal("0"), Decimal("300"), Decimal("0")),
        _M111_IMPORTE_SOURCE_CASILLAS[5]: (Decimal("0"), Decimal("80"), Decimal("0"), Decimal("0")),
        _M111_IMPORTE_SOURCE_CASILLAS[6]: (Decimal("0"), Decimal("0"), Decimal("250"), Decimal("0")),
        _M111_IMPORTE_SOURCE_CASILLAS[7]: (Decimal("0"), Decimal("0"), Decimal("0"), Decimal("75")),
        _M111_IMPORTE_SOURCE_CASILLAS[8]: (Decimal("400"), Decimal("0"), Decimal("0"), Decimal("0")),
        _M111_RETENCIONES_TOTAL_CASILLA: (Decimal("190"), Decimal("210"), Decimal("175.25"), Decimal("225.75")),
    }
    observed_by_period: dict[str, dict[CasillaId, Decimal]] = {}
    for requirement in requirements:
        source_casilla_id = requirement.source_casilla_ids[0]
        if source_casilla_id not in source_values:
            raise AssertionError(f"unexpected Modelo 190 relation source casilla {source_casilla_id}")
        for index, period in enumerate(requirement.periods):
            observed_by_period.setdefault(period, {})[source_casilla_id] = source_values[source_casilla_id][index]
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

    expected_percepciones_total = sum(
        (sum(source_values[casilla_id], Decimal("0")) for casilla_id in _M111_IMPORTE_SOURCE_CASILLAS),
        Decimal("0"),
    )
    expected_retenciones_total = sum(source_values[_M111_RETENCIONES_TOTAL_CASILLA], Decimal("0"))
    withholding_values = resolve_withholding_binding_values(
        snapshot.revision,
        (
            _withholding_observation("m190-1", "11111111H", "A"),
            _withholding_observation("m190-1-repeat", "11111111H", "A"),
            _withholding_observation("m190-2", "11111111H", "G"),
            _withholding_observation("m190-3", "22222222J", "A"),
        ),
    )
    assert withholding_values[_M190_PERCEPCIONES_BINDING] == Decimal("3")

    result = calculate_registry_snapshot(
        snapshot,
        inputs=resolve_bound_inputs_by_casilla_id(snapshot.revision, withholding_values),
        date_context={"filing_period": date(2025, 12, 31)},
        binding_values=withholding_values,
        relation_values=relation_values,
    )

    entries = {entry.target_casilla_id: entry for entry in result.entries}
    assert _DECL_TOTAL_PERCEPCIONES_CASILLA not in entries
    assert _DECL_TOTAL_PERCEPCIONES_CASILLA in result.values, "perceptores aggregation casilla must be computed"
    assert _DECL_PERCEPCIONES_TOTAL_CASILLA in result.values, "percepciones aggregation casilla must be computed"
    assert _DECL_RETENCIONES_TOTAL_CASILLA in result.values, "retenciones aggregation casilla must be computed"
    assert result.values[_DECL_TOTAL_PERCEPCIONES_CASILLA] == Decimal("3")
    assert result.values[_DECL_PERCEPCIONES_TOTAL_CASILLA] == expected_percepciones_total
    assert result.values[_DECL_RETENCIONES_TOTAL_CASILLA] == expected_retenciones_total
