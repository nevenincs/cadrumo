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
