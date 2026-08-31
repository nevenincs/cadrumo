"""Modelo 100 construct and export-layout registry tests."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any, cast

import pytest
from pydantic import AnyUrl, ValidationError

from .....core import CasillaId, RegistryAuthorityGrade
from ....contribuyente import (
    PROFILE_KEYS,
    RentaAscendantProfile,
    RentaDescendantProfile,
    RentaFamilyProfile,
    TaxResidenceProfile,
)
from .._validate import RegistryValidator
from .._validate_constructs import _CONSTRUCT_MEMBER_ATTRS
from ..binding_selector_utils import selector_as_dict
from ..errors import RegistryValidationError
from ..export import resolve_export_layout
from ..export_parse import parse_export_payload
from ..remote_state_guard import (
    RemoteOperation,
    assert_remote_operation_allowed,
    remote_state_policy_from_cross_reference,
)
from ..schema import DataBindingDefinition, RegistrySnapshot
from ..schema_input_kind import InputKind
from ..schema_surfaces import CasillaDefinition
from ..snapshot import build_snapshot
from ._modelo_100_registry_support import (
    _DECLARATIONS_LISTING_URL,
    _MEMBER_GROUNDED_2025_CONSTRUCT_IDS,
    _PERSONAL_FAMILY_BINDINGS,
    _PERSONAL_FAMILY_CASILLAS,
    _SOURCE_FOUNDATION_APPLICATION_LINKS,
    _assert_registry_validation_error,
    _binding_map_by_casilla,
    _loaded_registry,
    _modelo_100_revision_2025,
    _modelo_100_snapshot,
    _modelo_100_with_revision,
    _source_root,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SNAPSHOT_IDENTIFIER_KEYED_MAPS = (
    "legal",
    "sources",
    "extraction_profiles",
    "live_cross_references",
    "workbook_parity_refs",
    "verification_expectations",
    "application_links",
    "deadline_windows",
    "filing_schedules",
    "constructs",
    "dependency_classifications",
)


def _revalidate_snapshot_with_map(
    snapshot: RegistrySnapshot,
    field_name: str,
    values: Mapping[str, object],
) -> RegistrySnapshot:
    payload = {name: getattr(snapshot, name) for name in type(snapshot).model_fields}
    payload[field_name] = values
    return RegistrySnapshot.model_validate(payload)


def _snapshot_with_populated_identifier_map(field_name: str) -> tuple[RegistrySnapshot, Mapping[str, object]]:
    if field_name == "filing_schedules":
        modelos_by_id, catalogues = _loaded_registry()
        # Modelo 036 is borrowed only because it populates `filing_schedules`;
        # the subject here is identifier-map key/payload drift on the snapshot
        # model. Built at the rung 036 actually declares -- its censal alta is
        # filed on AEAT's sede and it authors no export layout, so the FILING
        # rung refuses it on a capability this test never reads.
        snapshot = build_snapshot(
            modelos_by_id["036"],
            catalogues,
            source_root=_source_root(),
            filing_year=2025,
            period="alta",
            grade=RegistryAuthorityGrade.APPLICABILITY,
        )
        return snapshot, snapshot.filing_schedules

    snapshot = _modelo_100_snapshot()
    values = cast(Mapping[str, object], getattr(snapshot, field_name))
    assert values, f"real Modelo 100 snapshot must populate {field_name}"
    return snapshot, values


def _construct_members(construct: object) -> tuple[tuple[str, str], ...]:
    """Return every (kind, member id) a construct declares.

    Driven from the registry validator's own kind-to-field mapping, so a new
    member kind reaches these assertions the moment production learns it.
    """
    members: list[tuple[str, str]] = []
    for kind, attribute in _CONSTRUCT_MEMBER_ATTRS.items():
        for member_id in getattr(construct, attribute, ()):
            assert isinstance(member_id, str)
            members.append((kind, member_id))
    return tuple(members)


def _members_of_kind(construct: object, kind: str) -> tuple[str, ...]:
    """Return the member ids a construct declares for one kind."""
    members: list[str] = []
    for member_id in getattr(construct, _CONSTRUCT_MEMBER_ATTRS[kind], ()):
        assert isinstance(member_id, str)
        members.append(member_id)
    return tuple(members)


def test_real_registry_snapshots_accept_identifier_keyed_maps() -> None:
    snapshot = _modelo_100_snapshot()
    rebuilt = RegistrySnapshot.model_validate(
        {name: getattr(snapshot, name) for name in type(snapshot).model_fields},
    )

    assert rebuilt == snapshot


@pytest.mark.parametrize("field_name", _SNAPSHOT_IDENTIFIER_KEYED_MAPS)
def test_registry_snapshot_rejects_identifier_map_key_payload_drift(field_name: str) -> None:
    snapshot, values = _snapshot_with_populated_identifier_map(field_name)
    accepted = _revalidate_snapshot_with_map(snapshot, field_name, values)
    payload = next(iter(values.values()))
    payload_id = cast(Any, payload).id
    mismatched_key = "wrong-key"
    assert getattr(accepted, field_name) == values
    assert mismatched_key != payload_id

    with pytest.raises(
        ValidationError,
        match=rf"snapshot {field_name} key 'wrong-key' does not match payload id {payload_id!r}",
    ):
        _revalidate_snapshot_with_map(snapshot, field_name, {mismatched_key: payload})


def test_modelo_100_source_foundation_matches_revision_refs_and_links() -> None:
    snapshot = _modelo_100_snapshot()
    source_foundation = snapshot.constructs["renta-source-foundation"]

    assert set(snapshot.revision.legal_refs).issubset(source_foundation.legal_refs)
    assert set(snapshot.revision.source_refs).issubset(source_foundation.source_refs)
    assert set(source_foundation.workbook_parity_refs) == set(snapshot.workbook_parity_refs)
    assert set(source_foundation.live_cross_references) == set(snapshot.live_cross_references)
    assert set(source_foundation.application_links) == _SOURCE_FOUNDATION_APPLICATION_LINKS


def test_modelo_100_personal_family_construct_members_match_expected_sets() -> None:
    snapshot = _modelo_100_snapshot()
    personal_family = snapshot.constructs["renta-personal-family"]

    assert set(personal_family.bindings) == _PERSONAL_FAMILY_BINDINGS
    assert set(personal_family.casilla_ids) == _PERSONAL_FAMILY_CASILLAS


def test_modelo_100_dependent_modelos_construct_covers_dependency_members() -> None:
    snapshot = _modelo_100_snapshot()
    dependencies = snapshot.constructs["renta-dependent-modelos"]
    # The dependent-modelos construct covers every current observation-backed slot:
    # the direct same-modelo previous_filing carries (BIN N-1) and every registered
    # cross-modelo relation_prefill fold-in slot.
    filed_dependency_bindings = {
        binding.id
        for binding in snapshot.revision.bindings
        if binding.source in {"previous_filing", "relation_prefill"}
    }
    assert set(dependencies.bindings) == filed_dependency_bindings
    assert set(dependencies.relations) == {relation.id for relation in snapshot.revision.relations}


def test_modelo_100_2025_member_grounded_constructs_do_not_declare_extra_legal_refs() -> None:
    snapshot = _modelo_100_snapshot()
    revision = snapshot.revision
    resolved_constructs = {construct.id: construct for construct in revision.constructs}
    member_indexes = {
        "casilla": {item.id: item for item in revision.casillas},
        "formula": {item.id: item for item in revision.formulas},
        "binding": {item.id: item for item in revision.bindings},
        "relation": {item.id: item for item in revision.relations},
        "dependency classification": {item.id: item for item in revision.dependency_classifications},
    }
    offenders: dict[str, list[str]] = {}

    for construct_id in _MEMBER_GROUNDED_2025_CONSTRUCT_IDS:
        construct = resolved_constructs[construct_id]
        member_refs: set[str] = set()
        for kind, member_id in _construct_members(construct):
            if kind in member_indexes:
                member_refs.update(getattr(member_indexes[kind][member_id], "legal_refs", ()))
        extra_refs = sorted(set(construct.legal_refs) - member_refs)
        if extra_refs:
            offenders[construct_id] = extra_refs

    assert not offenders


def test_modelo_100_payments_retentions_construct_covers_classified_payment_members() -> None:
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
    expected_bindings = {
        binding.id
        for binding in snapshot.revision.bindings
        if binding.source in {"previous_filing", "relation_prefill"}
        and selector_as_dict(binding).get("source_modelo") in payment_source_modelos
    }
    expected_relations = {
        relation.id for relation in snapshot.revision.relations if relation.source_modelo in payment_source_modelos
    }
    expected_classifications = {
        classification.id
        for classification in snapshot.dependency_classifications.values()
        if "renta-payments-retentions" in classification.target_constructs
    }

    assert set(payments_retentions.bindings) == expected_bindings
    assert set(payments_retentions.relations) == expected_relations
    assert set(payments_retentions.dependency_classifications) == expected_classifications
    assert "renta-2025-base-liquidable-negativa-general-anterior" not in payments_retentions.bindings
    assert (
        "renta-2025-base-liquidable-negativa-general-anterior"
        in snapshot.constructs["renta-anexo-c-base-liquidable-negativa-general"].bindings
    )


def test_modelo_100_economic_activities_construct_pins_estimacion_directa_binding() -> None:
    snapshot = _modelo_100_snapshot()
    economic_activities = snapshot.constructs["renta-economic-activities"]
    assert "renta-2025-modelo-100-estimacion-directa-es-normal" in economic_activities.bindings
    assert {"1479", "1553", "1577"}.issubset(economic_activities.casilla_ids)


def test_modelo_100_observation_parsing_construct_lists_filed_declarations_read() -> None:
    snapshot = _modelo_100_snapshot()
    observation_parsing = snapshot.constructs["renta-observation-parsing"]
    assert observation_parsing.live_cross_references == ("modelo-100-filed-declarations-read",)


def test_modelo_100_dependent_modelos_construct_carries_every_dependency_classification() -> None:
    snapshot = _modelo_100_snapshot()
    dependencies = snapshot.constructs["renta-dependent-modelos"]
    assert set(dependencies.dependency_classifications) == set(snapshot.dependency_classifications)
    assert (
        "renta-2025-dep-100"
        in snapshot.constructs["renta-anexo-c-base-liquidable-negativa-general"].dependency_classifications
    )


_CASILLA_TO_PROFILE_BINDING: Mapping[CasillaId, str] = _binding_map_by_casilla(
    ("DPNIF_D", "renta-2025-profile-tax-id"),
    ("DP_APENOM_D", "renta-2025-profile-display-name"),
    ("ZCCAD", "renta-2025-profile-tax-residence-ccaa"),
    ("TIPOTRIBUTACION", "renta-2025-profile-declaration-type"),
    ("SEXO_D", "renta-2025-profile-taxpayer-sex"),
    ("ECIVIL", "renta-2025-profile-marital-status"),
    ("DPFNAC_D", "renta-2025-profile-taxpayer-birth-date"),
    ("DPNIF_C", "renta-2025-profile-spouse-tax-id"),
    ("DP_APENOM_C", "renta-2025-profile-spouse-display-name"),
    ("DPFNAC_C", "renta-2025-profile-spouse-birth-date"),
    ("SEXO_C", "renta-2025-profile-spouse-sex"),
    ("DPGMIN_D", "renta-2025-profile-taxpayer-disability-grade"),
    ("DECFAL", "renta-2025-profile-taxpayer-death-date"),
    ("DPGMIN_C", "renta-2025-profile-spouse-disability-grade"),
    ("NORESIDENTE", "renta-2025-profile-spouse-non-resident-irpf"),
    ("RESIDENTEUE", "renta-2025-profile-spouse-eu-eea-resident"),
    ("ZRUE2", "renta-2025-profile-spouse-eu-eea-country"),
    ("HIJOSUE", "renta-2025-profile-family-descendants-eu-eea-deduction"),
    ("PH18", "renta-2025-profile-family-minor-children-in-unit"),
    ("NIFDLG", "renta-2025-family-descendant-tax-id"),
    ("APENOMDLG", "renta-2025-family-descendant-display-name"),
    ("FNACDLG", "renta-2025-family-descendant-birth-date"),
    ("MINUSDLG", "renta-2025-family-descendant-disability-grade"),
    ("FALLDLG", "renta-2025-family-descendant-death-date"),
    ("DNIASDLG", "renta-2025-family-ascendant-tax-id"),
    ("APENOMDLG_ASC", "renta-2025-family-ascendant-display-name"),
    ("ANOASDLG", "renta-2025-family-ascendant-birth-date"),
    ("PCTMINASDLG", "renta-2025-family-ascendant-disability-grade"),
    ("CONVASDLG", "renta-2025-family-ascendant-cohabiting-descendant-count"),
    ("FALLASDLG", "renta-2025-family-ascendant-death-date"),
)
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


def _assert_casilla_binding_links(casillas_by_id: Mapping[CasillaId, CasillaDefinition]) -> None:
    """Each personal/family casilla links to its declared profile binding."""
    mismatches = [
        f"{casilla_id}: expected binding {expected_binding!r}, got {casillas_by_id[casilla_id].binding!r}"
        for casilla_id, expected_binding in _CASILLA_TO_PROFILE_BINDING.items()
        if casillas_by_id[casilla_id].binding != expected_binding
    ]
    assert not mismatches, "casilla-binding link mismatches:\n  " + "\n  ".join(mismatches)


def _assert_casillas_are_bound_input(casillas_by_id: Mapping[CasillaId, CasillaDefinition]) -> None:
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
        selector_key = selector_as_dict(bindings_by_id[binding_id])["profile_key"]
        assert selector_key in profile_keys, f"{binding_id}: selector profile_key {selector_key!r} is unknown"
    for binding_id in ("renta-2025-profile-display-name", "renta-2025-profile-spouse-display-name"):
        many_keys = cast(tuple[str, ...], selector_as_dict(bindings_by_id[binding_id])["profile_keys"])
        unknown = set(many_keys) - profile_keys
        assert not unknown, f"{binding_id}: selector profile_keys outside known set: {sorted(unknown)}"


def _assert_spouse_joint_gating(bindings_by_id: Mapping[str, DataBindingDefinition]) -> None:
    """Spouse-only bindings gate on declaration type 2 (joint)."""
    for binding_id in _SPOUSE_REQUIRED_BINDINGS:
        selector = selector_as_dict(bindings_by_id[binding_id])
        assert selector["required_when_profile_key"] == "renta_filing.declaration_type", (
            f"{binding_id}: required_when_profile_key={selector['required_when_profile_key']!r}"
        )
        assert selector["required_when_value"] == "2", (
            f"{binding_id}: required_when_value={selector['required_when_value']!r}"
        )


def _assert_eu_eea_gating(bindings_by_id: Mapping[str, DataBindingDefinition]) -> None:
    """The two EU-EEA bindings chain their gating predicates correctly."""
    eu_resident_selector = selector_as_dict(bindings_by_id["renta-2025-profile-spouse-eu-eea-resident"])
    assert eu_resident_selector["required_when_profile_key"] == "renta_spouse.non_resident_irpf"
    assert eu_resident_selector["required_when_value"] == "true"
    eu_country_selector = selector_as_dict(bindings_by_id["renta-2025-profile-spouse-eu-eea-country"])
    assert eu_country_selector["required_when_profile_key"] == "renta_spouse.eu_eea_resident"
    assert eu_country_selector["required_when_value"] == "true"


def _assert_tax_residence_selector(bindings_by_id: Mapping[str, DataBindingDefinition]) -> None:
    """The tax-residence-ccaa binding's selector targets the TaxResidenceProfile model."""
    selector = selector_as_dict(bindings_by_id["renta-2025-profile-tax-residence-ccaa"])
    assert selector["profile_model"] == "TaxResidenceProfile"
    assert selector["field"] in TaxResidenceProfile.model_fields


