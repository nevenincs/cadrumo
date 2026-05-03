"""Unit tests for the profile-key registry."""

from __future__ import annotations

import pytest

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
    entry = get_profile_key("tax.id")
    assert isinstance(entry, ProfileKey)
    assert entry.key == "tax.id"
    assert entry.requirement is ProfileKeyRequirement.REQUIRED
    assert entry.description["es"]
    assert entry.description["en"]


def test_get_profile_key_raises_keyerror_for_unknown_key() -> None:
    with pytest.raises(KeyError):
        get_profile_key("not.a.profile.key")


def test_every_entry_carries_authoritative_spanish_description() -> None:
    for entry in PROFILE_KEYS:
        assert entry.description.get("es", "").strip(), f"{entry.key}: missing description.es"


def test_profile_key_rejects_blank_keys() -> None:
    with pytest.raises(ValueError):
        ProfileKey(
            key="",
            requirement=ProfileKeyRequirement.OPTIONAL,
            description={"es": "x", "en": "x", "ca": "x", "hu": "x"},
        )


def test_profile_key_rejects_padded_keys() -> None:
    with pytest.raises(ValueError):
        ProfileKey(
            key=" tax.id ",
            requirement=ProfileKeyRequirement.OPTIONAL,
            description={"es": "x", "en": "x", "ca": "x", "hu": "x"},
        )


def test_profile_key_rejects_descriptions_without_authoritative_spanish() -> None:
    with pytest.raises(ValueError):
        ProfileKey(
            key="x",
            requirement=ProfileKeyRequirement.OPTIONAL,
            description={"en": "english only"},  # type: ignore[typeddict-item]
        )
