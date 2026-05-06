"""Tests for the Modelo 100 registry foundation."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Any, cast

import pytest
from pydantic import AnyUrl

from aeat.core.paths import PROJECT_ROOT
from aeat.domain.profile import PROFILE_KEYS, TaxResidenceProfile
from aeat.domain.profile.family import RentaAscendantProfile, RentaDescendantProfile, RentaFamilyProfile

from ._constructs import resolve_construct, resolve_revision_constructs
from ._errors import RegistrySnapshotError, RegistryValidationError
from ._export import resolve_export_layout
from ._export_parse import parse_export_payload
from ._formula_runtime import calculate_registry_snapshot
from ._loader import load_registry_tree
from ._remote_state_guard import (
    RemoteOperation,
    assert_remote_operation_allowed,
    remote_state_policy_from_cross_reference,
)
from ._schema import ModeloDefinition, ModeloRevision, RegistryCatalogues
from ._snapshot import build_snapshot
from ._validate import RegistryValidator

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _loaded_registry() -> tuple[dict[str, ModeloDefinition], RegistryCatalogues]:
    modelos, catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")
    return {modelo.id: modelo for modelo in modelos}, catalogues


def test_modelo_100_revisions_match_record_design_manifest() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    manifest_path = PROJECT_ROOT / "corpus" / "aeat_official" / "disenos_registro" / "modelo_100" / "manifest.json"
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

    for year in years_with_complete_layout:
        revision = modelo.revisions[year]
        expected_sources = {
            f"aeat-dr-100-{year}-dictionary",
            f"aeat-dr-100-{year}-input-dictionary",
            f"aeat-dr-100-{year}-xsd",
        }

        assert expected_sources.issubset(revision.source_refs)
        assert expected_sources.issubset(catalogues.sources)
        assert revision.period_selector.years == (int(year),)
        assert revision.period_selector.periods == ("0A",)


def test_modelo_100_dependency_relations_resolve_against_registered_modelos() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    revision = modelo.revisions["2025"]

    RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(modelo)
    assert revision.relations

    for relation in revision.relations:
        source_modelo = modelos_by_id[relation.source_modelo]
        source_revisions = _select_source_revisions(source_modelo, relation.source_revision_selector)
        assert source_revisions, relation.id
        for source_revision in source_revisions:
            outputs = {casilla.id for casilla in source_revision.casillas}
            outputs.update(binding.id for binding in source_revision.bindings)
            for binding in source_revision.algorithm_bindings:
                outputs.update(binding.outputs.values())

            assert relation.source_output in outputs, relation.id
            assert set(relation.source_periods).issubset(source_revision.period_selector.periods), relation.id
        assert relation.target_binding in {binding.id for binding in revision.bindings}
        assert set(relation.target_periods).issubset(revision.period_selector.periods)


def test_modelo_100_constructs_include_dependency_and_source_evidence_members() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    snapshot = build_snapshot(modelo, catalogues, source_root=PROJECT_ROOT, filing_year=2025, period="0A")
    source_foundation = snapshot.constructs["renta-source-foundation"]
    personal_family = snapshot.constructs["renta-personal-family"]
    dependencies = snapshot.constructs["renta-dependent-modelos"]
    payments_retentions = snapshot.constructs["renta-payments-retentions"]
    economic_activities = snapshot.constructs["renta-economic-activities"]
    observation_parsing = snapshot.constructs["renta-observation-parsing"]
    filed_dependency_bindings = {
        binding.id for binding in snapshot.revision.bindings if binding.source == "previous_filing"
    }
    payments_dependency_classifications = {
        classification.id
        for classification in snapshot.dependency_classifications.values()
        if "renta-payments-retentions" in classification.target_constructs
    }

    assert set(snapshot.revision.legal_refs).issubset(source_foundation.legal_refs)
    assert set(snapshot.revision.source_refs).issubset(source_foundation.source_refs)
    assert set(personal_family.bindings) == {
        "renta-2025-profile-tax-id",
        "renta-2025-profile-display-name",
        "renta-2025-profile-tax-residence-ccaa",
        "renta-2025-profile-declaration-type",
        "renta-2025-profile-taxpayer-sex",
        "renta-2025-profile-marital-status",
        "renta-2025-profile-taxpayer-birth-date",
        "renta-2025-profile-spouse-tax-id",
        "renta-2025-profile-spouse-display-name",
        "renta-2025-profile-spouse-birth-date",
        "renta-2025-profile-spouse-sex",
        "renta-2025-profile-taxpayer-disability-grade",
        "renta-2025-profile-taxpayer-death-date",
        "renta-2025-profile-spouse-disability-grade",
        "renta-2025-profile-spouse-non-resident-irpf",
        "renta-2025-profile-spouse-eu-eea-resident",
        "renta-2025-profile-spouse-eu-eea-country",
        "renta-2025-profile-family-descendants-eu-eea-deduction",
        "renta-2025-profile-family-minor-children-in-unit",
        "renta-2025-family-descendant-tax-id",
        "renta-2025-family-descendant-display-name",
        "renta-2025-family-descendant-birth-date",
        "renta-2025-family-descendant-disability-grade",
        "renta-2025-family-descendant-death-date",
        "renta-2025-family-ascendant-tax-id",
        "renta-2025-family-ascendant-display-name",
        "renta-2025-family-ascendant-birth-date",
        "renta-2025-family-ascendant-disability-grade",
        "renta-2025-family-ascendant-cohabiting-descendant-count",
        "renta-2025-family-ascendant-death-date",
    }
    assert set(personal_family.casillas) == {
        "DPNIF_D",
        "DP_APENOM_D",
        "ZCCAD",
        "TIPOTRIBUTACION",
        "SEXO_D",
        "ECIVIL",
        "DPFNAC_D",
        "DPNIF_C",
        "DP_APENOM_C",
        "DPFNAC_C",
        "SEXO_C",
        "DPGMIN_D",
        "DECFAL",
        "DPGMIN_C",
        "NORESIDENTE",
        "RESIDENTEUE",
        "ZRUE2",
        "HIJOSUE",
        "PH18",
        "NIFDLG",
        "APENOMDLG",
        "FNACDLG",
        "MINUSDLG",
        "FALLDLG",
        "DNIASDLG",
        "APENOMDLG_ASC",
        "ANOASDLG",
        "PCTMINASDLG",
        "CONVASDLG",
        "FALLASDLG",
    }
    assert set(dependencies.bindings) == filed_dependency_bindings
    assert set(dependencies.relations) == {relation.id for relation in snapshot.revision.relations}
    assert set(payments_retentions.bindings) == filed_dependency_bindings
    assert set(payments_retentions.relations) == {relation.id for relation in snapshot.revision.relations}
    assert "renta-2025-modelo-100-estimacion-directa-es-normal" in economic_activities.bindings
    assert {"1479", "1553", "1577"}.issubset(economic_activities.casillas)
    assert set(source_foundation.workbook_parity_refs) == set(snapshot.workbook_parity_refs)
    assert set(source_foundation.live_cross_references) == set(snapshot.live_cross_references)
    assert set(source_foundation.application_links) == {
        "modelo-100-renta-web-open-cross-reference",
        "modelo-100-export",
        "modelo-100-filed-declarations-observation",
        "modelo-100-calculation",
        "modelo-100-verification",
        "modelo-100-review",
        "modelo-100-approval",
        "modelo-100-reconciliation",
        "modelo-100-workflow",
    }
    assert observation_parsing.live_cross_references == ("modelo-100-filed-declarations-read",)
    assert set(dependencies.dependency_classifications) == set(snapshot.dependency_classifications)
    assert set(payments_retentions.dependency_classifications) == payments_dependency_classifications


def test_modelo_100_personal_family_profile_bindings_target_profile_schema() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    snapshot = build_snapshot(modelos_by_id["100"], catalogues, source_root=PROJECT_ROOT, filing_year=2025, period="0A")
    profile_keys = {entry.key for entry in PROFILE_KEYS}
    bindings_by_id = {binding.id: binding for binding in snapshot.revision.bindings if binding.source == "profile"}
    casillas_by_id = {casilla.id: casilla for casilla in snapshot.revision.casillas}

    assert bindings_by_id.keys() >= {
        "renta-2025-profile-tax-id",
        "renta-2025-profile-display-name",
        "renta-2025-profile-tax-residence-ccaa",
        "renta-2025-profile-declaration-type",
        "renta-2025-profile-taxpayer-sex",
        "renta-2025-profile-marital-status",
        "renta-2025-profile-taxpayer-birth-date",
        "renta-2025-profile-spouse-tax-id",
        "renta-2025-profile-spouse-display-name",
        "renta-2025-profile-spouse-birth-date",
        "renta-2025-profile-spouse-sex",
        "renta-2025-profile-taxpayer-disability-grade",
        "renta-2025-profile-taxpayer-death-date",
        "renta-2025-profile-spouse-disability-grade",
        "renta-2025-profile-spouse-non-resident-irpf",
        "renta-2025-profile-spouse-eu-eea-resident",
        "renta-2025-profile-spouse-eu-eea-country",
        "renta-2025-profile-family-descendants-eu-eea-deduction",
        "renta-2025-profile-family-minor-children-in-unit",
        "renta-2025-family-descendant-tax-id",
        "renta-2025-family-descendant-display-name",
        "renta-2025-family-descendant-birth-date",
        "renta-2025-family-descendant-disability-grade",
        "renta-2025-family-descendant-death-date",
        "renta-2025-family-ascendant-tax-id",
        "renta-2025-family-ascendant-display-name",
        "renta-2025-family-ascendant-birth-date",
        "renta-2025-family-ascendant-disability-grade",
        "renta-2025-family-ascendant-cohabiting-descendant-count",
        "renta-2025-family-ascendant-death-date",
    }
    assert casillas_by_id["DPNIF_D"].binding == "renta-2025-profile-tax-id"
    assert casillas_by_id["DP_APENOM_D"].binding == "renta-2025-profile-display-name"
    assert casillas_by_id["ZCCAD"].binding == "renta-2025-profile-tax-residence-ccaa"
    assert casillas_by_id["TIPOTRIBUTACION"].binding == "renta-2025-profile-declaration-type"
    assert casillas_by_id["SEXO_D"].binding == "renta-2025-profile-taxpayer-sex"
    assert casillas_by_id["ECIVIL"].binding == "renta-2025-profile-marital-status"
    assert casillas_by_id["DPFNAC_D"].binding == "renta-2025-profile-taxpayer-birth-date"
    assert casillas_by_id["DPNIF_C"].binding == "renta-2025-profile-spouse-tax-id"
    assert casillas_by_id["DP_APENOM_C"].binding == "renta-2025-profile-spouse-display-name"
    assert casillas_by_id["DPFNAC_C"].binding == "renta-2025-profile-spouse-birth-date"
    assert casillas_by_id["SEXO_C"].binding == "renta-2025-profile-spouse-sex"
    assert casillas_by_id["DPGMIN_D"].binding == "renta-2025-profile-taxpayer-disability-grade"
    assert casillas_by_id["DECFAL"].binding == "renta-2025-profile-taxpayer-death-date"
    assert casillas_by_id["DPGMIN_C"].binding == "renta-2025-profile-spouse-disability-grade"
    assert casillas_by_id["NORESIDENTE"].binding == "renta-2025-profile-spouse-non-resident-irpf"
    assert casillas_by_id["RESIDENTEUE"].binding == "renta-2025-profile-spouse-eu-eea-resident"
    assert casillas_by_id["ZRUE2"].binding == "renta-2025-profile-spouse-eu-eea-country"
    assert casillas_by_id["HIJOSUE"].binding == "renta-2025-profile-family-descendants-eu-eea-deduction"
    assert casillas_by_id["PH18"].binding == "renta-2025-profile-family-minor-children-in-unit"
    assert casillas_by_id["NIFDLG"].binding == "renta-2025-family-descendant-tax-id"
    assert casillas_by_id["APENOMDLG"].binding == "renta-2025-family-descendant-display-name"
    assert casillas_by_id["FNACDLG"].binding == "renta-2025-family-descendant-birth-date"
    assert casillas_by_id["MINUSDLG"].binding == "renta-2025-family-descendant-disability-grade"
    assert casillas_by_id["FALLDLG"].binding == "renta-2025-family-descendant-death-date"
    assert casillas_by_id["DNIASDLG"].binding == "renta-2025-family-ascendant-tax-id"
    assert casillas_by_id["APENOMDLG_ASC"].binding == "renta-2025-family-ascendant-display-name"
    assert casillas_by_id["ANOASDLG"].binding == "renta-2025-family-ascendant-birth-date"
    assert casillas_by_id["PCTMINASDLG"].binding == "renta-2025-family-ascendant-disability-grade"
    assert casillas_by_id["CONVASDLG"].binding == "renta-2025-family-ascendant-cohabiting-descendant-count"
    assert casillas_by_id["FALLASDLG"].binding == "renta-2025-family-ascendant-death-date"
    assert all(
        casillas_by_id[casilla_id].input_kind == "bound"
        for casilla_id in (
            "DPNIF_D",
            "DP_APENOM_D",
            "ZCCAD",
            "TIPOTRIBUTACION",
            "SEXO_D",
            "ECIVIL",
            "DPFNAC_D",
            "DPNIF_C",
            "DP_APENOM_C",
            "DPFNAC_C",
            "SEXO_C",
            "DPGMIN_D",
            "DECFAL",
            "DPGMIN_C",
            "NORESIDENTE",
            "RESIDENTEUE",
            "ZRUE2",
            "HIJOSUE",
            "PH18",
            "NIFDLG",
            "APENOMDLG",
            "FNACDLG",
            "MINUSDLG",
            "FALLDLG",
            "DNIASDLG",
            "APENOMDLG_ASC",
            "ANOASDLG",
            "PCTMINASDLG",
            "CONVASDLG",
            "FALLASDLG",
        )
    )

    assert bindings_by_id["renta-2025-profile-tax-id"].selector["profile_key"] in profile_keys
    display_name_profile_keys = cast(
        tuple[str, ...],
        bindings_by_id["renta-2025-profile-display-name"].selector["profile_keys"],
    )
    assert set(display_name_profile_keys).issubset(profile_keys)
    assert bindings_by_id["renta-2025-profile-declaration-type"].selector["profile_key"] in profile_keys
    for binding_id in (
        "renta-2025-profile-taxpayer-sex",
        "renta-2025-profile-marital-status",
        "renta-2025-profile-taxpayer-birth-date",
        "renta-2025-profile-spouse-tax-id",
        "renta-2025-profile-spouse-birth-date",
        "renta-2025-profile-spouse-sex",
        "renta-2025-profile-taxpayer-disability-grade",
        "renta-2025-profile-taxpayer-death-date",
        "renta-2025-profile-spouse-disability-grade",
        "renta-2025-profile-spouse-non-resident-irpf",
        "renta-2025-profile-spouse-eu-eea-resident",
        "renta-2025-profile-spouse-eu-eea-country",
        "renta-2025-profile-family-descendants-eu-eea-deduction",
        "renta-2025-profile-family-minor-children-in-unit",
    ):
        assert bindings_by_id[binding_id].selector["profile_key"] in profile_keys
    spouse_display_name_profile_keys = cast(
        tuple[str, ...],
        bindings_by_id["renta-2025-profile-spouse-display-name"].selector["profile_keys"],
    )
    assert set(spouse_display_name_profile_keys).issubset(profile_keys)
    for binding_id in (
        "renta-2025-profile-spouse-tax-id",
        "renta-2025-profile-spouse-display-name",
        "renta-2025-profile-spouse-birth-date",
        "renta-2025-profile-spouse-sex",
    ):
        selector = bindings_by_id[binding_id].selector
        assert selector["required_when_profile_key"] == "declaration.type"
        assert selector["required_when_value"] == "2"
    assert (
        bindings_by_id["renta-2025-profile-spouse-eu-eea-resident"].selector["required_when_profile_key"]
        == "spouse.non_resident_irpf"
    )
    assert bindings_by_id["renta-2025-profile-spouse-eu-eea-resident"].selector["required_when_value"] == "true"
    assert (
        bindings_by_id["renta-2025-profile-spouse-eu-eea-country"].selector["required_when_profile_key"]
        == "spouse.eu_eea_resident"
    )
    assert bindings_by_id["renta-2025-profile-spouse-eu-eea-country"].selector["required_when_value"] == "true"
    tax_residence_selector = bindings_by_id["renta-2025-profile-tax-residence-ccaa"].selector
    assert tax_residence_selector["profile_model"] == "TaxResidenceProfile"
    assert tax_residence_selector["field"] in TaxResidenceProfile.model_fields

    family_row_bindings = {
        "renta-2025-family-descendant-tax-id": ("descendants", "tax_id"),
        "renta-2025-family-descendant-display-name": ("descendants", "display_name"),
        "renta-2025-family-descendant-birth-date": ("descendants", "birth_date"),
        "renta-2025-family-descendant-disability-grade": ("descendants", "disability_grade"),
        "renta-2025-family-descendant-death-date": ("descendants", "death_date"),
        "renta-2025-family-ascendant-tax-id": ("ascendants", "tax_id"),
        "renta-2025-family-ascendant-display-name": ("ascendants", "display_name"),
        "renta-2025-family-ascendant-birth-date": ("ascendants", "birth_date"),
        "renta-2025-family-ascendant-disability-grade": ("ascendants", "disability_grade"),
        "renta-2025-family-ascendant-cohabiting-descendant-count": (
            "ascendants",
            "cohabiting_descendant_count",
        ),
        "renta-2025-family-ascendant-death-date": ("ascendants", "death_date"),
    }
    for binding_id, (collection, field) in family_row_bindings.items():
        selector = bindings_by_id[binding_id].selector
        assert selector["profile_model"] == "RentaFamilyProfile"
        assert selector["collection"] in RentaFamilyProfile.model_fields
        assert selector["collection"] == collection
        assert selector["field"] == field
        assert selector["repeating"] is True
        assert selector["dictionary_field"] in casillas_by_id
        if collection == "descendants":
            assert field in RentaDescendantProfile.model_fields
        else:
            assert field in RentaAscendantProfile.model_fields


def test_modelo_100_application_links_route_current_workflows_through_snapshots() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    snapshot = build_snapshot(modelos_by_id["100"], catalogues, source_root=PROJECT_ROOT, filing_year=2025, period="0A")
    links_by_surface = {link.surface: link for link in snapshot.revision.application_links}

    assert {
        "calculation",
        "export",
        "filing",
        "verification",
        "review",
        "approval",
        "reconciliation",
        "workflow",
        "portal",
    }.issubset(links_by_surface)
    assert all(link.requires_snapshot is True for link in snapshot.revision.application_links)
    assert links_by_surface["calculation"].consumer == "aeat.domain.calculations.registry.calculate_registry_snapshot"
    assert links_by_surface["export"].consumer == "aeat.application.filing.export"
    assert links_by_surface["filing"].consumer == "aeat.application.filing"
    assert links_by_surface["verification"].consumer == "aeat.application.verification"
    assert links_by_surface["review"].consumer == "aeat.application.filing.review"
    assert links_by_surface["approval"].consumer == "aeat.application.filing.approval"
    assert links_by_surface["reconciliation"].consumer == "aeat.application.filing.reconciliation"
    assert links_by_surface["workflow"].consumer == "aeat.application.workflow"


def test_modelo_100_construct_reader_resolves_revision_member_objects() -> None:
    modelos_by_id, _catalogues = _loaded_registry()
    revision = modelos_by_id["100"].revisions["2025"]
    constructs = {construct.id: construct for construct in resolve_revision_constructs(revision)}
    dependencies = constructs["renta-dependent-modelos"]
    economic_activities = constructs["renta-economic-activities"]
    filed_dependency_binding_ids = {binding.id for binding in revision.bindings if binding.source == "previous_filing"}

    assert {member.id for member in dependencies.members_of_kind("binding")} == filed_dependency_binding_ids
    assert {member.id for member in dependencies.members_of_kind("relation")} == {
        relation.id for relation in revision.relations
    }
    assert "renta-2025-modelo-100-estimacion-directa-es-normal" in {
        member.id for member in economic_activities.members_of_kind("binding")
    }
    for member in dependencies.members:
        assert cast(Any, member.value).id == member.id


def test_modelo_100_renta_section_constructs_classify_registered_relation_sources() -> None:
    modelos_by_id, _catalogues = _loaded_registry()
    revision = modelos_by_id["100"].revisions["2025"]
    relations_by_id = {relation.id: relation for relation in revision.relations}
    constructs = {construct.id: construct for construct in resolve_revision_constructs(revision)}
    source_modelos_by_construct = {
        construct_id: {
            relations_by_id[member.id].source_modelo for member in constructs[construct_id].members_of_kind("relation")
        }
        for construct_id in (
            "renta-work-income",
            "renta-real-estate-capital",
            "renta-movable-capital",
            "renta-economic-activities",
        )
    }

    assert source_modelos_by_construct == {
        "renta-work-income": {"111", "190"},
        "renta-real-estate-capital": {"115", "180"},
        "renta-movable-capital": {"123", "193"},
        "renta-economic-activities": {"130", "131"},
    }


def test_modelo_100_dependency_classifications_cover_registered_relation_sources() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    snapshot = build_snapshot(modelos_by_id["100"], catalogues, source_root=PROJECT_ROOT, filing_year=2025, period="0A")
    relations_by_source: dict[str, set[str]] = {}
    for relation in snapshot.revision.relations:
        relations_by_source.setdefault(relation.source_modelo, set()).add(relation.id)
    classifications_by_source = {
        classification.source_modelo: classification
        for classification in snapshot.revision.dependency_classifications
        if classification.relation_refs
    }

    assert set(classifications_by_source) == set(relations_by_source)
    for source_modelo, relation_ids in relations_by_source.items():
        classification = classifications_by_source[source_modelo]
        assert set(classification.relation_refs) == relation_ids
        assert "renta-dependent-modelos" in classification.target_constructs
        assert all(construct_id in snapshot.constructs for construct_id in classification.target_constructs)


def test_modelo_100_payments_on_account_calculate_from_registry_relations() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    snapshot = build_snapshot(modelos_by_id["100"], catalogues, source_root=PROJECT_ROOT, filing_year=2025, period="0A")
    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            "0592": Decimal("1.00"),
            "0593": Decimal("2.00"),
            "0594": Decimal("3.00"),
            "0596": Decimal("4.00"),
            "0597": Decimal("5.00"),
            "0153": Decimal("6.00"),
            "0599": Decimal("7.00"),
            "0600": Decimal("8.00"),
            "0601": Decimal("9.00"),
            "0602": Decimal("10.00"),
            "0603": Decimal("11.00"),
            "0605": Decimal("12.00"),
            "0606": Decimal("13.00"),
        },
        date_context={},
        binding_values={"renta-2025-modelo-100-estimacion-directa-es-normal": Decimal("1")},
        relation_values={
            "renta-2025-rel-130-pagos-fraccionados": Decimal("140.00"),
            "renta-2025-rel-131-pagos-fraccionados": Decimal("220.00"),
        },
    )
    entries = {entry.target: entry for entry in result.entries}

    assert result.values["0604"] == Decimal("360.00")
    assert result.values["0598"] == Decimal("6.00")
    assert result.values["0609"] == Decimal("451.00")
    assert entries["0598"].operand_refs == ("0153",)
    assert entries["0604"].operand_refs == (
        "renta-2025-rel-130-pagos-fraccionados",
        "renta-2025-rel-131-pagos-fraccionados",
    )
    assert entries["0609"].operand_refs == (
        "0592",
        "0593",
        "0594",
        "0596",
        "0597",
        "0598",
        "0599",
        "0600",
        "0601",
        "0602",
        "0603",
        "0604",
        "0605",
        "0606",
    )


def test_modelo_100_final_settlement_calculates_result_from_registry() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    snapshot = build_snapshot(modelos_by_id["100"], catalogues, source_root=PROJECT_ROOT, filing_year=2025, period="0A")
    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            "0585": Decimal("8000.00"),
            "0586": Decimal("7000.00"),
            "0588": Decimal("100.00"),
            "0414": Decimal("200.00"),
            "0589": Decimal("300.00"),
            "0590": Decimal("400.00"),
            "0591": Decimal("500.00"),
            "0592": Decimal("10.00"),
            "0593": Decimal("20.00"),
            "0594": Decimal("30.00"),
            "0596": Decimal("40.00"),
            "0597": Decimal("50.00"),
            "0153": Decimal("60.00"),
            "0599": Decimal("70.00"),
            "0600": Decimal("80.00"),
            "0601": Decimal("90.00"),
            "0602": Decimal("100.00"),
            "0603": Decimal("110.00"),
            "0605": Decimal("120.00"),
            "0606": Decimal("130.00"),
            "0611": Decimal("100.00"),
            "0612": Decimal("10.00"),
            "0613": Decimal("20.00"),
            "0623": Decimal("30.00"),
            "0624": Decimal("40.00"),
            "0636": Decimal("50.00"),
            "0637": Decimal("60.00"),
            "0248": Decimal("70.00"),
            "0249": Decimal("80.00"),
            "0660": Decimal("90.00"),
            "0661": Decimal("100.00"),
            "0662": Decimal("110.00"),
            "0663": Decimal("120.00"),
            "0664": Decimal("130.00"),
            "0666": Decimal("140.00"),
            "0669": Decimal("150.00"),
        },
        date_context={},
        binding_values={"renta-2025-modelo-100-estimacion-directa-es-normal": Decimal("1")},
        relation_values={
            "renta-2025-rel-130-pagos-fraccionados": Decimal("600.00"),
            "renta-2025-rel-131-pagos-fraccionados": Decimal("400.00"),
        },
    )
    entries = {entry.target: entry for entry in result.entries}

    assert result.values["0587"] == Decimal("15000.00")
    assert result.values["0595"] == Decimal("13500.00")
    assert result.values["0598"] == Decimal("60.00")
    assert result.values["0604"] == Decimal("1000.00")
    assert result.values["0609"] == Decimal("1910.00")
    assert result.values["0610"] == Decimal("11590.00")
    assert result.values["0670"] == Decimal("11950.00")
    assert entries["0610"].operand_refs == ("0595", "0609")
    assert entries["0670"].operand_refs == (
        "0610",
        "0611",
        "0612",
        "0613",
        "0623",
        "0624",
        "0636",
        "0637",
        "0248",
        "0249",
        "0660",
        "0661",
        "0662",
        "0663",
        "0664",
        "0666",
        "0669",
    )


def test_modelo_100_real_estate_capital_calculates_from_registry() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    snapshot = build_snapshot(modelos_by_id["100"], catalogues, source_root=PROJECT_ROOT, filing_year=2025, period="0A")
    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            "0089": Decimal("123.45"),
            "0102": Decimal("10000.00"),
            "0104": Decimal("100.00"),
            "0107": Decimal("200.00"),
            "0109": Decimal("300.00"),
            "0110": Decimal("40.00"),
            "0111": Decimal("50.00"),
            "0112": Decimal("60.00"),
            "0113": Decimal("70.00"),
            "0114": Decimal("80.00"),
            "0115": Decimal("90.00"),
            "0116": Decimal("110.00"),
            "0117": Decimal("120.00"),
            "0131": Decimal("400.00"),
            "0132": Decimal("30.00"),
            "0146": Decimal("20.00"),
            "0147": Decimal("10.00"),
            "0148": Decimal("500.00"),
            "0150": Decimal("1000.00"),
            "0151": Decimal("250.00"),
            "0152": Decimal("7000.00"),
            "0153": Decimal("800.00"),
        },
        date_context={},
        binding_values={"renta-2025-modelo-100-estimacion-directa-es-normal": Decimal("1")},
        relation_values={
            "renta-2025-rel-130-pagos-fraccionados": Decimal("0.00"),
            "renta-2025-rel-131-pagos-fraccionados": Decimal("0.00"),
        },
    )
    entries = {entry.target: entry for entry in result.entries}

    assert result.values["0149"] == Decimal("7820.00")
    assert result.values["0154"] == Decimal("7000.00")
    assert result.values["0155"] == Decimal("123.45")
    assert result.values["0156"] == Decimal("7000.00")
    assert result.values["0598"] == Decimal("800.00")
    assert entries["0149"].operand_refs == (
        "0102",
        "0104",
        "0107",
        "0109",
        "0110",
        "0111",
        "0112",
        "0113",
        "0114",
        "0115",
        "0116",
        "0117",
        "0131",
        "0132",
        "0146",
        "0147",
        "0148",
    )
    assert entries["0154"].operand_refs == ("0149", "0150", "0151", "0152")
    assert entries["0598"].source_refs == (
        "aeat-dr-100-2025-dictionary",
        "aeat-renta-2025-manual-parte1",
        "boe-modelo-100-2025-form",
    )


def test_modelo_100_work_income_calculates_from_registry() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    snapshot = build_snapshot(modelos_by_id["100"], catalogues, source_root=PROJECT_ROOT, filing_year=2025, period="0A")
    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            "0003": Decimal("30000.00"),
            "0004": Decimal("1200.00"),
            "0005": Decimal("228.00"),
            "0006": Decimal("100.00"),
            "0008": Decimal("500.00"),
            "0024": Decimal("200.00"),
            "0009": Decimal("150.00"),
            "0010": Decimal("50.00"),
            "0011": Decimal("300.00"),
            "0058": Decimal("75.00"),
            "0013": Decimal("1800.00"),
            "0014": Decimal("120.00"),
            "0015": Decimal("80.00"),
            "0016": Decimal("40.00"),
            "0019": Decimal("2000.00"),
            "0020": Decimal("1000.00"),
            "0021": Decimal("500.00"),
            "0057": Decimal("250.00"),
            "0023": Decimal("1500.00"),
        },
        date_context={},
        binding_values={"renta-2025-modelo-100-estimacion-directa-es-normal": Decimal("1")},
        relation_values={
            "renta-2025-rel-130-pagos-fraccionados": Decimal("0.00"),
            "renta-2025-rel-131-pagos-fraccionados": Decimal("0.00"),
        },
    )
    entries = {entry.target: entry for entry in result.entries}

    assert result.values["0007"] == Decimal("1328.00")
    assert result.values["0012"] == Decimal("31853.00")
    assert result.values["0017"] == Decimal("29813.00")
    assert result.values["0018"] == Decimal("29813.00")
    assert result.values["0022"] == Decimal("26313.00")
    assert result.values["0025"] == Decimal("24563.00")
    assert entries["0012"].operand_refs == (
        "0003",
        "0007",
        "0008",
        "0024",
        "0009",
        "0010",
        "0011",
        "0058",
    )
    assert entries["0025"].legal_refs == (
        "ley-35-2006:art-18",
        "ley-35-2006:art-19",
        "ley-35-2006:art-20",
        "orden-hac-277-2026:art-3",
    )


def test_modelo_100_movable_capital_income_calculates_from_registry() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    snapshot = build_snapshot(modelos_by_id["100"], catalogues, source_root=PROJECT_ROOT, filing_year=2025, period="0A")
    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            "0027": Decimal("10.00"),
            "0028": Decimal("20.00"),
            "0029": Decimal("30.00"),
            "0030": Decimal("40.00"),
            "0031": Decimal("50.00"),
            "0032": Decimal("60.00"),
            "0033": Decimal("70.00"),
            "0034": Decimal("80.00"),
            "0035": Decimal("90.00"),
            "0037": Decimal("25.00"),
            "0039": Decimal("5.00"),
            "0046": Decimal("100.00"),
            "0047": Decimal("200.00"),
            "0048": Decimal("300.00"),
            "0050": Decimal("400.00"),
            "0051": Decimal("500.00"),
            "0053": Decimal("45.00"),
            "0055": Decimal("15.00"),
        },
        date_context={},
        binding_values={"renta-2025-modelo-100-estimacion-directa-es-normal": Decimal("1")},
        relation_values={
            "renta-2025-rel-130-pagos-fraccionados": Decimal("0.00"),
            "renta-2025-rel-131-pagos-fraccionados": Decimal("0.00"),
        },
    )
    entries = {entry.target: entry for entry in result.entries}

    assert result.values["0036"] == Decimal("450.00")
    assert result.values["0038"] == Decimal("425.00")
    assert result.values["0040"] == Decimal("420.00")
    assert result.values["0041"] == Decimal("420.00")
    assert result.values["0052"] == Decimal("1500.00")
    assert result.values["0054"] == Decimal("1455.00")
    assert result.values["0056"] == Decimal("1440.00")
    assert result.values["0060"] == Decimal("1440.00")
    assert entries["0036"].operand_refs == (
        "0027",
        "0028",
        "0029",
        "0030",
        "0031",
        "0032",
        "0033",
        "0034",
        "0035",
    )
    assert entries["0056"].legal_refs == (
        "ley-35-2006:art-25",
        "ley-35-2006:art-26",
        "orden-hac-277-2026:art-3",
    )


def test_modelo_100_direct_estimation_subtotals_calculate_from_registry() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    snapshot = build_snapshot(modelos_by_id["100"], catalogues, source_root=PROJECT_ROOT, filing_year=2025, period="0A")
    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            "0171": Decimal("100.00"),
            "0172": Decimal("20.00"),
            "0173": Decimal("3.00"),
            "0174": Decimal("4.00"),
            "0175": Decimal("5.00"),
            "0176": Decimal("6.00"),
            "0177": Decimal("7.00"),
            "0178": Decimal("8.00"),
            "0179": Decimal("9.00"),
            "0181": Decimal("10.00"),
            "0182": Decimal("1.00"),
            "0183": Decimal("2.00"),
            "0184": Decimal("3.00"),
            "0185": Decimal("4.00"),
            "0186": Decimal("5.00"),
            "0187": Decimal("6.00"),
            "0188": Decimal("7.00"),
            "0189": Decimal("8.00"),
            "0190": Decimal("9.00"),
            "0191": Decimal("10.00"),
            "0192": Decimal("11.00"),
            "0193": Decimal("12.00"),
            "0194": Decimal("13.00"),
            "0195": Decimal("14.00"),
            "0196": Decimal("15.00"),
            "0197": Decimal("4.00"),
            "0198": Decimal("16.00"),
            "0199": Decimal("17.00"),
            "0200": Decimal("18.00"),
            "0202": Decimal("19.00"),
            "0203": Decimal("20.00"),
            "0205": Decimal("21.00"),
            "0206": Decimal("22.00"),
            "0208": Decimal("23.00"),
            "0214": Decimal("25.00"),
            "0215": Decimal("26.00"),
            "0216": Decimal("27.00"),
            "0217": Decimal("28.00"),
            "0219": Decimal("30.00"),
            "0227": Decimal("24.00"),
        },
        date_context={},
        binding_values={"renta-2025-modelo-100-estimacion-directa-es-normal": Decimal("1")},
        relation_values={
            "renta-2025-rel-130-pagos-fraccionados": Decimal("0.00"),
            "renta-2025-rel-131-pagos-fraccionados": Decimal("0.00"),
        },
    )
    entries = {entry.target: entry for entry in result.entries}

    assert result.values["0180"] == Decimal("162.00")
    assert result.values["0218"] == Decimal("412.00")
    assert result.values["0220"] == Decimal("442.00")
    assert result.values["0221"] == Decimal("-250.00")
    assert result.values["0222"] == Decimal("0.00")
    assert result.values["0223"] == Decimal("412.00")
    assert entries["0222"].operand_refs == (
        "0180",
        "0218",
        "renta-2025-estimacion-directa-simplificada-gastos-dificil-justificacion-rate",
        "renta-2025-estimacion-directa-simplificada-gastos-dificil-justificacion-cap",
    )
    assert entries["0218"].operand_refs == (
        "0181",
        "0182",
        "0183",
        "0184",
        "0185",
        "0186",
        "0187",
        "0188",
        "0189",
        "0190",
        "0191",
        "0192",
        "0193",
        "0194",
        "0195",
        "0196",
        "0197",
        "0198",
        "0199",
        "0200",
        "0202",
        "0203",
        "0205",
        "0206",
        "0208",
        "0227",
        "0214",
        "0215",
        "0216",
        "0217",
    )


def test_modelo_100_direct_estimation_net_returns_and_reductions_branch_on_mode_binding() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    snapshot = build_snapshot(modelos_by_id["100"], catalogues, source_root=PROJECT_ROOT, filing_year=2025, period="0A")
    inputs = {
        "0171": Decimal("80.00"),
        "0172": Decimal("20.00"),
        "0181": Decimal("20.00"),
        "0225": Decimal("5.00"),
        "0232": Decimal("1.00"),
        "0233": Decimal("2.00"),
        "0234": Decimal("3.00"),
        "0236": Decimal("2.00"),
        "0237": Decimal("4.00"),
    }

    normal = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        date_context={},
        binding_values={"renta-2025-modelo-100-estimacion-directa-es-normal": Decimal("1")},
        relation_values={
            "renta-2025-rel-130-pagos-fraccionados": Decimal("0.00"),
            "renta-2025-rel-131-pagos-fraccionados": Decimal("0.00"),
        },
    )
    simplified = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        date_context={},
        binding_values={"renta-2025-modelo-100-estimacion-directa-es-normal": Decimal("0")},
        relation_values={
            "renta-2025-rel-130-pagos-fraccionados": Decimal("0.00"),
            "renta-2025-rel-131-pagos-fraccionados": Decimal("0.00"),
        },
    )

    assert normal.values["0224"] == Decimal("80.00")
    assert normal.values["0226"] == Decimal("73.00")
    assert normal.values["0231"] == Decimal("73.00")
    assert normal.values["0235"] == Decimal("63.00")
    assert simplified.values["0222"] == Decimal("4.00")
    assert simplified.values["0224"] == Decimal("76.00")
    assert simplified.values["0226"] == Decimal("69.00")
    assert simplified.values["0231"] == Decimal("69.00")
    assert simplified.values["0235"] == Decimal("59.00")


def test_modelo_100_simplified_direct_estimation_difficult_justification_cap_is_registry_backed() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    snapshot = build_snapshot(modelos_by_id["100"], catalogues, source_root=PROJECT_ROOT, filing_year=2025, period="0A")
    result = calculate_registry_snapshot(
        snapshot,
        inputs={"0171": Decimal("100000.00")},
        date_context={"filing_period": date(2025, 12, 31)},
        binding_values={"renta-2025-modelo-100-estimacion-directa-es-normal": Decimal("0")},
        relation_values={
            "renta-2025-rel-130-pagos-fraccionados": Decimal("0.00"),
            "renta-2025-rel-131-pagos-fraccionados": Decimal("0.00"),
        },
    )
    entries = {entry.target: entry for entry in result.entries}

    assert result.values["0222"] == Decimal("2000.00")
    assert result.values["0223"] == Decimal("2000.00")
    assert result.values["0224"] == Decimal("98000.00")
    assert entries["0222"].legal_refs == (
        "ley-35-2006:art-30",
        "rd-439-2007:art-30",
        "orden-hac-277-2026:art-3",
    )


def test_modelo_100_authenticated_filed_data_cross_reference_is_guarded_read_only() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    source = catalogues.sources["aeat-modelo-100-procedure"]
    source_text = (PROJECT_ROOT / source.corpus_path).read_text(encoding="utf-8")

    assert "Consulta de declaraciones presentadas" in source_text
    assert "Datos fiscales" in source_text

    for year in range(2020, 2026):
        snapshot = build_snapshot(
            modelos_by_id["100"],
            catalogues,
            source_root=PROJECT_ROOT,
            filing_year=year,
            period="0A",
        )
        cross_reference = snapshot.live_cross_references["modelo-100-filed-declarations-read"]
        policy = remote_state_policy_from_cross_reference(cross_reference)

        assert cross_reference.surface == "authenticated_read_surface"
        assert cross_reference.synthetic_data_allowed is False
        assert cross_reference.requires_authentication is True
        assert cross_reference.requires_aeat_authorization is True
        assert "aeat-modelo-100-procedure" in cross_reference.source_refs
        assert_remote_operation_allowed(
            policy,
            RemoteOperation(
                kind="http",
                method="GET",
                url=AnyUrl("https://www6.agenciatributaria.gob.es/wlpl/SCEJ-MANT/CONSUL/index.zul"),
            ),
        )
        with pytest.raises(RegistryValidationError, match="remote write method"):
            assert_remote_operation_allowed(
                policy,
                RemoteOperation(
                    kind="http",
                    method="POST",
                    url=AnyUrl("https://www6.agenciatributaria.gob.es/wlpl/SCEJ-MANT/CONSUL/index.zul"),
                ),
            )


def test_modelo_100_live_cross_references_block_declared_forbidden_actions() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    snapshot = build_snapshot(modelos_by_id["100"], catalogues, source_root=PROJECT_ROOT, filing_year=2025, period="0A")
    expected_by_id = {
        "modelo-100-renta-web-open": {
            "authenticated-renta-web",
            "fiscal-data-read",
            "borrador-read",
            "filed-declaration-read",
            "server-side-save",
            "signing",
            "presentation",
            "payment",
            "amendment",
            "cancellation",
            "document-submission",
        },
        "modelo-100-filed-declarations-read": {
            "server-side-save",
            "signing",
            "presentation",
            "payment",
            "amendment",
            "cancellation",
            "document-submission",
            "borrador-confirmation",
            "declaration-submission",
        },
    }

    for cross_reference_id, expected_actions in expected_by_id.items():
        cross_reference = snapshot.live_cross_references[cross_reference_id]
        policy = remote_state_policy_from_cross_reference(cross_reference)

        assert expected_actions.issubset(cross_reference.forbidden_actions)
        for action in expected_actions:
            with pytest.raises(RegistryValidationError, match="forbidden action"):
                assert_remote_operation_allowed(
                    policy,
                    RemoteOperation(kind="browser_action", action=f"operator attempts {action}"),
                )


def test_modelo_100_xml_dictionary_layout_reads_official_casilla_paths() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    snapshot = build_snapshot(modelos_by_id["100"], catalogues, source_root=PROJECT_ROOT, filing_year=2023, period="0A")
    resolved = resolve_export_layout(snapshot)
    payload = b"""<?xml version="1.0" encoding="UTF-8"?>