def _assert_family_row_selectors(
    bindings_by_id: Mapping[str, DataBindingDefinition],
    casillas_by_id: Mapping[CasillaId, CasillaDefinition],
) -> None:
    """Family-row bindings address a repeating collection + field pair on RentaFamilyProfile."""
    for binding_id, (collection, field) in _FAMILY_ROW_BINDINGS.items():
        selector = selector_as_dict(bindings_by_id[binding_id])
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
        "review",
        "approval",
        "reconciliation",
        "workflow",
        "portal",
    }.issubset(links_by_surface)
    assert all(link.requires_snapshot is True for link in snapshot.revision.application_links)
    assert (
        links_by_surface["calculation"].consumer == "cadrumo.domain.calculations.registry.calculate_registry_snapshot"
    )
    assert links_by_surface["export"].consumer == "cadrumo.application.filing.export_draft"
    assert links_by_surface["filing"].consumer == "cadrumo.application.filing"
    assert "verification" not in links_by_surface
    assert links_by_surface["review"].consumer == "cadrumo.application.filing.review"
    assert links_by_surface["approval"].consumer == "cadrumo.application.filing.approval"
    assert links_by_surface["reconciliation"].consumer == "cadrumo.application.modelo.modelo_reconcile"
    assert links_by_surface["workflow"].consumer == "cadrumo.application.workflow"


