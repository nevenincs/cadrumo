"""Unit tests for the profile-key registry."""

from __future__ import annotations

import pytest

from ...core.i18n import Translatable as tr
from . import (
    PROFILE_KEYS,
    ProfileKey,
    ProfileKeyRequirement,
    get_profile_key,
    optional_profile_keys,
    required_profile_keys,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


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


def test_spouse_profile_keys_are_conditionally_required_for_joint_taxation() -> None:
    for key in (
        "renta_spouse.tax_id",
        "renta_spouse.name",
        "renta_spouse.surnames",
        "renta_spouse.birth_date",
        "renta_spouse.sex",
    ):
        entry = get_profile_key(key)
        assert entry.requirement is ProfileKeyRequirement.OPTIONAL
        assert entry.required_when_key == "filing_export.declaration_type"
        assert entry.required_when_value == "2"


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
    assert get_profile_key("renta_spouse.eu_eea_resident").required_when_key == "renta_spouse.non_resident_irpf"
    assert get_profile_key("renta_spouse.eu_eea_resident").required_when_value == "true"
    assert get_profile_key("renta_spouse.eu_eea_country").required_when_key == "renta_spouse.eu_eea_resident"
    assert get_profile_key("renta_spouse.eu_eea_country").required_when_value == "true"