<Renta>
  <DatosIdentificativos>
    <Declarante>
      <DPNIF_D>12345678Z</DPNIF_D>
    </Declarante>
  </DatosIdentificativos>
    <DatosEconomicos>
      <TomaDatosAmpliada>
        <RegEstimaDirecta>
          <ActividadEstDirecta>
            <E1INGRESO>1234.56</E1INGRESO>
          </ActividadEstDirecta>
        </RegEstimaDirecta>
        <RegEstimaObj>
          <ActividadEstObj>
            <E4AL>2000.00</E4AL>
          </ActividadEstObj>
        </RegEstimaObj>
        <RegEstimaObjAgricola>
          <ActividadAgr>
            <E5AK>1500.00</E5AK>
          </ActividadAgr>
        </RegEstimaObjAgricola>
        <Inmuebles>
          <Inmueble>
            <DisposicionTitulares>
              <C_RII>10.00</C_RII>
            </DisposicionTitulares>
        </Inmueble>
      </Inmuebles>
    </TomaDatosAmpliada>
    <Resultados>
      <InmueblesRes>
        <IRIM>10.00</IRIM>
      </InmueblesRes>
    </Resultados>
  </DatosEconomicos>
</Renta>
"""

    parsed = parse_export_payload(
        resolved.layout,
        payload,
        source_root=PROJECT_ROOT,
        sources=snapshot.sources,
    )

    assert {item.casilla_id: item.value for item in parsed.casillas} == {
        "0089": Decimal("10.00"),
        "0155": Decimal("10.00"),
        "0180": Decimal("1234.56"),
        "1479": Decimal("2000.00"),
        "1553": Decimal("1500.00"),
    }
    assert all(item.casilla_id != "01" for item in parsed.casillas)


def test_modelo_100_objective_estimation_record_design_paths_roundtrip_from_export_layout() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    snapshot = build_snapshot(modelos_by_id["100"], catalogues, source_root=PROJECT_ROOT, filing_year=2025, period="0A")
    resolved = resolve_export_layout(snapshot)
    payload = b"""<?xml version="1.0" encoding="UTF-8"?>