def test_modelo_100_constructs_declare_their_revision_members() -> None:
    modelos_by_id, _catalogues = _loaded_registry()
    revision = modelos_by_id["100"].revisions["2025"]
    constructs = {construct.id: construct for construct in revision.constructs}
    dependencies = constructs["renta-dependent-modelos"]
    economic_activities = constructs["renta-economic-activities"]
    filed_dependency_binding_ids = {
        binding.id for binding in revision.bindings if binding.source in {"previous_filing", "relation_prefill"}
    }

    assert set(_members_of_kind(dependencies, "binding")) == filed_dependency_binding_ids
    assert set(_members_of_kind(dependencies, "relation")) == {relation.id for relation in revision.relations}
    assert "renta-2025-modelo-100-estimacion-directa-es-normal" in _members_of_kind(economic_activities, "binding")


def test_modelo_100_renta_section_constructs_classify_registered_relation_sources() -> None:
    modelos_by_id, _catalogues = _loaded_registry()
    revision = modelos_by_id["100"].revisions["2025"]
    relations_by_id = {relation.id: relation for relation in revision.relations}
    constructs = {construct.id: construct for construct in revision.constructs}
    source_modelos_by_construct = {
        construct_id: {
            relations_by_id[member_id].source_modelo
            for member_id in _members_of_kind(constructs[construct_id], "relation")
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
        "renta-real-estate-capital": set(),
        "renta-movable-capital": {"123", "193"},
        "renta-economic-activities": {"130", "131", "184"},
    }
    real_estate = constructs["renta-real-estate-capital"]
    assert "0598" in _members_of_kind(real_estate, "casilla")
    assert "renta-2025-retenciones-arrendamientos-urbanos" in _members_of_kind(real_estate, "formula")


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
    source_text = (_source_root() / source.corpus_path).read_text(encoding="utf-8")

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
        # The sede procedure ficha grounds this read only for the revisions it
        # governs. Its bundled page documents the ejercicio 2025 campaign and
        # declares applies_from 2025-01-01, so an earlier revision citing it
        # would claim grounding from a later campaign's page -- which
        # `_check_revision_scoped_source_windows` refuses at snapshot build.
        # Those years ground the same read on that year's own Renta manual,
        # which documents Renta WEB and the consulta of filed declarations.
        expected_ref = "aeat-modelo-100-procedure" if year >= 2025 else f"aeat-renta-{year}-manual-parte1"
        assert expected_ref in cross_reference.source_refs
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
        source_root=_source_root(),
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
        source_root=_source_root(),
        sources=snapshot.sources,
    )

    assert {item.casilla_id: item.value for item in parsed.casillas} == {
        "1479": Decimal("214.00"),
        "1553": Decimal("315.00"),
        "1577": Decimal("128.00"),
    }


