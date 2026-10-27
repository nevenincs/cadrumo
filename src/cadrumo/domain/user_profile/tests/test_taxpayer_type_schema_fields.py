"""Shape + legal-grounding tests for the three-axis taxpayer schema fields.

The profile schema gained a structured taxpayer model: an entity-type
axis, an IRPF income-category set, an IRPF estimation-regime enum, the
REAGP IVA regime, and the SII / REDEME special-enrolment flags. Every
field that drives a downstream regulated calculation must declare
``legal_refs`` pointing at a primary BOE source.
"""

from __future__ import annotations

import pytest

from ..schema import ProfileSchemaDefinition
from ._schema_loader_fixtures import legal_ids_fixture, module_scoped_schema

__all__ = ["legal_ids_fixture", "module_scoped_schema"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]


def test_entity_type_enum_carries_the_three_branches(
    schema: ProfileSchemaDefinition,
    legal_ids: frozenset[str],
) -> None:
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
    assert expected_refs <= legal_ids


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
    legal_ids: frozenset[str],
) -> None:
    field = schema.field("taxpayer_type.irpf_income_categories")
    assert field.type.value == "string"
    assert field.schedule_predicates
    expected_refs = {
        "ley-35-2006:art-17",
        "ley-35-2006:art-22",
        "ley-35-2006:art-25",
        "ley-35-2006:art-27",
        "ley-35-2006:art-33",
    }
    assert set(field.legal_refs) == expected_refs
    assert expected_refs <= legal_ids


def test_irpf_estimation_regime_enum_covers_directa_and_objetiva(
    schema: ProfileSchemaDefinition,
    legal_ids: frozenset[str],
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
    assert expected_refs <= legal_ids


def test_art109_activity_income_coverage_is_the_schedule_predicate(
    schema: ProfileSchemaDefinition,
    legal_ids: frozenset[str],
) -> None:
    field = schema.field("irpf.art109_activity_income_withholding_ge_70pct")
    assert field.type.value == "boolean"
    assert field.model_selectors == ("art109_activity_income_withholding_ge_70pct",)
    assert field.schedule_predicates == ("art109_activity_income_withholding_ge_70pct",)
    assert field.legal_refs == ("rd-439-2007:art-109",)
    assert "activity-start" in field.description
    assert "professional, agricultural, livestock, or forestry" in field.description
    assert set(field.legal_refs) <= legal_ids


def test_objective_estimation_threshold_refs_resolve_against_catalogue(
    schema: ProfileSchemaDefinition,
    legal_ids: frozenset[str],
) -> None:
    """Objective-estimation exclusion threshold inputs are grounded in their legal basis."""
    expected_refs_by_field = {
        "irpf.objective_estimation_prior_year_gross_income_eur": {
            "ley-35-2006:art-31",
            "ley-35-2006:dt-32",
        },
        "irpf.objective_estimation_prior_year_invoice_gross_income_eur": {
            "ley-35-2006:art-31",
            "ley-35-2006:dt-32",
        },
        "irpf.objective_estimation_prior_year_agri_livestock_forest_gross_eur": {
            "ley-35-2006:art-31",
        },
        "irpf.objective_estimation_prior_year_purchases_eur": {
            "ley-35-2006:art-31",
            "ley-35-2006:dt-32",
        },
    }

    for field_path, expected_refs in expected_refs_by_field.items():
        refs = set(schema.field(field_path).legal_refs)
        assert refs == expected_refs
        assert refs <= legal_ids


def test_selected_irpf_and_irnr_profile_refs_resolve_against_catalogue(
    schema: ProfileSchemaDefinition,
    legal_ids: frozenset[str],
) -> None:
    """Selected taxpayer-profile refs must use canonical legal catalogue ids."""
    expected = {
        "irpf.pagadores_count": {"ley-35-2006:art-96"},
        "irpf.pagadores_secondary_income": {"ley-35-2006:art-96"},
        "irpf.pagadores_total_work_income": {"ley-35-2006:art-96"},
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
    legal_ids: frozenset[str],
) -> None:
    """Selected corporate-profile refs must use canonical legal catalogue ids."""
    expected = {
        "taxpayer_type.legal_entity_form": {"ley-27-2014:art-29", "ley-44-2015:art-1"},
        "taxpayer_type.incn_prior_12_months": {"ley-27-2014:art-40-3"},
        "taxpayer_type.new_entity_first_two_profit_periods": {"ley-27-2014:art-29"},
        "taxpayer_type.tributacion_estado_porcentaje": {"ley-12-2002:art-15", "ley-28-1990:art-19"},
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
    group_member = schema.field("iva.group_member_enrolled")
    assert group_member.type.value == "boolean"
    assert group_member.legal_refs, "iva.group_member_enrolled must declare legal_refs"
    assert group_member.schedule_predicates

    group_dominant = schema.field("iva.group_dominant_entity_enrolled")
    assert group_dominant.type.value == "boolean"
    assert group_dominant.legal_refs, "iva.group_dominant_entity_enrolled must declare legal_refs"
    assert group_dominant.schedule_predicates

    sii = schema.field("iva.sii_enrolled")
    assert sii.type.value == "boolean"
    assert sii.legal_refs, "iva.sii_enrolled must declare legal_refs"
    assert sii.schedule_predicates == ()

    redeme = schema.field("iva.redeme_enrolled")
    assert redeme.type.value == "boolean"
    assert redeme.legal_refs, "iva.redeme_enrolled must declare legal_refs"
    assert redeme.schedule_predicates


def test_iva_profile_selector_legal_refs_resolve_against_catalogue(
    schema: ProfileSchemaDefinition,
    legal_ids: frozenset[str],
) -> None:
    """Selected IVA profile selectors must carry canonical LegalReference ids."""
    expected = {
        "iva.regime": {
            "ley-37-1992:art-122",
            "ley-37-1992:art-148",
            "ley-37-1992:art-164",
        },
        "censo.large_company": {"ley-37-1992:art-121", "rd-1624-1992:art-71"},
        "censo.public_administration_budget_gt_6000000": {"orden-eha-586-2011:art-1", "rd-439-2007:art-108"},
        "iva.sii_enrolled": {"rd-596-2016", "rd-1624-1992:art-71"},
        "iva.redeme_enrolled": {"rd-1624-1992:art-30"},
        "iva.group_member_enrolled": {"orden-eha-3434-2007:art-1", "rd-1624-1992:art-71"},
        "iva.group_dominant_entity_enrolled": {"orden-eha-3434-2007:art-2", "rd-1624-1992:art-71"},
        "iva.autoconsumo_promotor_base": {"ley-37-1992:art-9", "ley-37-1992:art-79"},
    }

    for field_path, expected_refs in expected.items():
        refs = set(schema.field(field_path).legal_refs)
        assert refs == expected_refs
        assert refs <= legal_ids


def test_objective_estimation_boolean_is_not_retained(
    schema: ProfileSchemaDefinition,
) -> None:
    """The profile schema exposes only the structured estimation-regime axis."""

    assert "irpf.uses_objective_estimation" not in schema.field_paths
    field = schema.field("irpf.estimation_regime")
    assert "irpf.estimation_regime" in field.schedule_predicates
