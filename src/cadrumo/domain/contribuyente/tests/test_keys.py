"""Unit tests for the profile-key registry."""

from __future__ import annotations

import pytest

from ....core.errors import ERROR_REGISTRY, build_error_envelope
from ....core.i18n import Translatable as tr
from .. import (
    PROFILE_KEYS,
    ProfileKey,
    ProfileKeyRequirement,
    get_profile_key,
    optional_profile_keys,
    required_profile_keys,
)
from .._keys import register_profile_keys
from ..errors import ProfileKeysRegistrationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_registry_is_non_empty_and_unique() -> None:
    assert len(PROFILE_KEYS) >= 1
    keys = [entry.key for entry in PROFILE_KEYS]
    assert len(keys) == len(set(keys)), "every profile key must be unique"


def test_required_and_optional_partition_covers_registry() -> None:
    required = required_profile_keys()
    optional = optional_profile_keys()
    assert {entry.key for entry in required + optional} == {entry.key for entry in PROFILE_KEYS}
    assert all(entry.requirement is ProfileKeyRequirement.REQUIRED for entry in required)
    assert all(entry.requirement is ProfileKeyRequirement.OPTIONAL for entry in optional)


def test_get_profile_key_returns_canonical_record() -> None:
    entry = get_profile_key("identity.tax_id")
    assert isinstance(entry, ProfileKey)
    assert entry.key == "identity.tax_id"
    assert entry.requirement is ProfileKeyRequirement.REQUIRED
    assert entry.description
    assert entry.description


def test_get_profile_key_raises_keyerror_for_unknown_key() -> None:
    with pytest.raises(KeyError, match=r"unknown profile key"):
        get_profile_key("not.a.profile.key")


def test_every_entry_carries_authoritative_spanish_description() -> None:
    for entry in PROFILE_KEYS:
        assert entry.description.strip(), f"{entry.key}: missing description.es"


def test_profile_key_rejects_blank_keys() -> None:
    # Empty key is rejected by the pydantic Field(min_length=1)
    # constraint BEFORE the custom _validate_key validator runs.
    with pytest.raises(ValueError, match=r"at least 1 character"):
        ProfileKey(
            key="",
            requirement=ProfileKeyRequirement.OPTIONAL,
            description=tr("profile.keys.description"),
        )


def test_profile_key_rejects_padded_keys() -> None:
    with pytest.raises(ValueError, match=r"key must not be padded with whitespace"):
        ProfileKey(
            key=" tax.id ",
            requirement=ProfileKeyRequirement.OPTIONAL,
            description=tr("profile.keys.description"),
        )


def test_profile_key_rejects_descriptions_without_authoritative_spanish() -> None:
    with pytest.raises(ValueError, match=r"description must use a profile translation key"):
        ProfileKey(
            key="x",
            requirement=ProfileKeyRequirement.OPTIONAL,
            description=tr("translation"),
        )


def test_profile_key_conditional_requirement_fields_must_be_paired() -> None:
    with pytest.raises(ValueError, match=r"required_when_key and required_when_value must be set together"):
        ProfileKey(
            key="spouse.tax.id",
            requirement=ProfileKeyRequirement.OPTIONAL,
            description=tr("profile.keys.description"),
            required_when_key="declaration.type",
        )


def test_spouse_tax_id_is_conditionally_required_for_joint_taxation() -> None:
    """A joint declaration is invalid without the spouse NIF.

    ``renta_spouse.tax_id`` is the one spouse key the domain genuinely
    requires when ``taxation_type == "2"`` (``SetupAnswers`` enforces
    the same invariant). The conditional requirement compiles to the
    ``required_when_*`` pair so ``validate_profile_values`` promotes the
    key to required only while a joint declaration is declared."""

    entry = get_profile_key("renta_spouse.tax_id")
    assert entry.requirement is ProfileKeyRequirement.OPTIONAL
    assert entry.required_when_key == "renta_filing.declaration_type"
    assert entry.required_when_value == "2"


def test_optional_spouse_keys_carry_no_conditional_requirement() -> None:
    """The remaining spouse identity keys are optional even for a joint
    declaration — the domain validator requires only the spouse NIF.

    A ``visible_when`` gate controls *whether the question is asked*,
    not whether the key is required: a gated but ``required=False``
    question carries no ``required_when_*`` pair, so it is never
    promoted to required when its gate matches."""

    for key in (
        "renta_spouse.name",
        "renta_spouse.surnames",
        "renta_spouse.birth_date",
        "renta_spouse.sex",
    ):
        entry = get_profile_key(key)
        assert entry.requirement is ProfileKeyRequirement.OPTIONAL
        assert entry.required_when_key is None
        assert entry.required_when_value is None


def test_profile_keys_registration_error_is_in_error_registry() -> None:
    """ProfileKeysRegistrationError must be present in ERROR_REGISTRY."""
    assert "INTERNAL_PROFILE_KEYS_REGISTRATION" in ERROR_REGISTRY


def test_profile_keys_registration_error_round_trips_through_build_error_envelope() -> None:
    """build_error_envelope must produce a well-formed envelope for ProfileKeysRegistrationError."""
    error = ProfileKeysRegistrationError()
    envelope = build_error_envelope(error)
    assert envelope.code == "INTERNAL_PROFILE_KEYS_REGISTRATION"
    assert envelope.category == "INTERNAL"
    assert envelope.message
    assert not envelope.retryable


def test_double_registration_with_conflicting_tuple_raises_profile_keys_registration_error() -> None:
    """register_profile_keys must raise ProfileKeysRegistrationError when a
    second conflicting tuple is supplied.

    The cache is already populated from the PROFILE_KEYS import above.
    Supplying an empty tuple is guaranteed to differ from the real registry.
    """
    assert PROFILE_KEYS, "pre-condition: registry must be non-empty"
    with pytest.raises(ProfileKeysRegistrationError):
        register_profile_keys(())  # empty tuple != real registry tuple


def test_renta_family_profile_keys_cover_official_scalar_family_fields() -> None:
    expected = {
        "renta_taxpayer.disability_grade",
        "renta_taxpayer.death_date",
        "renta_spouse.disability_grade",
        "renta_spouse.non_resident_irpf",
        "renta_spouse.eu_eea_resident",
        "renta_spouse.eu_eea_country",
        "renta_family.descendants_eu_eea_deduction",
        "renta_family.minor_children_in_unit",
    }

    assert expected.issubset({entry.key for entry in optional_profile_keys()})
    # `spouse.eu_eea_resident` is an optional boolean — no validator
    # requires it — so it carries no conditional-requirement pair.
    assert get_profile_key("renta_spouse.eu_eea_resident").required_when_key is None
    # The residence country IS required once the spouse is declared an
    # EU/EEA resident (SetupAnswers enforces the same invariant).
    assert get_profile_key("renta_spouse.eu_eea_country").required_when_key == "renta_spouse.eu_eea_resident"
    assert get_profile_key("renta_spouse.eu_eea_country").required_when_value == "true"
