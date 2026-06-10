"""Tests for the Modelo 100 registry foundation."""

from __future__ import annotations

import json
from collections.abc import Mapping
from decimal import Decimal
from functools import cache
from typing import Any, cast

import pytest
from pydantic import AnyUrl

from .....core.resources import bundled_path
from .....tests.aeat_literal_fixtures import aeat_url, configured_path
from .... import renta as _renta_snapshot_checks  # noqa: F401  # snapshot-check registration side effect
from ....contribuyente import PROFILE_KEYS, TaxResidenceProfile
from ....contribuyente.family import RentaAscendantProfile, RentaDescendantProfile, RentaFamilyProfile
from .. import (
    CasillaDefinition,
    DataBindingDefinition,
    InputKind,
    ModeloDefinition,
    ModeloRevision,
    RegistryCatalogues,
    RegistrySnapshot,
    RegistrySnapshotError,
    RegistryValidationError,
    RegistryValidator,
    RemoteOperation,
    assert_remote_operation_allowed,
    build_snapshot,
    load_registry_tree,
    parse_export_payload,
    remote_state_policy_from_cross_reference,
    resolve_construct,
    resolve_export_layout,
    resolve_revision_constructs,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DECLARATIONS_LISTING_URL = aeat_url("www6", configured_path("sede_paths", "declarations_listing"))


@cache
def _loaded_registry() -> tuple[dict[str, ModeloDefinition], RegistryCatalogues]:
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    return {modelo.id: modelo for modelo in modelos}, catalogues


@cache
def _modelo_100_snapshot(filing_year: int = 2025) -> RegistrySnapshot:
    modelos_by_id, catalogues = _loaded_registry()
    return build_snapshot(
        modelos_by_id["100"],
        catalogues,
        source_root=bundled_path(),
        filing_year=filing_year,
        period="0A",
    )


def test_modelo_100_revisions_match_record_design_manifest() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    manifest_path = bundled_path("corpus", "aeat_official", "disenos_registro", "modelo_100", "manifest.json")
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
    modelos_by_id, catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    revision = modelo.revisions["2025"]

    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)
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