def test_validator_rejects_construct_sources_without_official_guidance() -> None:
    modelo, revision = _modelo_100_revision_2025()
    _modelos_by_id, catalogues = _loaded_registry()
    construct = next(item for item in revision.constructs if item.source_refs)
    sources = dict(catalogues.sources)
    for source_ref in construct.source_refs:
        sources[source_ref] = sources[source_ref].model_copy(update={"evidence_tier": "layout_authority"})
    mutated_catalogues = catalogues.model_copy(update={"sources": sources})

    with pytest.raises(
        RegistryValidationError,
        match=r"construct .* requires official_source_guidance source evidence",
    ):
        RegistryValidator(mutated_catalogues, source_root=_source_root()).validate_modelo(modelo)


def test_validator_rejects_construct_legal_refs_without_legal_authority() -> None:
    modelo, revision = _modelo_100_revision_2025()
    _modelos_by_id, catalogues = _loaded_registry()
    construct = next(item for item in revision.constructs if item.legal_refs)
    legal = dict(catalogues.legal)
    legal_ref = construct.legal_refs[0]
    legal[legal_ref] = legal[legal_ref].model_copy(update={"evidence_tier": "official_source_guidance"})
    mutated_catalogues = catalogues.model_copy(update={"legal": legal})

    with pytest.raises(
        RegistryValidationError,
        match=r"construct .* legal ref .* is not legal authority",
    ):
        RegistryValidator(mutated_catalogues, source_root=_source_root()).validate_modelo(modelo)


