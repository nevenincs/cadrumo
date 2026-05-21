"""Tests for the centralized strict user-profile schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aeat.core.classification import SensitivityClass

from . import (
    ProfileFieldDefinition,
    ProfileFieldType,
    ProfileRemovePolicy,
    ProfileSchemaDefinition,
    ProfileSnapshotPolicy,
    load_user_profile_schema,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def test_committed_user_profile_schema_loads_with_canonical_sections() -> None:
    schema = load_user_profile_schema()

    assert schema.id == "aeat.user_profile"
    assert schema.version == 2
    assert schema.snapshot_policy is ProfileSnapshotPolicy.IMMUTABLE_SECURE_SNAPSHOT_HASH
    assert schema.remove_policy is ProfileRemovePolicy.LIVE_PROFILE_TOMBSTONE_RETAIN_SNAPSHOTS
    assert {
        "identity",
        "tax_residence",
        "census",
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


def test_committed_user_profile_schema_exposes_profile_lookup_metadata() -> None:
    schema = load_user_profile_schema()

    tax_id = schema.field("identity.tax_id")
    assert tax_id.type is ProfileFieldType.STRING
    assert tax_id.required is True
    assert tax_id.sensitivity is SensitivityClass.IDENTITY
    assert "tax.id" in tax_id.model_selectors

    large_company = schema.field("census.large_company")
    assert large_company.type is ProfileFieldType.BOOLEAN
    assert "enrollment.large_company" in large_company.schedule_predicates

    ccaa = schema.field("tax_residence.ccaa")
    assert ccaa.type is ProfileFieldType.ENUM
    assert "cataluna" in ccaa.enum_values


def test_user_profile_schema_models_are_strict_frozen_and_forbid_extras() -> None:
    field = ProfileFieldDefinition.model_validate(
        {
            "key": "tax_id",
            "type": "string",
            "sensitivity": "identity",
            "description": "Tax identifier.",
        }
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
            }
        )


def test_enum_fields_require_declared_values() -> None:
    with pytest.raises(ValidationError, match="enum fields must declare enum_values"):
        ProfileFieldDefinition.model_validate(
            {
                "key": "ccaa",
                "type": "enum",
                "sensitivity": "identity",
                "description": "Tax residence.",
            }
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
            }
        )
