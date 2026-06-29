"""Tests for the centralized strict user-profile schema."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from ....core.classification import SensitivityClass
from .. import (
    ProfileFieldDefinition,
    ProfileFieldType,
    ProfileRemovePolicy,
    ProfileSchemaDefinition,
    ProfileSnapshotPolicy,
    UserProfileSchemaLoadError,
    load_user_profile_schema,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_committed_user_profile_schema_loads_with_canonical_sections() -> None:
    schema = load_user_profile_schema()

    assert schema.id == "aeat.user_profile"
    assert schema.version == 2
    assert schema.snapshot_policy is ProfileSnapshotPolicy.IMMUTABLE_SECURE_SNAPSHOT_HASH
    assert schema.remove_policy is ProfileRemovePolicy.LIVE_PROFILE_TOMBSTONE_RETAIN_SNAPSHOTS
    assert {
        "identity",
        "tax_residence",
        "censo",
        "activities",
        "irpf",
        "withholding",
        "iva",
        "filing_export",
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
    assert exc_info.value.translated_message == "errors.fail.fail_user_profile_schema_load"
    assert exc_info.value.context == {
        "operation": "stat",
        "path": str(missing),
        "schema": "user_profile",
    }


def test_user_profile_schema_missing_tables_raises_structured_domain_error(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.toml"
    schema_path.write_text("[not_schema]\nid = 'wrong'\n", encoding="utf-8")

    with pytest.raises(UserProfileSchemaLoadError) as exc_info:
        load_user_profile_schema(schema_path)

    assert exc_info.value.__cause__ is None
    assert exc_info.value.translated_message == "errors.fail.fail_user_profile_schema_load"
    assert exc_info.value.context == {
        "operation": "validate",
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

    autoconsumo_promotor_base = schema.field("iva.autoconsumo_promotor_base")
    assert autoconsumo_promotor_base.type is ProfileFieldType.MONEY
    assert autoconsumo_promotor_base.sensitivity is SensitivityClass.FINANCIAL

    ccaa = schema.field("tax_residence.ccaa")
    assert ccaa.type is ProfileFieldType.ENUM
    assert "cataluna" in ccaa.enum_values

    situacion = schema.field("renta_family.situacion_familiar")
    assert situacion.type is ProfileFieldType.ENUM
    assert "soltero" in situacion.enum_values


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
