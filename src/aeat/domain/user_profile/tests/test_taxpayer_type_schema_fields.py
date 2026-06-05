"""Shape + legal-grounding tests for the three-axis taxpayer schema fields.

The profile schema gained a structured taxpayer model: an entity-type
axis, an IRPF income-category set, an IRPF estimation-regime enum, the
REAGP IVA regime, and the SII / REDEME special-enrolment flags. Every
field that drives a downstream regulated calculation must declare
``legal_refs`` pointing at a primary BOE source.
"""

from __future__ import annotations

import pytest

from .. import ProfileSchemaDefinition, load_user_profile_schema

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture
def schema() -> ProfileSchemaDefinition:
    return load_user_profile_schema()


def test_entity_type_enum_carries_the_three_branches(schema: ProfileSchemaDefinition) -> None:
    field = schema.field("taxpayer_type.entity_type")
    assert field.type.value == "enum"
    assert set(field.enum_values) == {
        "natural_person",
        "legal_entity",
        "attribution_entity",
    }
    assert field.legal_refs


def test_legal_entity_form_enum_covers_recognised_forms(
    schema: ProfileSchemaDefinition,
) -> None:
    field = schema.field("taxpayer_type.legal_entity_form")
    assert field.type.value == "enum"
    assert set(field.enum_values) == {
        "sl",
        "sa",
        "sal",
        "sll",
        "cooperativa",
        "sociedad_civil_mercantil",
        "sin_fines_lucrativos",
        "other",
    }


def test_irpf_income_categories_field_is_present_and_grounded(
    schema: ProfileSchemaDefinition,
) -> None:
    field = schema.field("taxpayer_type.irpf_income_categories")
    assert field.type.value == "string"
    assert field.legal_refs
    assert field.schedule_predicates


def test_irpf_estimation_regime_enum_covers_directa_and_objetiva(
    schema: ProfileSchemaDefinition,
) -> None:
    field = schema.field("irpf.estimation_regime")
    assert field.type.value == "enum"
    assert set(field.enum_values) == {
        "directa_normal",
        "directa_simplificada",
        "objetiva",
    }
    assert field.legal_refs


def test_iva_regime_enum_includes_reagp(schema: ProfileSchemaDefinition) -> None:
    field = schema.field("iva.regime")
    assert "REAGP" in field.enum_values
    # The pre-existing members are preserved.
    assert {"GENERAL", "SIMPLIFICADO", "RECARGO_EQUIVALENCIA", "EXENTO"}.issubset(set(field.enum_values))


def test_sii_and_redeme_enrolment_fields_are_present_and_grounded(
    schema: ProfileSchemaDefinition,
) -> None:
    for field_key in ("sii_enrolled", "redeme_enrolled"):
        field = schema.field(f"iva.{field_key}")
        assert field.type.value == "boolean"
        assert field.legal_refs, f"iva.{field_key} must declare legal_refs"
        assert field.schedule_predicates


def test_uses_objective_estimation_boolean_is_retained(
    schema: ProfileSchemaDefinition,
) -> None:
    """The legacy objective-estimation boolean stays alongside the enum.

    Registry schedule predicates / model selectors still test
    ``uses_objective_estimation_irpf``; the taxpayer-type schema adds the
    structured ``estimation_regime`` enum without removing the boolean
    the engine has not yet been rewired off.
    """

    field = schema.field("irpf.uses_objective_estimation")
    assert field.type.value == "boolean"
    assert "uses_objective_estimation_irpf" in field.schedule_predicates
