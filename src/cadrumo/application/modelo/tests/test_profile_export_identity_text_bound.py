"""A profile text past a producer's bound refuses as the profile field to shorten."""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter

from cadrumo.application.filing.producer_snapshot import DeclarationContactFacts, TaxpayerIdentityFacts
from cadrumo.application.user_profile.preflight import build_profile_preflight_requirement
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.user_profile.errors import ProfileSchemaValidationError
from cadrumo.domain.user_profile.schema import ProfileValueRefusalKind, profile_value_refusal

from ..profile_export_binding import _identity_from_profile_facts

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PERSON = {"identity.tax_id": "12345678Z", "taxpayer_type.entity_type": "natural_person"}


def _field(operation: PinnedAuthorityOperation, path: str):
    section_key, field_key = path.split(".")
    schema = operation.profile_schema()
    [section] = [section for section in schema.sections if section.key == section_key]
    [field] = [field for field in section.fields if field.key == field_key]
    return field


@pytest.mark.parametrize(
    ("facts", "named"),
    [
        ({"identity.name": "Ana", "identity.surnames": "S" * 300}, "identity.surnames"),
        ({"identity.name": "N" * 300, "identity.surnames": "Gil"}, "identity.name"),
        ({"identity.name": "N" * 128, "identity.surnames": "S" * 128}, "identity.surnames"),
    ],
    ids=["surnames", "given name", "each fits and the composed name does not"],
)
def test_the_refusal_names_the_field_and_never_the_value(
    operation: PinnedAuthorityOperation, facts: dict[str, str], named: str
) -> None:
    schema = operation.profile_schema()

    with pytest.raises(ProfileSchemaValidationError) as refused:
        _identity_from_profile_facts({**_PERSON, **facts}, schema=schema)

    assert refused.value.translated_message == "application.user_profile.errors.profile_text_too_long"
    assert refused.value.context is not None
    assert refused.value.context["field"] == build_profile_preflight_requirement(named, schema=schema).label
    assert refused.value.context["limit"] == 256
    assert not any(value in str(refused.value.context) for value in facts.values())


def test_a_name_at_the_bound_is_carried(operation: PinnedAuthorityOperation) -> None:
    identity = _identity_from_profile_facts(
        {**_PERSON, "identity.name": "N" * 127, "identity.surnames": "S" * 128},
        schema=operation.profile_schema(),
    )
    assert identity is not None
    assert identity[1].full_name is not None
    assert len(identity[1].full_name) == 256


@pytest.mark.parametrize(
    ("path", "record", "attribute"),
    [
        ("identity.name", TaxpayerIdentityFacts, "given_name"),
        ("identity.surnames", TaxpayerIdentityFacts, "surnames"),
        ("identity.legal_name", TaxpayerIdentityFacts, "legal_name"),
        ("contact.contact_person_name", DeclarationContactFacts, "full_name"),
        ("contact.contact_person_phone", DeclarationContactFacts, "phone"),
    ],
)
def test_the_declared_bound_is_what_the_producer_record_holds(
    operation: PinnedAuthorityOperation, path: str, record: type, attribute: str
) -> None:
    limit = _field(operation, path).max_length
    assert limit is not None
    adapter = TypeAdapter(record.model_fields[attribute].rebuild_annotation())
    assert adapter.validate_python("A" * limit) == "A" * limit
    with pytest.raises(ValueError, match="at most"):
        adapter.validate_python("A" * (limit + 1))


def test_the_write_door_refuses_past_the_bound_without_quoting_the_value(operation: PinnedAuthorityOperation) -> None:
    field = _field(operation, "identity.surnames")
    assert field.max_length is not None
    assert profile_value_refusal(field, "S" * field.max_length) is None

    refusal = profile_value_refusal(field, "S" * (field.max_length + 1))

    assert refusal is not None
    assert refusal.kind is ProfileValueRefusalKind.TEXT_LENGTH
    assert "SS" not in refusal.message
