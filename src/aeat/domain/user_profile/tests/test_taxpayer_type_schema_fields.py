"""Shape + legal-grounding tests for the three-axis taxpayer schema fields.

The profile schema gained a structured taxpayer model: an entity-type
axis, an IRPF income-category set, an IRPF estimation-regime enum, the
REAGP IVA regime, and the SII / REDEME special-enrolment flags. Every
field that drives a downstream regulated calculation must declare
``legal_refs`` pointing at a primary BOE source.
"""

from __future__ import annotations

import pytest

from ....core.resources import bundled_path
from ...calculations.registry import load_registry_tree
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
    expected_refs = {
        "ley-35-2006:art-8",
        "ley-27-2014:art-7",
        "ley-35-2006:art-86",
        "ley-35-2006:art-87",
    }
    assert set(field.legal_refs) == expected_refs
    _, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    assert expected_refs <= set(catalogues.legal)


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
    expected_refs = {
        "ley-35-2006:art-28",
        "ley-35-2006:art-30",
        "ley-35-2006:art-31",
        "rd-439-2007:art-30",
        "rd-439-2007:art-31",
    }
    assert set(field.legal_refs) == expected_refs
    _, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    assert expected_refs <= set(catalogues.legal)


def test_objective_estimation_threshold_refs_resolve_against_catalogue(
    schema: ProfileSchemaDefinition,
) -> None:
    """Objective-estimation exclusion threshold inputs are grounded in DT 32."""
    _, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    legal_ids = set(catalogues.legal)
    expected_refs = {"ley-35-2006:dt-32"}

    for field_path in (
        "irpf.objective_estimation_prior_year_gross_income_eur",
        "irpf.objective_estimation_prior_year_invoice_gross_income_eur",
        "irpf.objective_estimation_prior_year_purchases_eur",
    ):
        refs = set(schema.field(field_path).legal_refs)
        assert refs == expected_refs
        assert refs <= legal_ids


def test_selected_irpf_and_irnr_profile_refs_resolve_against_catalogue(
    schema: ProfileSchemaDefinition,
) -> None:
    """Selected taxpayer-profile refs must use canonical legal catalogue ids."""
    _, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    legal_ids = set(catalogues.legal)
    expected = {
        "irpf.pagadores_count": {"ley-35-2006:art-96"},
        "irpf.pagadores_secondary_income": {"ley-35-2006:art-96"},
        "irpf.special_regime": {"ley-35-2006:art-93", "rd-439-2007:art-113", "rd-439-2007:art-115"},
        "irpf.special_regime_start_date": {"rd-439-2007:art-116"},
        "taxpayer_type.fiscal_residency": {"ley-35-2006:art-9", "trlirnr-rdleg-5-2004:art-2"},
        "taxpayer_type.country_of_fiscal_residence": {
            "trlirnr-rdleg-5-2004:art-2",
            "trlirnr-rdleg-5-2004:art-25.1.a",
            "trlirnr-rdleg-5-2004:art-25.1.f",
        },
        "taxpayer_type.representante_fiscal_nif": {"trlirnr-rdleg-5-2004:art-10"},
        "taxpayer_type.representante_fiscal_nombre": {"trlirnr-rdleg-5-2004:art-10"},
    }

    for field_path, expected_refs in expected.items():
        refs = set(schema.field(field_path).legal_refs)
        assert refs == expected_refs
        assert refs <= legal_ids


def test_selected_sociedades_profile_refs_resolve_against_catalogue(
    schema: ProfileSchemaDefinition,
) -> None:
    """Selected corporate-profile refs must use canonical legal catalogue ids."""
    _, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    legal_ids = set(catalogues.legal)
    expected = {
        "taxpayer_type.legal_entity_form": {"ley-27-2014:art-29", "ley-44-2015:art-1"},
        "taxpayer_type.incn_prior_12_months": {"ley-27-2014:art-40-3"},
        "taxpayer_type.new_entity_first_two_profit_periods": {"ley-27-2014:art-29"},
        "taxpayer_type.sal_socios_trabajadores_count": {"ley-44-2015:art-1", "ley-44-2015:art-2"},
        "taxpayer_type.sal_reserva_especial_dotada": {"ley-44-2015:art-14"},
        "taxpayer_type.sal_capital_social": {"ley-44-2015:art-14"},
    }

    for field_path, expected_refs in expected.items():
        refs = set(schema.field(field_path).legal_refs)
        assert refs == expected_refs
        assert refs <= legal_ids


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


def test_iva_profile_selector_legal_refs_resolve_against_catalogue(
    schema: ProfileSchemaDefinition,
) -> None:
    """Selected IVA profile selectors must carry canonical LegalReference ids."""
    _, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    legal_ids = set(catalogues.legal)
    expected = {
        "iva.regime": {
            "ley-37-1992:art-122",
            "ley-37-1992:art-148",
            "ley-37-1992:art-164",
        },
        "iva.sii_enrolled": {"rd-596-2016"},
        "iva.redeme_enrolled": {"rd-1624-1992:art-30"},
        "iva.autoconsumo_promotor_base": {"ley-37-1992:art-9", "ley-37-1992:art-79"},
    }

    for field_path, expected_refs in expected.items():
        refs = set(schema.field(field_path).legal_refs)
        assert refs == expected_refs
        assert refs <= legal_ids


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
