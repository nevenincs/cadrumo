"""Tests for the Modelo 100 registry foundation."""

from __future__ import annotations

import json

import pytest

from .._validate_relation_periods import select_relation_source_revisions
from ._modelo_100_registry_support import _loaded_registry, _registry_validator, _source_root

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_modelo_100_revisions_match_record_design_manifest() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    manifest_path = _source_root() / "corpus" / "aeat_official" / "disenos_registro" / "modelo_100" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    years_with_complete_layout = set[str]()
    for year in range(2020, 2026):
        artefact_names = {
            item["original_filename"]
            for item in manifest["artefacts"]
            if f"_{year}" in item["original_filename"] or f"{year}.xsd" in item["original_filename"]
        }
        assert {
            f"diccionarioXSD_{year}.properties",
            f"diccionarioDlgXSD_{year}.properties",
            f"Renta{year}.xsd",
        }.issubset(artefact_names)
        years_with_complete_layout.add(str(year))

    assert set(modelo.revisions) == years_with_complete_layout

    for year_str in years_with_complete_layout:
        revision = modelo.revisions[year_str]
        expected_sources = {
            f"aeat-dr-100-{year_str}-dictionary",
            f"aeat-dr-100-{year_str}-input-dictionary",
            f"aeat-dr-100-{year_str}-xsd",
        }

        assert expected_sources.issubset(revision.source_refs)
        assert expected_sources.issubset(catalogues.sources)
        assert revision.period_selector.years == (int(year_str),)
        assert revision.period_selector.periods == ("0A",)


def test_modelo_100_dependency_relations_resolve_against_registered_modelos() -> None:
    modelos_by_id, _catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    revision = modelo.revisions["2025"]

    _registry_validator().validate_modelo(modelo)
    assert revision.relations

    for relation in revision.relations:
        source_modelo = modelos_by_id[relation.source_modelo]
        source_revisions, selector_failures = select_relation_source_revisions(
            source_modelo,
            relation.source_revision_selector,
        )
        assert not selector_failures, relation.id
        assert source_revisions, relation.id
        for source_revision in source_revisions:
            outputs = {casilla.id for casilla in source_revision.casillas}
            for binding in source_revision.algorithm_bindings:
                outputs.update(binding.output_casilla_ids.values())

            assert relation.source_casilla_id in outputs, relation.id
            assert set(relation.source_periods).issubset(source_revision.period_selector.periods), relation.id
        assert relation.target_binding in {binding.id for binding in revision.bindings}
        assert set(relation.target_periods).issubset(revision.period_selector.periods)


def test_modelo_100_rental_landlord_foreign_nif_flags_have_specific_role() -> None:
    modelos_by_id, _catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]

    for year in range(2020, 2026):
        revision = modelo.revisions[str(year)]
        casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}
        for casilla_id, referenced_nif_id in (("0716", "0715"), ("0718", "0717")):
            casilla = casillas_by_id[casilla_id]

            assert tuple(casilla.section)[-1] == "deduccion_alquiler_res"
            assert casilla.data_type == "boolean"
            assert casilla.semantic_role == "irpf_deduccion_alquiler_arrendador_nif_extranjero_flag"
            assert f"[{referenced_nif_id}]" in casilla.label

    assert all(
        casilla.semantic_role != "irpf_anexo_a_nif_extranjero_flag"
        for revision in modelo.revisions.values()
        for casilla in revision.casillas
    )


def test_modelo_100_cadastral_construction_ratios_are_decimal_roles() -> None:
    modelos_by_id, _catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]

    for year in range(2020, 2026):
        revision = modelo.revisions[str(year)]
        casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}
        for casilla_id in ("0125", "0140"):
            casilla = casillas_by_id[casilla_id]

            assert tuple(casilla.section) == ("toma_datos_ampliada", "inmuebles", "inmueble")
            assert casilla.data_type == "decimal"
            assert casilla.semantic_role == "irpf_inmueble_ratio_construccion_catastral"
            assert "valor catastral" in casilla.label.lower()
            assert "100" in casilla.label

    assert all(
        casilla.semantic_role != "irpf_inmueble_pct_valor_catastral_construccion"
        for revision in modelo.revisions.values()
        for casilla in revision.casillas
    )


def test_modelo_100_business_lease_marker_is_boolean_flag() -> None:
    modelos_by_id, _catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]

    for year in range(2020, 2026):
        revision = modelo.revisions[str(year)]
        casilla = next(casilla for casilla in revision.casillas if casilla.id == "0082")

        assert tuple(casilla.section) == ("toma_datos_ampliada", "inmuebles", "inmueble")
        assert casilla.data_type == "boolean"
        assert casilla.semantic_role == "irpf_inmueble_arrendamiento_negocio_flag"
        assert casilla.label == "Bien inmueble objeto de arrendamiento de negocio"


def test_modelo_100_regularization_refunds_use_noun_role() -> None:
    modelos_by_id, _catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]

    for year in range(2020, 2026):
        revision = modelo.revisions[str(year)]
        casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}
        expected_casilla_ids = ("0677", "0682") if year <= 2023 else ("0677",)

        for casilla_id in expected_casilla_ids:
            casilla = casillas_by_id[casilla_id]

            assert tuple(casilla.section) == ("resultados", "regularizacion_res")
            assert casilla.semantic_role == "irpf_regularizacion_devolucion_autoliquidaciones_anteriores"
            assert "devoluci" in casilla.label.lower()
            assert str(year) in casilla.label

    assert all(
        casilla.semantic_role != "irpf_regularizacion_autoliquidaciones_anteriores_devolver"
        for revision in modelo.revisions.values()
        for casilla in revision.casillas
    )