def test_validator_rejects_construct_member_outside_revision() -> None:
    modelo, revision = _modelo_100_revision_2025()
    construct = next(item for item in revision.constructs if item.id == "renta-dependent-modelos")
    mutated_construct = construct.model_copy(update={"relations": (*construct.relations, "missing-relation")})
    mutated_revision = revision.model_copy(
        update={
            "constructs": tuple(mutated_construct if item.id == construct.id else item for item in revision.constructs),
        },
    )
    mutated_modelo = _modelo_100_with_revision(modelo, mutated_revision)

    _assert_registry_validation_error(mutated_modelo, match="references unknown relation")


def test_validator_rejects_construct_dependency_classification_outside_revision() -> None:
    modelo, revision = _modelo_100_revision_2025()
    construct = next(item for item in revision.constructs if item.id == "renta-dependent-modelos")
    mutated_construct = construct.model_copy(
        update={"dependency_classifications": (*construct.dependency_classifications, "missing-dependency")},
    )
    mutated_revision = revision.model_copy(
        update={
            "constructs": tuple(mutated_construct if item.id == construct.id else item for item in revision.constructs),
        },
    )
    mutated_modelo = _modelo_100_with_revision(modelo, mutated_revision)

    _assert_registry_validation_error(mutated_modelo, match="references unknown dependency classification")


