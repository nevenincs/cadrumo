"""Which country fields offer which codes, read through the schema and the overview."""

from __future__ import annotations

import tomllib
from uuid import UUID

import pytest
from pydantic import ValidationError

from ....core.resources.bundled_data import bundled_path
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.renta_codes_catalogue import ue_eea_country_codes
from ....domain.iva.establishment import catalogued_country_codes
from ....domain.user_profile.schema import ProfileFieldCodeList, ProfileFieldDefinition
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from ..overview import build_profile_overview

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = UUID("41414141-4141-4141-8141-414141414141")
_EXPECTED = {
    "taxpayer_type.country_of_fiscal_residence": "countries",
    "attribution_entity_socios.country_of_residence": "countries",
    "m200_establecimiento_permanente.pais_residencia_fiscal": "countries",
    "renta_spouse.eu_eea_country": "eu_eea_countries",
}


def test_the_schema_source_declares_a_code_list_on_exactly_these_fields() -> None:
    with bundled_path("registry", "cadrumo", "user_profile", "schema.toml").open("rb") as handle:
        schema = tomllib.load(handle)

    declared = {
        f"{section['key']}.{field['key']}": field["code_list"]
        for section in schema["sections"]
        for field in section.get("fields", ())
        if "code_list" in field
    }

    assert declared == _EXPECTED


def _definition(**over: object) -> ProfileFieldDefinition:
    values: dict[str, object] = {
        "key": "country",
        "type": "string",
        "sensitivity": "identity",
        "description": "A country.",
    }
    return ProfileFieldDefinition.model_validate(values | over)


def test_a_code_list_belongs_to_a_text_field_and_is_one_the_schema_knows() -> None:
    assert _definition(code_list="countries").code_list is ProfileFieldCodeList.COUNTRIES
    assert _definition().code_list is None
    with pytest.raises(ValidationError):
        _definition(code_list="provinces")
    with pytest.raises(ValidationError):
        _definition(type="integer", code_list="countries")


def test_the_eu_eea_list_is_the_membership_of_the_states_it_names() -> None:
    with bundled_indexed_authority().operation() as operation:
        members = ue_eea_country_codes(authority=operation)
        known = catalogued_country_codes(operation=operation)

    assert {"DE", "ES", "NO", "IS", "LI"} <= members
    assert not {"US", "CH", "GB", "ZZ"} & members
    assert {"ES", "US", "CH", "GB"} <= known


def test_the_overview_offers_each_list_and_keeps_a_stored_code_outside_it() -> None:
    lists = {
        ProfileFieldCodeList.COUNTRIES: ("DE", "ES"),
        ProfileFieldCodeList.EU_EEA_COUNTRIES: ("DE",),
    }
    with bundled_indexed_authority().operation() as authority:
        record = create_user_profile_record(
            context=authority.profile_create_context(),
            profile_id=str(_PROFILE_ID),
            setup_state=ProfileSetupState.INCOMPLETE,
            facts=(UserProfileFact(path="taxpayer_type.country_of_fiscal_residence", value="AQ"),),
        )
        overview = build_profile_overview(record, schema=authority.profile_schema(), code_lists=lists)
        unlisted = build_profile_overview(record, schema=authority.profile_schema())
    fields = {field.path: field for section in overview.sections for field in section.fields}
    plain = {field.path: field for section in unlisted.sections for field in section.fields}

    assert fields["taxpayer_type.country_of_fiscal_residence"].country_options == ("DE", "ES")
    assert fields["taxpayer_type.country_of_fiscal_residence"].value == "AQ"
    assert fields["renta_spouse.eu_eea_country"].country_options == ("DE",)
    # A list is an offer, never the closed answer set a surface would refuse from.
    assert fields["renta_spouse.eu_eea_country"].choices == ()
    assert fields["renta_spouse.eu_eea_country"].field_type.value == "string"
    assert plain["taxpayer_type.country_of_fiscal_residence"].country_options == ()
    assert {path for path, field in fields.items() if field.country_options} == set(_EXPECTED)
