"""Hard-cutover tests for profile fields removed from the schema.

A removed field is not interpreted. Facts stored under its path are refused as
unknown rather than read, and the one way to drop them stays open: clearing a
fact is admissible at any path, declared or not.
"""

from __future__ import annotations

import pytest

from ....domain.calculations.registry.tests.published_authority import published_profile_schema
from ....domain.deadlines.setup_answer_projection import setup_answer_fields
from ....domain.user_profile.values import UserProfileFact, section_field_key
from ..validation import ProfileValidationService

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_PROFILE_ID = "11111111-1111-4111-8111-111111111111"

_RETIRED_SECTIONS = ("usage_ratios", "properties", "attribution_entity")

_RETIRED_FACTS = (
    UserProfileFact(path="identity.notes", value="note"),
    UserProfileFact(path="contact.fiscal_address_is_habitual_vivienda", value=True),
    UserProfileFact(path="censo.establecimiento_type", value="propio"),
    UserProfileFact(path="censo.elected_withholding_pct", value="15"),
    UserProfileFact(path="activities.0.cnae", value="6201"),
    UserProfileFact(path="attribution_entity_socios.0.role", value="socio"),
    UserProfileFact(path="attribution_entity.legal_form", value="comunidad_bienes"),
    UserProfileFact(path="properties.0.cadastral_reference", value="9872023VH5797S0001WX"),
    UserProfileFact(path="properties.0.use_type", value="habitual"),
    UserProfileFact(path="usage_ratios.0.category_id", value="office"),
    UserProfileFact(path="usage_ratios.0.business_ratio", value="0.3"),
    UserProfileFact(path="taxpayer_type.sal_socios_trabajadores_count", value=3),
    UserProfileFact(path="taxpayer_type.sal_reserva_especial_dotada", value="0"),
    UserProfileFact(path="taxpayer_type.sal_capital_social", value="5000"),
    UserProfileFact(path="taxpayer_type.ley_49_2002_special_regime_option_declared", value=True),
    UserProfileFact(path="taxpayer_type.ley_49_2002_special_regime_option_date", value="2024-02-03"),
    UserProfileFact(path="taxpayer_type.ley_49_2002_special_regime_renunciation_declared", value=False),
    UserProfileFact(path="taxpayer_type.ley_49_2002_special_regime_renunciation_date", value="2026-05-11"),
    UserProfileFact(path="irpf.professional_income_withholding_ge_70pct", value=True),
    UserProfileFact(path="irpf.objective_estimation_modulos_iae_epigraph", value="972.1"),
    *(
        UserProfileFact(path=f"irpf.objective_estimation_modulos_module_{slot}_units", value="1")
        for slot in range(1, 8)
    ),
)


def test_removed_fields_and_sections_are_absent_from_the_schema() -> None:
    schema = published_profile_schema()
    retired_paths = {section_field_key(fact.path) for fact in _RETIRED_FACTS}

    assert retired_paths.isdisjoint(schema.field_paths)
    assert {section.key for section in schema.sections}.isdisjoint(_RETIRED_SECTIONS)
    assert schema.path_for_model_selector("address.is_habitual_vivienda") is None


def test_no_setup_answer_is_read_from_a_removed_path() -> None:
    retired_paths = {section_field_key(fact.path) for fact in _RETIRED_FACTS}
    answer_paths = {section_field_key(spec.path) for spec in setup_answer_fields().values()}

    assert answer_paths.isdisjoint(retired_paths)


def test_a_stored_fact_at_a_removed_path_is_refused_as_unknown() -> None:
    report = ProfileValidationService(schema=published_profile_schema()).validate_facts(_PROFILE_ID, _RETIRED_FACTS)

    unknown_paths = {issue.path for issue in report.issues if issue.code == "unknown_field"}

    assert unknown_paths == {fact.path for fact in _RETIRED_FACTS}


def test_clearing_a_stored_fact_at_a_removed_path_stays_admissible() -> None:
    cleared = tuple(UserProfileFact(path=fact.path, value=None) for fact in _RETIRED_FACTS)

    report = ProfileValidationService(schema=published_profile_schema()).validate_facts(_PROFILE_ID, cleared)

    assert not [issue for issue in report.issues if issue.code == "unknown_field"]
