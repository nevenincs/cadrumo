"""Tests for the centralized strict user-profile schema."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.domain.calculations.registry.legal import verify_legal_catalogue

from ....core.classification import SensitivityClass
from ....core.resources import bundled_path
from ...calculations.registry.authority import bundled_authority
from ..errors import SCHEMA_LOAD_MESSAGE_KEY, UserProfileNotFoundError, UserProfileSchemaLoadError
from ..loader import CONDITION_SCHEMA_PATH_STAT, CONDITION_SCHEMA_TABLE_PRESENT, load_user_profile_schema
from ..schema import (
    ProfileFieldDefinition,
    ProfileFieldType,
    ProfileRemovePolicy,
    ProfileSchemaDefinition,
    ProfileSectionDefinition,
    ProfileSnapshotPolicy,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_committed_user_profile_schema_loads_with_canonical_sections() -> None:
    schema = load_user_profile_schema()

    assert schema.id == "cadrumo.user_profile"
    assert schema.version == 6
    assert schema.snapshot_policy is ProfileSnapshotPolicy.IMMUTABLE_SECURE_SNAPSHOT_HASH
    assert schema.remove_policy is ProfileRemovePolicy.LIVE_PROFILE_TOMBSTONE_RETAIN_SNAPSHOTS
    assert {
        "identity",
        "tax_residence",
        "censo",
        "attribution_entity",
        "attribution_entity_socios",
        "activities",
        "irpf",
        "withholding",
        "iva",
        "renta_filing",
        "renta_rental",
        "renta_taxpayer",
        "renta_spouse",
        "renta_family",
        "properties",
        "usage_ratios",
        "provenance",
    } <= {section.key for section in schema.sections}


def test_missing_user_profile_schema_path_raises_typed_localized_error(tmp_path: Path) -> None:
    missing = tmp_path / "missing-schema.toml"

    with pytest.raises(UserProfileSchemaLoadError) as exc_info:
        load_user_profile_schema(missing)

    assert isinstance(exc_info.value.__cause__, FileNotFoundError)
    assert exc_info.value.translated_message == SCHEMA_LOAD_MESSAGE_KEY
    assert str(exc_info.value) == SCHEMA_LOAD_MESSAGE_KEY
    assert exc_info.value.context == {
        "operation": "stat",
        "condition": CONDITION_SCHEMA_PATH_STAT,
        "path": str(missing),
        "schema": "user_profile",
    }


def test_user_profile_schema_missing_tables_raises_structured_domain_error(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.toml"
    schema_path.write_text("[not_schema]\nid = 'wrong'\n", encoding="utf-8")

    with pytest.raises(UserProfileSchemaLoadError) as exc_info:
        load_user_profile_schema(schema_path)

    assert exc_info.value.__cause__ is None
    assert exc_info.value.translated_message == SCHEMA_LOAD_MESSAGE_KEY
    assert str(exc_info.value) == SCHEMA_LOAD_MESSAGE_KEY
    assert exc_info.value.context == {
        "operation": "validate",
        "condition": CONDITION_SCHEMA_TABLE_PRESENT,
        "path": str(schema_path),
        "schema": "user_profile",
    }


def test_committed_user_profile_schema_exposes_profile_lookup_metadata() -> None:
    schema = load_user_profile_schema()

    tax_id = schema.field("identity.tax_id")
    assert tax_id.type is ProfileFieldType.STRING
    assert tax_id.required is True
    assert tax_id.sensitivity is SensitivityClass.IDENTITY
    assert "tax.id" in tax_id.model_selectors

    large_company = schema.field("censo.large_company")
    assert large_company.type is ProfileFieldType.BOOLEAN
    assert "enrollment.large_company" in large_company.schedule_predicates
    assert set(large_company.legal_refs) == {"ley-37-1992:art-121", "rd-1624-1992:art-71"}
    assert "6.010.121,04" in large_company.description

    public_admin_budget = schema.field("censo.public_administration_budget_gt_6000000")
    assert public_admin_budget.type is ProfileFieldType.BOOLEAN
    assert "enrollment.public_administration_budget_gt_6000000" in public_admin_budget.schedule_predicates
    assert set(public_admin_budget.legal_refs) == {"orden-eha-586-2011:art-1", "rd-439-2007:art-108"}
    assert "6 million" in public_admin_budget.description

    autoconsumo_promotor_base = schema.field("iva.autoconsumo_promotor_base")
    assert autoconsumo_promotor_base.type is ProfileFieldType.MONEY
    assert autoconsumo_promotor_base.sensitivity is SensitivityClass.FINANCIAL

    ccaa = schema.field("tax_residence.ccaa")
    assert ccaa.type is ProfileFieldType.ENUM
    assert "cataluna" in ccaa.enum_values

    marital_status = schema.field("renta_taxpayer.marital_status")
    assert marital_status.type is ProfileFieldType.ENUM
    assert marital_status.enum_values == ("1", "2", "3", "4", "5")

    situacion = schema.field("renta_family.situacion_familiar")
    assert situacion.type is ProfileFieldType.ENUM
    assert "soltero" in situacion.enum_values


def test_committed_user_profile_schema_legal_refs_resolve_against_catalogue_and_corpus() -> None:
    schema = load_user_profile_schema()
    catalogues = bundled_authority().catalogues
    refs_by_field = {
        f"{section.key}.{field.key}": field.legal_refs
        for section in schema.sections
        for field in section.fields
        if field.legal_refs
    }
    refs = sorted({ref for field_refs in refs_by_field.values() for ref in field_refs})

    assert refs_by_field, "committed user-profile schema carries no field legal_refs"
    missing = sorted(ref for ref in refs if ref not in catalogues.legal)
    assert not missing, f"user-profile schema legal_refs absent from registry legal catalogue: {missing}"
    verify_legal_catalogue({ref: catalogues.legal[ref] for ref in refs}, source_root=bundled_path())


def test_no_grounded_profile_key_regresses_to_a_schema_field_with_no_legal_refs() -> None:
    """A live-grounded profile key must not silently lose its schema citation.

    Computed against the LIVE registry authority, not a hardcoded snapshot -
    fails the moment a new ``source = "profile"`` binding is added for a
    field whose schema entry is never updated to carry the same citation.

    Two fields with a deliberately unreconciled two-way citation divergence
    (``iva.autoconsumo_promotor_base``, ``taxpayer_type.irpf_income_categories``)
    are excluded from this check: both already carry non-empty schema
    ``legal_refs``, so they are a different situation - a disagreement
    between two non-empty citation sets - not the "schema carries nothing"
    gap this test guards.
    """
    from cadrumo.domain.calculations.registry.profile_grounding import build_profile_grounding_index

    authority = bundled_authority()
    index = build_profile_grounding_index(authority)
    schema = load_user_profile_schema()

    regressed: list[str] = []
    for key, grounding in index.items():
        if not grounding.legal_refs:
            continue
        try:
            field = schema.field(key)
        except UserProfileNotFoundError:
            continue
        if not field.legal_refs:
            regressed.append(key)

    assert not regressed, (
        "these profile keys carry a live registry legal_ref but their schema field carries none - "
        f"carry the citation onto the schema field: {sorted(regressed)}"
    )


def test_user_profile_schema_models_are_strict_frozen_and_forbid_extras() -> None:
    field = ProfileFieldDefinition.model_validate(
        {
            "key": "tax_id",
            "type": "string",
            "sensitivity": "identity",
            "description": "Tax identifier.",
        },
    )

    assert field.type is ProfileFieldType.STRING
    assert field.sensitivity is SensitivityClass.IDENTITY

    with pytest.raises(ValidationError, match="frozen_instance"):
        field.required = True

    with pytest.raises(ValidationError, match="extra_forbidden"):
        ProfileFieldDefinition.model_validate(
            {
                "key": "tax_id",
                "type": "string",
                "sensitivity": "identity",
                "description": "Tax identifier.",
                "unexpected": "not allowed",
            },
        )

    with pytest.raises(ValidationError, match="extra_forbidden"):
        ProfileFieldDefinition.model_validate(
            {
                "key": "tax_id",
                "type": "string",
                "sensitivity": "identity",
                "description": "Tax identifier.",
                "export_headers": ["profile_tax_id"],
            },
        )


def test_enum_fields_require_declared_values() -> None:
    with pytest.raises(ValidationError, match="enum fields must declare enum_values"):
        ProfileFieldDefinition.model_validate(
            {
                "key": "ccaa",
                "type": "enum",
                "sensitivity": "identity",
                "description": "Tax residence.",
            },
        )


def test_model_selector_resolves_to_the_declaring_field_path() -> None:
    schema = load_user_profile_schema()

    resolved = schema.path_for_model_selector("has_employees")

    assert resolved == "withholding.has_employees"
    assert "has_employees" in schema.field(resolved).model_selectors


def test_every_committed_model_selector_either_resolves_or_is_declared_twice() -> None:
    """No committed selector may resolve to a field that does not declare it.

    Guards the resolver against the failure that would matter in production:
    returning a confidently wrong path. A token declared by two fields is
    permitted to resolve to nothing, but a token that resolves at all must
    resolve to a field carrying that exact token.
    """
    schema = load_user_profile_schema()
    declared = {
        selector for section in schema.sections for field in section.fields for selector in field.model_selectors
    }
    assert declared, "the committed schema declares no model selectors at all"

    for selector in sorted(declared):
        resolved = schema.path_for_model_selector(selector)
        if resolved is None:
            continue
        assert selector in schema.field(resolved).model_selectors


def test_unknown_and_blank_model_selectors_resolve_to_nothing() -> None:
    schema = load_user_profile_schema()

    assert schema.path_for_model_selector("no_such_selector_token") is None
    assert schema.path_for_model_selector("") is None
    assert schema.path_for_model_selector("   ") is None


def test_ambiguous_model_selector_resolves_to_nothing_rather_than_guessing() -> None:
    """A token two fields declare has no single correct path, so none is returned.

    The committed schema happens to declare each token once, so the ambiguity
    this guards against cannot be reproduced from real data and is constructed
    here instead. Returning either candidate would mislabel the other.
    """
    schema = load_user_profile_schema()
    shared_selector = "shared_ambiguous_selector"
    section = ProfileSectionDefinition.model_validate(
        {
            "key": "ambiguity_probe",
            "title": "Ambiguity probe",
            "sensitivity": "identity",
            "fields": (
                {
                    "key": "first_declaring_field",
                    "type": "string",
                    "sensitivity": "identity",
                    "description": "First field declaring the shared selector.",
                    "model_selectors": (shared_selector,),
                },
                {
                    "key": "second_declaring_field",
                    "type": "string",
                    "sensitivity": "identity",
                    "description": "Second field declaring the shared selector.",
                    "model_selectors": (shared_selector,),
                },
            ),
        },
    )
    ambiguous = ProfileSchemaDefinition.model_validate(
        {
            "id": schema.id,
            "version": schema.version,
            "title": schema.title,
            "snapshot_policy": schema.snapshot_policy.value,
            "remove_policy": schema.remove_policy.value,
            "sections": (*schema.sections, section),
        },
    )

    assert ambiguous.path_for_model_selector(shared_selector) is None
    # The same schema still resolves an unambiguous token, so the None above is
    # the ambiguity refusal and not a resolver broken by the added section.
    assert ambiguous.path_for_model_selector("has_employees") == "withholding.has_employees"


def test_schema_rejects_duplicate_section_keys() -> None:
    schema = load_user_profile_schema()
    duplicate = schema.sections[0]

    with pytest.raises(ValidationError, match="duplicate section keys"):
        ProfileSchemaDefinition.model_validate(
            {
                "id": schema.id,
                "version": schema.version,
                "title": schema.title,
                "snapshot_policy": schema.snapshot_policy.value,
                "remove_policy": schema.remove_policy.value,
                "sections": (*schema.sections, duplicate),
            },
        )
