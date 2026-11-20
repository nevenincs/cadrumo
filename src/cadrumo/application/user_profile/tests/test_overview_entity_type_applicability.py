"""The overview offers a declaration only to the taxpayer entity types it concerns.

Driven through the published schema and the real projection: a natural person
is not offered the Impuesto sobre Sociedades declarations (Modelo 200 pages 2
and 2 bis, the Modelo 202 additional data), an entity is, and a profile that
does not state its type is offered neither kind and is told why.
"""

from __future__ import annotations

import pytest

from ....domain.calculations.registry.tests.published_authority import (
    leased_profile_create_context,
    published_profile_schema,
)
from ....domain.user_profile.values import (
    ProfileSetupState,
    UserProfileFact,
    UserProfileRecord,
    create_user_profile_record,
    section_field_key,
)
from ..overview import ENTITY_TYPE_UNSTATED_NOTICE_CODE, ProfileOverview, build_profile_overview

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_PROFILE_ID = "11111111-1111-4111-8111-111111111113"
_ENTITY_TYPE = "taxpayer_type.entity_type"
_BOARD_SECRETARY = "m200_secretario_consejo"
_SOCIMI = "taxpayer_type.regimen_socimi"
_ATTRIBUTION_SOCIOS = "attribution_entity_socios"


def _overview(*facts: UserProfileFact) -> ProfileOverview:
    record: UserProfileRecord = create_user_profile_record(
        profile_id=_PROFILE_ID,
        setup_state=ProfileSetupState.INCOMPLETE,
        facts=facts,
        context=leased_profile_create_context(),
    )
    return build_profile_overview(record, schema=published_profile_schema())


def _sections(overview: ProfileOverview) -> set[str]:
    return {section.key for section in overview.sections}


def _fields(overview: ProfileOverview) -> set[str]:
    return {section_field_key(view.path) for section in overview.sections for view in section.fields}


def _notice_codes(overview: ProfileOverview) -> set[str]:
    return {notice.code for notice in overview.notices}


def test_the_schema_restricts_the_entity_declarations_this_relies_on() -> None:
    """The registry declares what concerns an entity; the projection reads it."""
    schema = published_profile_schema()
    assert schema.entity_types_of(_BOARD_SECRETARY, "nif") == {"legal_entity"}
    assert schema.entity_types_of("taxpayer_type", "regimen_socimi") == {"legal_entity"}
    assert schema.entity_types_of(_ATTRIBUTION_SOCIOS, "nif") == {"attribution_entity"}
    assert schema.entity_types_of("identity", "tax_id") == frozenset()


def test_a_natural_person_is_offered_no_entity_declaration() -> None:
    overview = _overview(UserProfileFact(path=_ENTITY_TYPE, value="natural_person"))

    assert _BOARD_SECRETARY not in _sections(overview)
    assert _ATTRIBUTION_SOCIOS not in _sections(overview)
    assert not any(key.startswith("m200_") for key in _sections(overview))
    assert _SOCIMI not in _fields(overview)
    assert {"identity", "taxpayer_type"} <= _sections(overview)
    assert _ENTITY_TYPE in _fields(overview)
    assert ENTITY_TYPE_UNSTATED_NOTICE_CODE not in _notice_codes(overview)
    assert not [path for path in overview.missing_required if section_field_key(path).startswith("m200_")]


def test_a_legal_entity_is_offered_its_declarations_and_not_an_attribution_entitys() -> None:
    overview = _overview(UserProfileFact(path=_ENTITY_TYPE, value="legal_entity"))

    assert _BOARD_SECRETARY in _sections(overview)
    assert _SOCIMI in _fields(overview)
    assert _ATTRIBUTION_SOCIOS not in _sections(overview)
    assert ENTITY_TYPE_UNSTATED_NOTICE_CODE not in _notice_codes(overview)


def test_an_unstated_type_offers_no_restricted_declaration_and_asks_for_the_type() -> None:
    overview = _overview()

    assert _BOARD_SECRETARY not in _sections(overview)
    assert _SOCIMI not in _fields(overview)
    assert _ENTITY_TYPE in _fields(overview)
    assert ENTITY_TYPE_UNSTATED_NOTICE_CODE in _notice_codes(overview)


def test_a_stored_value_stays_shown_whatever_it_is_declared_for() -> None:
    overview = _overview(
        UserProfileFact(path=_ENTITY_TYPE, value="natural_person"),
        UserProfileFact(path=_SOCIMI, value=True),
    )

    assert _SOCIMI in _fields(overview)
