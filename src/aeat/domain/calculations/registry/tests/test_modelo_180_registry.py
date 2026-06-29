"""Modelo 180 registry behaviour for annual Modelo 115 summary links."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.resources import bundled_path
from .....tests.registry_observations import registry_grounded_modelo_observation
from .. import (
    CasillaId,
    RegistryValidationError,
    RegistryValidator,
    build_snapshot,
    calculate_registry_snapshot,
    load_registry_tree,
    relation_source_requirements,
    resolve_bound_inputs_by_casilla_id,
    resolve_relation_values_from_observations,
    validated_casilla_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat")


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test casilla id")
    except ValueError as exc:
        raise AssertionError(f"Modelo 180 registry fixture casilla key {value!r} is not a CasillaId") from exc


_M115_BASE_CASILLA: CasillaId = _casilla_id("02")
_M180_TOTAL_PERCEPTORES_CASILLA: CasillaId = _casilla_id("decl.total-perceptores")
_M180_BASE_TOTAL_CASILLA: CasillaId = _casilla_id("decl.base-total")
_M180_RETENCIONES_TOTAL_CASILLA: CasillaId = _casilla_id("decl.retenciones-total")
_M180_2023_AMENDMENT_REF = "orden-hfp-1284-2023:art-7"
_M180_HISTORICAL_PROFILE_TARGET_LEGAL_REFS = frozenset(
    [
        "ley-35-2006:art-101",
        "ley-35-2006:art-99",
        "ley-58-2003:art-93",
        "orden-hap-1732-2014:art-2",
        "rd-439-2007:art-100",
        "rd-439-2007:art-108",
    ]
)
_M180_2023_PROFILE_TARGET_LEGAL_REFS = _M180_HISTORICAL_PROFILE_TARGET_LEGAL_REFS | frozenset(
    [_M180_2023_AMENDMENT_REF]
)


def _load_modelo(modelo_id: str):
    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(item for item in modelos if item.id == modelo_id)
    return modelo, catalogues


def _nested_legal_refs(value: object) -> set[str]:
    refs: set[str] = set()

    def visit(item: object) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                if key == "legal_refs":
                    assert isinstance(child, (list, tuple))
                    refs.update(str(ref) for ref in child)
                visit(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                visit(child)

    visit(value)
    return refs


def test_modelo_180_2023_amendment_is_scoped_to_2023_revision() -> None:
    modelo, _ = _load_modelo("180")
    historical_refs = _nested_legal_refs(modelo.revisions["2019-2022"].model_dump(mode="python"))
    current_refs = _nested_legal_refs(modelo.revisions["2023-y-siguientes"].model_dump(mode="python"))

    assert _M180_2023_AMENDMENT_REF not in historical_refs
    assert _M180_2023_AMENDMENT_REF in current_refs


@pytest.mark.parametrize(
    ("revision_id", "expected_refs"),
    [
        ("2019-2022", _M180_HISTORICAL_PROFILE_TARGET_LEGAL_REFS),
        ("2023-y-siguientes", _M180_2023_PROFILE_TARGET_LEGAL_REFS),
    ],
)
def test_modelo_180_extraction_profile_legal_refs_match_target_casillas(
    revision_id: str,
    expected_refs: frozenset[str],
) -> None:
    modelo, _ = _load_modelo("180")
    revision = modelo.revisions[revision_id]
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}

    assert revision.extraction_profiles, revision_id
    for profile in revision.extraction_profiles:
        target_refs = frozenset(
            legal_ref
            for target in profile.target_casillas
            for legal_ref in casillas_by_id[target.casilla_id].legal_refs
        )
        assert target_refs == expected_refs
        assert set(profile.legal_refs) == expected_refs


@pytest.mark.parametrize(("filing_year", "period"), [(2021, "0A"), (2025, "0A")])
def test_modelo_180_validated_snapshot_gates_workflow_surfaces_for_annual_summary(
    filing_year: int,
    period: str,
) -> None:
    modelo, catalogues = _load_modelo("180")

    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=filing_year,
        period=period,
    )

    construct = snapshot.revision.constructs[0]
    linked_by_surface = {
        link.surface: link for link in snapshot.revision.application_links if link.id in construct.application_links
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
    } <= set(linked_by_surface)
    assert all(link.requires_snapshot for link in linked_by_surface.values())


def test_modelo_180_relations_resolve_against_modelo_115_registry() -> None:
    modelo, catalogues = _load_modelo("180")
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2025,
        period="0A",
    )
    modelo_115, _ = _load_modelo("115")
    snapshot_115 = build_snapshot(
        modelo_115,
        catalogues,
        source_root=bundled_path(),
        filing_year=2025,
        period="1T",
    )

    modelo_115_outputs = {casilla.id for casilla in snapshot_115.revision.casillas}
    relation_source_casilla_ids = {relation.source_casilla_id for relation in snapshot.revision.relations}
    assert relation_source_casilla_ids <= modelo_115_outputs
    assert {tuple(relation.source_periods) for relation in snapshot.revision.relations} == {("1T", "2T", "3T", "4T")}


def test_modelo_180_calculation_aggregates_modelo_115_quarterly_observations() -> None:
    modelo, catalogues = _load_modelo("180")
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2025,
        period="0A",
    )
    modelo_115, _ = _load_modelo("115")
    snapshot_115 = build_snapshot(
        modelo_115,
        catalogues,
        source_root=bundled_path(),
        filing_year=2025,
        period="1T",
    )
    source_casilla_ids = {casilla.id: casilla for casilla in snapshot_115.revision.casillas}
    requirements = relation_source_requirements(snapshot.revision, filing_year=2025, period="0A")
    observed_by_period: dict[str, dict[CasillaId, Decimal]] = {}
    for requirement in requirements:
        source_casilla_id = requirement.source_casilla_ids[0]
        source_casilla = source_casilla_ids[source_casilla_id]
        for index, period in enumerate(requirement.periods):
            value = _value_for(source_casilla.data_type, index)
            observed_by_period.setdefault(period, {})[source_casilla_id] = value
    observations = tuple(
        registry_grounded_modelo_observation(
            modelo="115",
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
    binding_values = {"modelo-180-115-perceptores-anual": Decimal("2")}
    result = calculate_registry_snapshot(
        snapshot,
        inputs=resolve_bound_inputs_by_casilla_id(snapshot.revision, binding_values),
        date_context={"filing_period": date(2025, 12, 31)},
        binding_values=binding_values,
        relation_values=relation_values,
    )

    entries_by_target = {entry.target_casilla_id: entry for entry in result.entries}
    assert _M180_TOTAL_PERCEPTORES_CASILLA not in entries_by_target
    assert result.values[_M180_TOTAL_PERCEPTORES_CASILLA] == Decimal("2")
    assert "modelo-180-rel-115-base-anual" in entries_by_target[_M180_BASE_TOTAL_CASILLA].operand_refs
    assert "modelo-180-rel-115-retenciones-anual" in entries_by_target[_M180_RETENCIONES_TOTAL_CASILLA].operand_refs


def test_modelo_180_rejects_incomplete_modelo_115_observation_chain() -> None:
    modelo, catalogues = _load_modelo("180")
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2025,
        period="0A",
    )
    incomplete_observations = (
        registry_grounded_modelo_observation(
            modelo="115",
            filing_year=2025,
            period="1T",
            casilla_values={_M115_BASE_CASILLA: Decimal("1")},
        ),
    )

    with pytest.raises(RegistryValidationError, match="expected one observed filing"):
        resolve_relation_values_from_observations(
            snapshot.revision,
            incomplete_observations,
            filing_year=2025,
            period="0A",
        )


def _value_for(data_type: str, period_index: int) -> Decimal:
    quarter = Decimal(period_index + 1)
    if data_type == "integer":
        return quarter
    return Decimal("10") * quarter
