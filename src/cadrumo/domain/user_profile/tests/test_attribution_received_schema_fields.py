"""Schema coverage for the socio-side attribution_received fact group.

The ``attribution_received`` repeatable section is the member-side counterpart of
``attribution_entity_socios``: the attribution entity (sociedad civil, comunidad
de bienes, herencia yacente) files Modelo 184 in its own workspace, and a member
socio records the share it received here so the member's own Modelo 100 has a
typed, provenance-carrying home for the attributed base. Grounded in LIRPF
arts. 86-89 (régimen de atribución de rentas).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ..schema import ProfileFieldType, ProfileSchemaDefinition
from ._schema_loader_fixtures import legal_ids_fixture, module_scoped_schema

__all__ = ["legal_ids_fixture", "module_scoped_schema"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_attribution_received_section_uses_repeatable_profile_pattern(
    schema: ProfileSchemaDefinition,
) -> None:
    section = schema.section("attribution_received")

    assert section.repeatable is True
    assert {field.key for field in section.fields} == {
        "entity_nif",
        "entity_name",
        "share_pct",
        "base_imponible_attributed",
        "filing_year",
    }
    assert {
        "attribution_received.entity_nif",
        "attribution_received.entity_name",
        "attribution_received.share_pct",
        "attribution_received.base_imponible_attributed",
        "attribution_received.filing_year",
    } <= set(schema.field_paths)


def test_attribution_received_identity_fields_are_required_and_grounded(
    schema: ProfileSchemaDefinition,
    legal_ids: frozenset[str],
) -> None:
    expected_refs = {"ley-35-2006:art-86", "ley-35-2006:art-87", "orden-hap-2250-2015:art-3"}

    for field_path in ("attribution_received.entity_nif", "attribution_received.entity_name"):
        field = schema.field(field_path)
        assert field.required is True
        assert field.type is ProfileFieldType.STRING
        assert set(field.legal_refs) == expected_refs
        assert expected_refs <= legal_ids


def test_attribution_received_share_pct_is_decimal_percentage(
    schema: ProfileSchemaDefinition,
    legal_ids: frozenset[str],
) -> None:
    field = schema.field("attribution_received.share_pct")

    assert field.type is ProfileFieldType.DECIMAL
    assert field.minimum == Decimal("0")
    assert field.maximum == Decimal("100")
    expected_refs = {"ley-35-2006:art-87", "ley-35-2006:art-89", "orden-hap-2250-2015:art-3"}
    assert set(field.legal_refs) == expected_refs
    assert expected_refs <= legal_ids


def test_attribution_received_base_is_explicit_money_amount(
    schema: ProfileSchemaDefinition,
    legal_ids: frozenset[str],
) -> None:
    field = schema.field("attribution_received.base_imponible_attributed")

    assert field.type is ProfileFieldType.MONEY
    assert field.required is True
    # The received base must be transcribed from the entity's Modelo 184 output,
    # never derived from share_pct without an independently declared entity total.
    assert "Debe consignarse expresamente" in field.description
    assert "no se deduce únicamente del porcentaje de participación" in field.description
    expected_refs = {
        "ley-35-2006:art-87",
        "ley-35-2006:art-88",
        "ley-35-2006:art-89",
        "orden-hap-2250-2015:art-3",
    }
    assert set(field.legal_refs) == expected_refs
    assert expected_refs <= legal_ids


def test_attribution_received_filing_year_is_required_integer_ejercicio(
    schema: ProfileSchemaDefinition,
    legal_ids: frozenset[str],
) -> None:
    field = schema.field("attribution_received.filing_year")

    assert field.type is ProfileFieldType.INTEGER
    assert field.required is True
    expected_refs = {"ley-35-2006:art-86", "ley-35-2006:art-89"}
    assert set(field.legal_refs) == expected_refs
    assert expected_refs <= legal_ids