def test_validator_rejects_dependency_classification_source_drift() -> None:
    modelo, revision = _modelo_100_revision_2025()
    classification = revision.dependency_classifications[0].model_copy(update={"source_modelo": "115"})
    mutated_revision = revision.model_copy(
        update={"dependency_classifications": (classification, *revision.dependency_classifications[1:])},
    )
    mutated_modelo = _modelo_100_with_revision(modelo, mutated_revision)

    _assert_registry_validation_error(mutated_modelo, match="does not match relation")


def test_validator_rejects_unclassified_relation_source() -> None:
    modelo, revision = _modelo_100_revision_2025()
    mutated_revision = revision.model_copy(
        update={
            "dependency_classifications": tuple(
                item for item in revision.dependency_classifications if item.source_modelo != "130"
            ),
        },
    )
    mutated_modelo = _modelo_100_with_revision(modelo, mutated_revision)

    _assert_registry_validation_error(
        mutated_modelo,
        match="relation source modelo '130' has no dependency classification",
    )


def test_validator_rejects_partial_dependency_classification_relation_coverage() -> None:
    modelo, revision = _modelo_100_revision_2025()
    classification = next(item for item in revision.dependency_classifications if item.source_modelo == "111")
    mutated_classification = classification.model_copy(update={"relation_refs": classification.relation_refs[:1]})
    mutated_revision = revision.model_copy(
        update={
            "dependency_classifications": tuple(
                mutated_classification if item.id == classification.id else item
                for item in revision.dependency_classifications
            ),
        },
    )
    mutated_modelo = _modelo_100_with_revision(modelo, mutated_revision)

    _assert_registry_validation_error(mutated_modelo, match="does not cover relation refs")


