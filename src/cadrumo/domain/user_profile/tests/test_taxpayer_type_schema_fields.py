"""Shape + legal-grounding tests for the three-axis taxpayer schema fields.

The profile schema gained a structured taxpayer model: an entity-type
axis, an IRPF income-category set, an IRPF estimation-regime enum, the
REAGP IVA regime, and the SII / REDEME special-enrolment flags. Every
field that drives a downstream regulated calculation must declare
``legal_refs`` pointing at a primary BOE source.
"""

from __future__ import annotations

import pytest

from ....core.resources._boundary import bundled_path
from ..schema import ProfileSchemaDefinition
from ._schema_loader_fixtures import legal_ids_fixture, module_scoped_schema

__all__ = ["legal_ids_fixture", "module_scoped_schema"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


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
    old_field = schema.field("irpf.professional_income_withholding_ge_70pct")
    assert old_field.type.value == "boolean"
    assert old_field.model_selectors == ("professional_income_withholding_ge_70pct",)
    assert old_field.schedule_predicates == ()

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


def test_objective_estimation_modulos_profile_facts_are_stable_annual_inputs(
    schema: ProfileSchemaDefinition,
    legal_ids: frozenset[str],
) -> None:
    """Módulos profile facts store operator-declared annual inputs, not coefficients."""
    epigraph = schema.field("irpf.objective_estimation_modulos_iae_epigraph")
    assert epigraph.type.value == "string"
    assert epigraph.model_selectors == ("irpf.objective_estimation_modulos_iae_epigraph",)

    expected_modulos_paths = {
        "irpf.objective_estimation_modulos_iae_epigraph",
        *(f"irpf.objective_estimation_modulos_module_{slot}_units" for slot in range(1, 8)),
    }
    assert {path for path in schema.field_paths if path.startswith("irpf.objective_estimation_modulos_")} == (
        expected_modulos_paths
    )

    expected_refs = {"ley-35-2006:art-31", "orden-hac-1425-2025:art-4"}
    assert set(epigraph.legal_refs) == expected_refs
    assert expected_refs <= legal_ids

    for slot in range(1, 8):
        field = schema.field(f"irpf.objective_estimation_modulos_module_{slot}_units")
        assert field.type.value == "decimal"
        assert field.model_selectors == (f"irpf.objective_estimation_modulos_module_{slot}_units",)
        assert field.required is False
        assert set(field.legal_refs) == expected_refs
        assert set(field.legal_refs) <= legal_ids


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
        "taxpayer_type.ley_49_2002_special_regime_option_declared": {"ley-49-2002:art-14"},
        "taxpayer_type.ley_49_2002_special_regime_option_date": {"ley-49-2002:art-14"},
        "taxpayer_type.ley_49_2002_special_regime_renunciation_declared": {"ley-49-2002:art-14"},
        "taxpayer_type.ley_49_2002_special_regime_renunciation_date": {"ley-49-2002:art-14"},
        "taxpayer_type.tributacion_estado_porcentaje": {"ley-12-2002:art-15", "ley-28-1990:art-19"},
        "taxpayer_type.sal_socios_trabajadores_count": {"ley-44-2015:art-1", "ley-44-2015:art-2"},
        "taxpayer_type.sal_reserva_especial_dotada": {"ley-44-2015:art-14"},
        "taxpayer_type.sal_capital_social": {"ley-44-2015:art-14"},
    }

    for field_path, expected_refs in expected.items():
        refs = set(schema.field(field_path).legal_refs)
        assert refs == expected_refs
        assert refs <= legal_ids


def test_ley_49_2002_special_regime_fields_match_modelo_036_record_design(
    schema: ProfileSchemaDefinition,
) -> None:
    """The Ley 49/2002 profile axis mirrors the current Modelo 036 censo fields."""
    expected = {
        "taxpayer_type.ley_49_2002_special_regime_option_declared": (
            "boolean",
            "taxpayer.ley_49_2002_special_regime_option_declared",
            "casilla 651",
        ),
        "taxpayer_type.ley_49_2002_special_regime_option_date": (
            "date",
            "taxpayer.ley_49_2002_special_regime_option_date",
            "casilla 653",
        ),
        "taxpayer_type.ley_49_2002_special_regime_renunciation_declared": (
            "boolean",
            "taxpayer.ley_49_2002_special_regime_renunciation_declared",
            "casilla 652",
        ),
        "taxpayer_type.ley_49_2002_special_regime_renunciation_date": (
            "date",
            "taxpayer.ley_49_2002_special_regime_renunciation_date",
            "casilla 654",
        ),
    }

    for field_path, (field_type, selector, description_anchor) in expected.items():
        field = schema.field(field_path)
        assert field.type.value == field_type
        assert field.model_selectors == (selector,)
        assert field.legal_refs == ("ley-49-2002:art-14",)
        assert description_anchor in field.description

    record_design = bundled_path(
        "corpus",
        "aeat_official",
        "disenos_registro",
        "modelo_036",
        "files",
        "01-036-diseno-de-registro-del-modelo-m036-03-02-2025-y-siguientes-124-kb-xlsx.xlsx.extracted.md",
    ).read_text(encoding="utf-8")
    assert "Opción/renuncia por el Regimen fiscal especial del Título II de la Ley 49/2002" in record_design
    assert "Ejerce la opción por el Régimen fiscal especial del Tit. II Ley 49/2002" in record_design
    assert "Ejercitada la opción por el Régimen fiscal especial del Tit. II Ley 49/2002, renuncia" in record_design
    assert "[651]" in record_design
    assert "[653]" in record_design
    assert "[652]" in record_design
    assert "[654]" in record_design


def test_sal_reserva_profile_description_uses_twice_capital_threshold(
    schema: ProfileSchemaDefinition,
) -> None:
    """The registry schema must not preserve obsolete SAL cap prose."""
    descriptions = " ".join(
        schema.field(field_path).description
        for field_path in (
            "taxpayer_type.sal_reserva_especial_dotada",
            "taxpayer_type.sal_capital_social",
        )
    ).casefold()

    assert "50 percent" not in descriptions
    assert "0.50" not in descriptions
    assert "does not exceed twice" not in descriptions
    assert "reaches at least 2 * capital_social." not in descriptions
    assert "twice" in descriptions
    assert "2 * capital_social + 0.01" in descriptions
    assert "first euro cent above twice capital social" in descriptions
    assert "ley 44/2015 art. 14" in descriptions


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