<Renta>
  <DatosEconomicos>
    <TomaDatosAmpliada>
      <RegEstimaObj>
        <ActividadEstObj>
          <E4AL>214.00</E4AL>
        </ActividadEstObj>
      </RegEstimaObj>
      <RegEstimaObjAgricola>
        <ActividadAgr>
          <E5AK>315.00</E5AK>
        </ActividadAgr>
      </RegEstimaObjAgricola>
      <RegimenesEspeciales>
        <REAtRentas>
          <ENTIDADAR>
            <F1EH>128.00</F1EH>
          </ENTIDADAR>
        </REAtRentas>
      </RegimenesEspeciales>
    </TomaDatosAmpliada>
  </DatosEconomicos>
</Renta>
"""

    parsed = parse_export_payload(
        resolved.layout,
        payload,
        source_root=PROJECT_ROOT,
        sources=snapshot.sources,
    )

    assert {item.casilla_id: item.value for item in parsed.casillas} == {
        "1479": Decimal("214.00"),
        "1553": Decimal("315.00"),
        "1577": Decimal("128.00"),
    }


def test_construct_reader_rejects_unknown_construct_id() -> None:
    modelos_by_id, _catalogues = _loaded_registry()
    revision = modelos_by_id["100"].revisions["2025"]

    with pytest.raises(RegistrySnapshotError, match="has no construct"):
        resolve_construct(revision, "missing-construct")


def test_validator_rejects_construct_member_outside_revision() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    revision = modelo.revisions["2025"]
    construct = next(item for item in revision.constructs if item.id == "renta-dependent-modelos")
    mutated_construct = construct.model_copy(update={"relations": (*construct.relations, "missing-relation")})
    mutated_revision = revision.model_copy(
        update={
            "constructs": tuple(mutated_construct if item.id == construct.id else item for item in revision.constructs)
        }
    )
    mutated_modelo = modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: mutated_revision}})

    with pytest.raises(RegistryValidationError, match="references unknown relation"):
        RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(mutated_modelo)


def test_validator_rejects_construct_dependency_classification_outside_revision() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    revision = modelo.revisions["2025"]
    construct = next(item for item in revision.constructs if item.id == "renta-dependent-modelos")
    mutated_construct = construct.model_copy(
        update={"dependency_classifications": (*construct.dependency_classifications, "missing-dependency")}
    )
    mutated_revision = revision.model_copy(
        update={
            "constructs": tuple(mutated_construct if item.id == construct.id else item for item in revision.constructs)
        }
    )
    mutated_modelo = modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: mutated_revision}})

    with pytest.raises(RegistryValidationError, match="references unknown dependency classification"):
        RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(mutated_modelo)


def test_validator_rejects_dependency_classification_source_drift() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    revision = modelo.revisions["2025"]
    classification = revision.dependency_classifications[0].model_copy(update={"source_modelo": "115"})
    mutated_revision = revision.model_copy(
        update={"dependency_classifications": (classification, *revision.dependency_classifications[1:])}
    )
    mutated_modelo = modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: mutated_revision}})

    with pytest.raises(RegistryValidationError, match="does not match relation"):
        RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(mutated_modelo)


def test_validator_rejects_unclassified_relation_source() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    revision = modelo.revisions["2025"]
    mutated_revision = revision.model_copy(
        update={
            "dependency_classifications": tuple(
                item for item in revision.dependency_classifications if item.source_modelo != "130"
            )
        }
    )
    mutated_modelo = modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: mutated_revision}})

    with pytest.raises(RegistryValidationError, match="relation source modelo '130' has no dependency classification"):
        RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(mutated_modelo)


def test_validator_rejects_partial_dependency_classification_relation_coverage() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    revision = modelo.revisions["2025"]
    classification = next(item for item in revision.dependency_classifications if item.source_modelo == "111")
    mutated_classification = classification.model_copy(update={"relation_refs": classification.relation_refs[:1]})
    mutated_revision = revision.model_copy(
        update={
            "dependency_classifications": tuple(
                mutated_classification if item.id == classification.id else item
                for item in revision.dependency_classifications
            )
        }
    )
    mutated_modelo = modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: mutated_revision}})

    with pytest.raises(RegistryValidationError, match="does not cover relation refs"):
        RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(mutated_modelo)


def test_schema_rejects_direct_dependency_classification_without_relation_refs() -> None:
    modelos_by_id, _catalogues = _loaded_registry()
    revision = modelos_by_id["100"].revisions["2025"]
    classification = next(item for item in revision.dependency_classifications if item.source_modelo == "130")

    with pytest.raises(ValueError, match="must declare relation_refs"):
        classification.__class__.model_validate({**classification.model_dump(mode="python"), "relation_refs": ()})


def test_validator_rejects_duplicate_dependency_classification_source() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    revision = modelo.revisions["2025"]
    classification = next(item for item in revision.dependency_classifications if item.source_modelo == "130")
    duplicate = classification.model_copy(update={"id": "renta-2025-dep-130-duplicate"})
    mutated_revision = revision.model_copy(
        update={"dependency_classifications": (*revision.dependency_classifications, duplicate)}
    )
    mutated_modelo = modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: mutated_revision}})

    with pytest.raises(RegistryValidationError, match="duplicate dependency classification source modelo '130'"):
        RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(mutated_modelo)


def test_validator_rejects_dependency_classification_target_construct_drift() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    revision = modelo.revisions["2025"]
    classification = next(item for item in revision.dependency_classifications if item.source_modelo == "190")
    construct = next(item for item in revision.constructs if item.id == "renta-work-income")
    mutated_construct = construct.model_copy(
        update={
            "dependency_classifications": tuple(
                item for item in construct.dependency_classifications if item != classification.id
            )
        }
    )
    mutated_revision = revision.model_copy(
        update={
            "constructs": tuple(mutated_construct if item.id == construct.id else item for item in revision.constructs)
        }
    )
    mutated_modelo = modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: mutated_revision}})

    with pytest.raises(RegistryValidationError, match="but the construct does not list it"):
        RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(mutated_modelo)


def test_modelo_100_renta_web_open_cross_reference_is_read_only_simulator_evidence() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    revision = modelos_by_id["100"].revisions["2025"]
    cross_reference = next(item for item in revision.live_cross_references if item.id == "modelo-100-renta-web-open")
    source = catalogues.sources[cross_reference.source_refs[0]]
    source_text = (PROJECT_ROOT / source.corpus_path).read_text(encoding="utf-8")

    assert cross_reference.surface == "open_simulator"
    assert cross_reference.synthetic_data_allowed is True
    assert cross_reference.requires_authentication is False
    assert "presentation" in cross_reference.forbidden_actions
    assert "payment" in cross_reference.forbidden_actions
    assert "funciona como un simulador" in source_text
    assert "no permite la presentaci&oacute;n de la declaraci&oacute;n" in source_text


def _select_source_revisions(
    modelo: ModeloDefinition,
    selector: Mapping[str, str | int],
) -> tuple[ModeloRevision, ...]:
    year = selector.get("year")
    revision_id = selector.get("revision_id", selector.get("revision"))
    selected: list[ModeloRevision] = []
    for revision in modelo.revisions.values():
        if isinstance(revision_id, str) and revision.id != revision_id:
            continue
        if isinstance(year, int) and not revision.period_selector.includes_year(year):
            continue
        selected.append(revision)
    return tuple(selected)