_PERSONAL_FAMILY_BINDINGS: frozenset[str] = frozenset(
    {
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
)

_PERSONAL_FAMILY_CASILLAS: frozenset[str] = frozenset(
    {
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
)

_SOURCE_FOUNDATION_APPLICATION_LINKS: frozenset[str] = frozenset(
    {
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
)


def test_modelo_100_source_foundation_inherits_revision_legal_and_source_refs() -> None:
    snapshot = _modelo_100_snapshot()
    source_foundation = snapshot.constructs["renta-source-foundation"]
    assert set(snapshot.revision.legal_refs).issubset(source_foundation.legal_refs)
    assert set(snapshot.revision.source_refs).issubset(source_foundation.source_refs)


def test_modelo_100_source_foundation_carries_workbook_and_live_cross_references() -> None:
    snapshot = _modelo_100_snapshot()
    source_foundation = snapshot.constructs["renta-source-foundation"]
    assert set(source_foundation.workbook_parity_refs) == set(snapshot.workbook_parity_refs)
    assert set(source_foundation.live_cross_references) == set(snapshot.live_cross_references)


def test_modelo_100_source_foundation_application_links_match_expected_set() -> None:
    snapshot = _modelo_100_snapshot()
    source_foundation = snapshot.constructs["renta-source-foundation"]
    assert set(source_foundation.application_links) == _SOURCE_FOUNDATION_APPLICATION_LINKS


def test_modelo_100_personal_family_construct_bindings_match_expected_set() -> None:
    snapshot = _modelo_100_snapshot()
    personal_family = snapshot.constructs["renta-personal-family"]
    assert set(personal_family.bindings) == _PERSONAL_FAMILY_BINDINGS


def test_modelo_100_personal_family_construct_casillas_match_expected_set() -> None:
    snapshot = _modelo_100_snapshot()
    personal_family = snapshot.constructs["renta-personal-family"]
    assert set(personal_family.casillas) == _PERSONAL_FAMILY_CASILLAS


def test_modelo_100_dependent_modelos_construct_covers_every_previous_filing_binding() -> None:
    snapshot = _modelo_100_snapshot()
    dependencies = snapshot.constructs["renta-dependent-modelos"]
    # The dependent-modelos construct covers every observation-backed slot: the
    # direct same-modelo previous_filing carries (BIN N-1) AND the cross-modelo
    # relation_prefill fold-in slots (130/131/111/115/123/180/184/190/193). The
    # latter were re-stamped from previous_filing to relation_prefill when the
    # relation became canonical for cross-modelo fold-ins (aggregation-taxonomy
    # ADR ruling 3).
    filed_dependency_bindings = {
        binding.id
        for binding in snapshot.revision.bindings
        if binding.source in {"previous_filing", "relation_prefill"}
    }
    assert set(dependencies.bindings) == filed_dependency_bindings


def test_modelo_100_dependent_modelos_construct_covers_every_revision_relation() -> None:
    snapshot = _modelo_100_snapshot()
    dependencies = snapshot.constructs["renta-dependent-modelos"]
    assert set(dependencies.relations) == {relation.id for relation in snapshot.revision.relations}


def test_modelo_100_payments_retentions_construct_covers_classified_payment_bindings() -> None:
    """payments_retentions covers retention + pagos-a-cuenta filings only.

    Some previous_filing bindings are not payment/retention sources:
    Modelo 184 belongs to economic-activities attribution semantics, and
    prior-year Modelo 100 base-liquidation carry-forward belongs to Anexo C.
    """
    snapshot = _modelo_100_snapshot()
    payments_retentions = snapshot.constructs["renta-payments-retentions"]
    payment_source_modelos = {
        classification.source_modelo
        for classification in snapshot.revision.dependency_classifications
        if "renta-payments-retentions" in classification.target_constructs
    }
    expected = {
        binding.id
        for binding in snapshot.revision.bindings
        if binding.source in {"previous_filing", "relation_prefill"}
        and binding.selector.get("source_modelo") in payment_source_modelos
    }

    assert set(payments_retentions.bindings) == expected
    assert "renta-2025-base-liquidable-negativa-general-anterior" not in payments_retentions.bindings
    assert (
        "renta-2025-base-liquidable-negativa-general-anterior"
        in snapshot.constructs["renta-anexo-c-base-liquidable-negativa-general"].bindings
    )


def test_modelo_100_payments_retentions_construct_excludes_atribucion_relations() -> None:
    snapshot = _modelo_100_snapshot()
    payments_retentions = snapshot.constructs["renta-payments-retentions"]
    payment_source_modelos = {
        classification.source_modelo
        for classification in snapshot.revision.dependency_classifications
        if "renta-payments-retentions" in classification.target_constructs
    }
    expected = {
        relation.id for relation in snapshot.revision.relations if relation.source_modelo in payment_source_modelos
    }
    assert set(payments_retentions.relations) == expected


def test_modelo_100_economic_activities_construct_pins_estimacion_directa_binding() -> None:
    snapshot = _modelo_100_snapshot()
    economic_activities = snapshot.constructs["renta-economic-activities"]
    assert "renta-2025-modelo-100-estimacion-directa-es-normal" in economic_activities.bindings
    assert {"1479", "1553", "1577"}.issubset(economic_activities.casillas)


def test_modelo_100_observation_parsing_construct_lists_filed_declarations_read() -> None:
    snapshot = _modelo_100_snapshot()
    observation_parsing = snapshot.constructs["renta-observation-parsing"]
    assert observation_parsing.live_cross_references == ("modelo-100-filed-declarations-read",)


def test_modelo_100_dependent_modelos_construct_carries_every_dependency_classification() -> None:
    snapshot = _modelo_100_snapshot()
    dependencies = snapshot.constructs["renta-dependent-modelos"]
    assert set(dependencies.dependency_classifications) == set(snapshot.dependency_classifications)


def test_modelo_100_payments_retentions_construct_dependency_classifications_target_payments() -> None:
    snapshot = _modelo_100_snapshot()
    payments_retentions = snapshot.constructs["renta-payments-retentions"]
    expected = {
        classification.id
        for classification in snapshot.dependency_classifications.values()
        if "renta-payments-retentions" in classification.target_constructs
    }
    assert set(payments_retentions.dependency_classifications) == expected


_CASILLA_TO_PROFILE_BINDING: Mapping[str, str] = {
    "DPNIF_D": "renta-2025-profile-tax-id",
    "DP_APENOM_D": "renta-2025-profile-display-name",
    "ZCCAD": "renta-2025-profile-tax-residence-ccaa",
    "TIPOTRIBUTACION": "renta-2025-profile-declaration-type",
    "SEXO_D": "renta-2025-profile-taxpayer-sex",
    "ECIVIL": "renta-2025-profile-marital-status",
    "DPFNAC_D": "renta-2025-profile-taxpayer-birth-date",
    "DPNIF_C": "renta-2025-profile-spouse-tax-id",
    "DP_APENOM_C": "renta-2025-profile-spouse-display-name",
    "DPFNAC_C": "renta-2025-profile-spouse-birth-date",
    "SEXO_C": "renta-2025-profile-spouse-sex",
    "DPGMIN_D": "renta-2025-profile-taxpayer-disability-grade",
    "DECFAL": "renta-2025-profile-taxpayer-death-date",
    "DPGMIN_C": "renta-2025-profile-spouse-disability-grade",
    "NORESIDENTE": "renta-2025-profile-spouse-non-resident-irpf",
    "RESIDENTEUE": "renta-2025-profile-spouse-eu-eea-resident",
    "ZRUE2": "renta-2025-profile-spouse-eu-eea-country",
    "HIJOSUE": "renta-2025-profile-family-descendants-eu-eea-deduction",
    "PH18": "renta-2025-profile-family-minor-children-in-unit",
    "NIFDLG": "renta-2025-family-descendant-tax-id",
    "APENOMDLG": "renta-2025-family-descendant-display-name",
    "FNACDLG": "renta-2025-family-descendant-birth-date",
    "MINUSDLG": "renta-2025-family-descendant-disability-grade",
    "FALLDLG": "renta-2025-family-descendant-death-date",
    "DNIASDLG": "renta-2025-family-ascendant-tax-id",
    "APENOMDLG_ASC": "renta-2025-family-ascendant-display-name",
    "ANOASDLG": "renta-2025-family-ascendant-birth-date",
    "PCTMINASDLG": "renta-2025-family-ascendant-disability-grade",
    "CONVASDLG": "renta-2025-family-ascendant-cohabiting-descendant-count",
    "FALLASDLG": "renta-2025-family-ascendant-death-date",
}
"""Maps each personal/family casilla id to the profile binding that feeds it.

Single source of truth for the binding-presence, casilla-binding link,
and bound-input-kind checks in
:func:`test_modelo_100_personal_family_profile_bindings_target_profile_schema`.
Adding a new profile-bound casilla means adding one row here.
"""

_PROFILE_KEY_BINDINGS: tuple[str, ...] = (
    "renta-2025-profile-tax-id",
    "renta-2025-profile-declaration-type",
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
)
"""Bindings whose selector carries a single ``profile_key`` (vs ``profile_keys`` tuple)."""

_SPOUSE_REQUIRED_BINDINGS: tuple[str, ...] = (
    "renta-2025-profile-spouse-tax-id",
    "renta-2025-profile-spouse-display-name",
    "renta-2025-profile-spouse-birth-date",
    "renta-2025-profile-spouse-sex",
)
"""Bindings whose ``required_when_*`` selector is keyed on declaration type == joint."""

_FAMILY_ROW_BINDINGS: Mapping[str, tuple[str, str]] = {
    "renta-2025-family-descendant-tax-id": ("descendants", "tax_id"),
    "renta-2025-family-descendant-display-name": ("descendants", "display_name"),
    "renta-2025-family-descendant-birth-date": ("descendants", "birth_date"),
    "renta-2025-family-descendant-disability-grade": ("descendants", "disability_grade"),
    "renta-2025-family-descendant-death-date": ("descendants", "death_date"),
    "renta-2025-family-ascendant-tax-id": ("ascendants", "tax_id"),
    "renta-2025-family-ascendant-display-name": ("ascendants", "display_name"),
    "renta-2025-family-ascendant-birth-date": ("ascendants", "birth_date"),
    "renta-2025-family-ascendant-disability-grade": ("ascendants", "disability_grade"),
    "renta-2025-family-ascendant-cohabiting-descendant-count": ("ascendants", "cohabiting_descendant_count"),
    "renta-2025-family-ascendant-death-date": ("ascendants", "death_date"),
}
"""Family row bindings → (collection name on RentaFamilyProfile, field name on the row model)."""


def test_modelo_100_personal_family_profile_bindings_target_profile_schema() -> None:
    snapshot = _modelo_100_snapshot()
    profile_keys = {entry.key for entry in PROFILE_KEYS}
    bindings_by_id = {binding.id: binding for binding in snapshot.revision.bindings if binding.source == "profile"}
    casillas_by_id = {casilla.id: casilla for casilla in snapshot.revision.casillas}

    _assert_profile_bindings_present(bindings_by_id)
    _assert_casilla_binding_links(casillas_by_id)
    _assert_casillas_are_bound_input(casillas_by_id)
    _assert_selector_profile_keys(bindings_by_id, profile_keys=profile_keys)
    _assert_spouse_joint_gating(bindings_by_id)
    _assert_eu_eea_gating(bindings_by_id)
    _assert_tax_residence_selector(bindings_by_id)
    _assert_family_row_selectors(bindings_by_id, casillas_by_id)


def _assert_profile_bindings_present(bindings_by_id: Mapping[str, DataBindingDefinition]) -> None:
    """Every casilla-mapped profile binding is declared on the snapshot."""
    missing = set(_CASILLA_TO_PROFILE_BINDING.values()) - bindings_by_id.keys()
    assert not missing, f"missing profile bindings: {sorted(missing)}"


def _assert_casilla_binding_links(casillas_by_id: Mapping[str, CasillaDefinition]) -> None:
    """Each personal/family casilla links to its declared profile binding."""
    mismatches = [
        f"{casilla_id}: expected binding {expected_binding!r}, got {casillas_by_id[casilla_id].binding!r}"
        for casilla_id, expected_binding in _CASILLA_TO_PROFILE_BINDING.items()
        if casillas_by_id[casilla_id].binding != expected_binding
    ]
    assert not mismatches, "casilla-binding link mismatches:\n  " + "\n  ".join(mismatches)


def _assert_casillas_are_bound_input(casillas_by_id: Mapping[str, CasillaDefinition]) -> None:
    """Every personal/family casilla is ``input_kind='bound'`` (profile-fed)."""
    non_bound = [
        f"{casilla_id}: input_kind={casillas_by_id[casilla_id].input_kind!r}"
        for casilla_id in _CASILLA_TO_PROFILE_BINDING
        if casillas_by_id[casilla_id].input_kind != InputKind.BOUND
    ]
    assert not non_bound, "casillas not marked bound:\n  " + "\n  ".join(non_bound)


def _assert_selector_profile_keys(
    bindings_by_id: Mapping[str, DataBindingDefinition],
    *,
    profile_keys: set[str],
) -> None:
    """Single-key + many-key selector references all land inside the declared profile keyset."""
    for binding_id in _PROFILE_KEY_BINDINGS:
        selector_key = bindings_by_id[binding_id].selector["profile_key"]
        assert selector_key in profile_keys, f"{binding_id}: selector profile_key {selector_key!r} is unknown"
    for binding_id in ("renta-2025-profile-display-name", "renta-2025-profile-spouse-display-name"):
        many_keys = cast(tuple[str, ...], bindings_by_id[binding_id].selector["profile_keys"])
        unknown = set(many_keys) - profile_keys
        assert not unknown, f"{binding_id}: selector profile_keys outside known set: {sorted(unknown)}"


def _assert_spouse_joint_gating(bindings_by_id: Mapping[str, DataBindingDefinition]) -> None:
    """Spouse-only bindings gate on declaration type 2 (joint)."""
    for binding_id in _SPOUSE_REQUIRED_BINDINGS:
        selector = bindings_by_id[binding_id].selector
        assert selector["required_when_profile_key"] == "filing_export.declaration_type", (
            f"{binding_id}: required_when_profile_key={selector['required_when_profile_key']!r}"
        )
        assert selector["required_when_value"] == "2", (
            f"{binding_id}: required_when_value={selector['required_when_value']!r}"
        )


def _assert_eu_eea_gating(bindings_by_id: Mapping[str, DataBindingDefinition]) -> None:
    """The two EU-EEA bindings chain their gating predicates correctly."""
    eu_resident_selector = bindings_by_id["renta-2025-profile-spouse-eu-eea-resident"].selector
    assert eu_resident_selector["required_when_profile_key"] == "renta_spouse.non_resident_irpf"
    assert eu_resident_selector["required_when_value"] == "true"
    eu_country_selector = bindings_by_id["renta-2025-profile-spouse-eu-eea-country"].selector
    assert eu_country_selector["required_when_profile_key"] == "renta_spouse.eu_eea_resident"
    assert eu_country_selector["required_when_value"] == "true"


def _assert_tax_residence_selector(bindings_by_id: Mapping[str, DataBindingDefinition]) -> None:
    """The tax-residence-ccaa binding's selector targets the TaxResidenceProfile model."""
    selector = bindings_by_id["renta-2025-profile-tax-residence-ccaa"].selector
    assert selector["profile_model"] == "TaxResidenceProfile"
    assert selector["field"] in TaxResidenceProfile.model_fields


def _assert_family_row_selectors(
    bindings_by_id: Mapping[str, DataBindingDefinition],
    casillas_by_id: Mapping[str, CasillaDefinition],
) -> None:
    """Family-row bindings address a repeating collection + field pair on RentaFamilyProfile."""
    for binding_id, (collection, field) in _FAMILY_ROW_BINDINGS.items():
        selector = bindings_by_id[binding_id].selector
        assert selector["profile_model"] == "RentaFamilyProfile", binding_id
        assert selector["collection"] == collection, binding_id
        assert collection in RentaFamilyProfile.model_fields, binding_id
        assert selector["field"] == field, binding_id
        assert selector["repeating"] is True, binding_id
        assert selector["dictionary_field"] in casillas_by_id, binding_id
        row_model_fields = (
            RentaDescendantProfile.model_fields if collection == "descendants" else RentaAscendantProfile.model_fields
        )
        assert field in row_model_fields, f"{binding_id}: row field {field!r} missing on {collection} model"


def test_modelo_100_application_links_route_current_workflows_through_snapshots() -> None:
    snapshot = _modelo_100_snapshot()
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
    assert links_by_surface["export"].consumer == "aeat.application.filing.export_draft"
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
    filed_dependency_binding_ids = {
        binding.id for binding in revision.bindings if binding.source in {"previous_filing", "relation_prefill"}
    }

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
        "renta-economic-activities": {"130", "131", "184"},
    }


def test_modelo_100_dependency_classifications_cover_registered_relation_sources() -> None:
    snapshot = _modelo_100_snapshot()
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


def test_modelo_100_authenticated_filed_data_cross_reference_is_guarded_read_only() -> None:
    _modelos_by_id, catalogues = _loaded_registry()
    source = catalogues.sources["aeat-modelo-100-procedure"]
    source_text = (bundled_path() / source.corpus_path).read_text(encoding="utf-8")

    assert "Consulta de declaraciones presentadas" in source_text
    assert "Datos fiscales" in source_text

    for year in range(2020, 2026):
        snapshot = _modelo_100_snapshot(year)
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
                url=AnyUrl(_DECLARATIONS_LISTING_URL),
            ),
        )
        with pytest.raises(RegistryValidationError, match="remote write method"):
            assert_remote_operation_allowed(
                policy,
                RemoteOperation(
                    kind="http",
                    method="POST",
                    url=AnyUrl(_DECLARATIONS_LISTING_URL),
                ),
            )


