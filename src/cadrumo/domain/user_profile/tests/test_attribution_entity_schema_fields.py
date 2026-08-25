"""Schema coverage for attribution-entity legal form and socio facts."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from ..schema import ProfileFieldDefinition, ProfileFieldType, ProfileSchemaDefinition
from ._schema_loader_fixtures import legal_ids_fixture, module_scoped_schema

__all__ = ["legal_ids_fixture", "module_scoped_schema"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_attribution_entity_legal_form_declares_sc_and_cb(
    schema: ProfileSchemaDefinition,
    legal_ids: frozenset[str],
) -> None:
    field = schema.field("attribution_entity.legal_form")

    assert field.type is ProfileFieldType.ENUM
    assert {"sociedad_civil", "comunidad_bienes"}.issubset(set(field.enum_values))
    expected_refs = {"ley-35-2006:art-86", "ley-35-2006:art-87", "orden-hap-2250-2015:art-2"}
    assert set(field.legal_refs) == expected_refs
    assert expected_refs <= legal_ids


def test_attribution_entity_socios_section_uses_repeatable_profile_pattern(
    schema: ProfileSchemaDefinition,
) -> None:
    section = schema.section("attribution_entity_socios")

    assert section.repeatable is True
    assert {field.key for field in section.fields} == {
        "nif",
        "name",
        "share_pct",
        "base_imponible_assigned",
        "participe_clave",
        "country_of_residence",
        "role",
    }
    assert {
        "attribution_entity_socios.nif",
        "attribution_entity_socios.name",
        "attribution_entity_socios.share_pct",
        "attribution_entity_socios.base_imponible_assigned",
        "attribution_entity_socios.participe_clave",
        "attribution_entity_socios.country_of_residence",
        "attribution_entity_socios.role",
    } <= set(schema.field_paths)


def test_attribution_entity_socios_role_enum_covers_member_roles(
    schema: ProfileSchemaDefinition,
    legal_ids: frozenset[str],
) -> None:
    field = schema.field("attribution_entity_socios.role")

    assert field.type is ProfileFieldType.ENUM
    assert set(field.enum_values) == {"socio", "comunero", "participe"}
    expected_refs = {
        "ley-35-2006:art-86",
        "ley-35-2006:art-87",
        "ley-35-2006:art-88",
        "ley-35-2006:art-89",
    }
    assert set(field.legal_refs) == expected_refs
    assert expected_refs <= legal_ids


def test_attribution_entity_socios_share_pct_is_decimal_percentage(
    schema: ProfileSchemaDefinition,
    legal_ids: frozenset[str],
) -> None:
    field = schema.field("attribution_entity_socios.share_pct")

    assert field.type is ProfileFieldType.DECIMAL
    assert field.minimum == Decimal("0")
    assert field.maximum == Decimal("100")
    expected_refs = {"ley-35-2006:art-87", "ley-35-2006:art-89", "orden-hap-2250-2015:art-3"}
    assert set(field.legal_refs) == expected_refs
    assert expected_refs <= legal_ids


def test_attribution_entity_socios_base_assigned_is_explicit_money_amount(
    schema: ProfileSchemaDefinition,
    legal_ids: frozenset[str],
) -> None:
    field = schema.field("attribution_entity_socios.base_imponible_assigned")

    assert field.type is ProfileFieldType.MONEY
    assert field.required is True
    assert "Debe consignarse expresamente" in field.description
    assert "no se deduce únicamente del porcentaje de participación" in field.description
    expected_refs = {"ley-35-2006:art-87", "ley-35-2006:art-89", "orden-hap-2250-2015:art-3"}
    assert set(field.legal_refs) == expected_refs
    assert expected_refs <= legal_ids


def test_attribution_entity_socios_identity_fields_are_required_and_grounded(
    schema: ProfileSchemaDefinition,
    legal_ids: frozenset[str],
) -> None:
    expected_refs = {"ley-35-2006:art-86", "ley-35-2006:art-87", "orden-hap-2250-2015:art-3"}

    for field_path in ("attribution_entity_socios.nif", "attribution_entity_socios.name"):
        field = schema.field(field_path)
        assert field.required is True
        assert field.type is ProfileFieldType.STRING
        assert set(field.legal_refs) == expected_refs
        assert expected_refs <= legal_ids


def test_taxpayer_type_attribution_entity_branch_remains_declared(
    schema: ProfileSchemaDefinition,
) -> None:
    field = schema.field("taxpayer_type.entity_type")

    assert "attribution_entity" in field.enum_values
    assert {"ley-35-2006:art-86", "ley-35-2006:art-87"} <= set(field.legal_refs)


def test_profile_field_numeric_bounds_are_validated() -> None:
    field = ProfileFieldDefinition.model_validate(
        {
            "key": "share_pct",
            "type": "decimal",
            "required": True,
            "sensitivity": "financial",
            "description": "Participation percentage.",
            "minimum": "0",
            "maximum": "100",
        },
    )

    assert field.minimum == Decimal("0")
    assert field.maximum == Decimal("100")

    with pytest.raises(ValidationError, match="numeric bounds are only valid for numeric fields"):
        ProfileFieldDefinition.model_validate(
            {
                "key": "name",
                "type": "string",
                "sensitivity": "identity",
                "description": "Member name.",
                "minimum": Decimal("0"),
            },
        )

    with pytest.raises(ValidationError, match="minimum must be less than or equal to maximum"):
        ProfileFieldDefinition.model_validate(
            {
                "key": "share_pct",
                "type": "decimal",
                "sensitivity": "financial",
                "description": "Participation percentage.",
                "minimum": Decimal("100"),
                "maximum": Decimal("0"),
            },
        )