def test_schema_accepts_direct_previous_filing_classification_without_relation_refs() -> None:
    modelos_by_id, _catalogues = _loaded_registry()
    revision = modelos_by_id["100"].revisions["2025"]
    classification = next(item for item in revision.dependency_classifications if item.source_modelo == "100")

    assert classification.treatment == "direct_annual_settlement"
    assert classification.relation_refs == ()
    assert classification.__class__.model_validate(classification.model_dump(mode="python")) == classification


def test_validator_rejects_direct_dependency_classification_without_relation_or_direct_binding() -> None:
    modelo, revision = _modelo_100_revision_2025()
    classification = next(item for item in revision.dependency_classifications if item.source_modelo == "130")
    mutated_classification = classification.model_copy(update={"relation_refs": ()})
    mutated_revision = revision.model_copy(
        update={
            "dependency_classifications": tuple(
                mutated_classification if item.id == classification.id else item
                for item in revision.dependency_classifications
            ),
        },
    )
    mutated_modelo = _modelo_100_with_revision(modelo, mutated_revision)

    _assert_registry_validation_error(
        mutated_modelo,
        match="must declare relation refs or cover direct previous_filing bindings",
    )


def test_validator_rejects_duplicate_dependency_classification_source() -> None:
    modelo, revision = _modelo_100_revision_2025()
    classification = next(item for item in revision.dependency_classifications if item.source_modelo == "130")
    duplicate = classification.model_copy(update={"id": "renta-2025-dep-130-duplicate"})
    mutated_revision = revision.model_copy(
        update={"dependency_classifications": (*revision.dependency_classifications, duplicate)},
    )
    mutated_modelo = _modelo_100_with_revision(modelo, mutated_revision)

    _assert_registry_validation_error(
        mutated_modelo,
        match="duplicate dependency classification source modelo '130'",
    )


def test_validator_rejects_dependency_classification_target_construct_drift() -> None:
    modelo, revision = _modelo_100_revision_2025()
    classification = next(item for item in revision.dependency_classifications if item.source_modelo == "190")
    construct = next(item for item in revision.constructs if item.id == "renta-work-income")
    mutated_construct = construct.model_copy(
        update={
            "dependency_classifications": tuple(
                item for item in construct.dependency_classifications if item != classification.id
            ),
        },
    )
    mutated_revision = revision.model_copy(
        update={
            "constructs": tuple(mutated_construct if item.id == construct.id else item for item in revision.constructs),
        },
    )
    mutated_modelo = _modelo_100_with_revision(modelo, mutated_revision)

    _assert_registry_validation_error(mutated_modelo, match="but the construct does not list it")


def test_modelo_100_renta_web_open_cross_reference_is_read_only_simulator_evidence() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    revision = modelos_by_id["100"].revisions["2025"]
    cross_reference = next(item for item in revision.live_cross_references if item.id == "modelo-100-renta-web-open")
    source = catalogues.sources[cross_reference.source_refs[0]]
    source_text = (_source_root() / source.corpus_path).read_text(encoding="utf-8")

    assert cross_reference.surface == "open_simulator"
    assert cross_reference.synthetic_data_allowed is False
    assert cross_reference.requires_authentication is False
    assert "presentation" in cross_reference.forbidden_actions
    assert "payment" in cross_reference.forbidden_actions
    assert "funciona como un simulador" in source_text
    assert "no permite la presentaci&oacute;n de la declaraci&oacute;n" in source_text