def test_modelo_100_live_cross_references_block_declared_forbidden_actions() -> None:
    snapshot = _modelo_100_snapshot()
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
    snapshot = _modelo_100_snapshot(2023)
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
        source_root=bundled_path(),
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
    snapshot = _modelo_100_snapshot()
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
        source_root=bundled_path(),
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


def test_construct_reader_rejects_unknown_member_id_at_runtime() -> None:
    """`resolve_construct` carries a defence-in-depth runtime check: if a
    construct's member tuple references an id absent from the matching
    revision index, it raises `RegistrySnapshotError` mentioning the
    construct id, the member kind, and the unknown id. The pre-flight
    validator should normally catch this, but the runtime gate must hold
    independently — this test pins the message format and the runtime
    branch."""
    modelos_by_id, _catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    revision = modelo.revisions["2025"]
    construct = next(item for item in revision.constructs if item.casillas)
    mutated_construct = construct.model_copy(update={"casillas": (*construct.casillas, "0000-ghost")})
    mutated_revision = revision.model_copy(
        update={
            "constructs": tuple(mutated_construct if item.id == construct.id else item for item in revision.constructs)
        }
    )

    with pytest.raises(
        RegistrySnapshotError,
        match=rf"construct '{construct.id}' references unknown casilla '0000-ghost'",
    ):
        resolve_construct(mutated_revision, construct.id)


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
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(mutated_modelo)


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
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(mutated_modelo)


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
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(mutated_modelo)


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
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(mutated_modelo)


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
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(mutated_modelo)


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
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(mutated_modelo)


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
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(mutated_modelo)


def test_modelo_100_renta_web_open_cross_reference_is_read_only_simulator_evidence() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    revision = modelos_by_id["100"].revisions["2025"]
    cross_reference = next(item for item in revision.live_cross_references if item.id == "modelo-100-renta-web-open")
    source = catalogues.sources[cross_reference.source_refs[0]]
    source_text = (bundled_path() / source.corpus_path).read_text(encoding="utf-8")

    assert cross_reference.surface == "open_simulator"
    assert cross_reference.synthetic_data_allowed is False
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
