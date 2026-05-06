"""Unit tests for typed profile validation."""

from __future__ import annotations

import pytest

from ...domain.profile import (
    PROFILE_KEYS,
    ProfileKey,
    ProfileKeyRequirement,
    optional_profile_keys,
    required_profile_keys,
)
from . import (
    list_profile_key_records,
    validate_profile,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _required_key() -> str:
    return required_profile_keys()[0].key


def _optional_key() -> str:
    return optional_profile_keys()[0].key


def _all_required_filled() -> dict[str, str]:
    return {entry.key: f"value-{entry.key}" for entry in required_profile_keys()}


def test_empty_values_returns_invalid_with_every_required_missing() -> None:
    result = validate_profile({})
    assert result.valid is False
    expected_missing = tuple(entry.key for entry in required_profile_keys())
    assert result.missing_required == expected_missing
    assert result.present_required == ()
    assert result.present_optional == ()
    assert result.unknown_keys == ()


def test_all_required_filled_returns_valid() -> None:
    result = validate_profile(_all_required_filled())
    assert result.valid is True
    assert result.missing_required == ()
    expected_present = tuple(entry.key for entry in required_profile_keys())
    assert result.present_required == expected_present


def test_blank_required_value_counts_as_missing() -> None:
    values = _all_required_filled()
    values[_required_key()] = "   "
    result = validate_profile(values)
    assert result.valid is False
    assert _required_key() in result.missing_required


def test_present_optional_keys_are_listed() -> None:
    values = _all_required_filled()
    values[_optional_key()] = "set"
    result = validate_profile(values)
    assert result.valid is True
    assert _optional_key() in result.present_optional


def test_absent_optional_keys_are_not_in_present_optional() -> None:
    """Optional keys never block validation and never appear in `present_optional` when absent."""
    result = validate_profile(_all_required_filled())
    for entry in optional_profile_keys():
        assert entry.key not in result.present_optional


def test_joint_taxation_requires_spouse_profile_fields() -> None:
    values = _all_required_filled()
    values["declaration.type"] = "2"

    result = validate_profile(values)

    assert result.valid is False
    assert set(result.missing_required) >= {
        "spouse.tax.id",
        "spouse.name",
        "spouse.surnames",
        "spouse.birth_date",
        "spouse.sex",
    }


def test_joint_taxation_spouse_profile_fields_clear_conditional_requirement() -> None:
    values = _all_required_filled()
    values.update(
        {
            "declaration.type": "2",
            "spouse.tax.id": "12345678Z",
            "spouse.name": "Ada",
            "spouse.surnames": "Lovelace",
            "spouse.birth_date": "1815-12-10",
            "spouse.sex": "M",
        }
    )

    result = validate_profile(values)

    assert result.valid is True
    assert result.missing_required == ()


def test_spouse_non_resident_status_requires_eu_eea_detail_when_set() -> None:
    values = _all_required_filled()
    values["spouse.non_resident_irpf"] = "true"

    missing_eu_flag = validate_profile(values)
    assert missing_eu_flag.valid is False
    assert missing_eu_flag.missing_required == ("spouse.eu_eea_resident",)

    values["spouse.eu_eea_resident"] = "true"
    missing_country = validate_profile(values)
    assert missing_country.valid is False
    assert missing_country.missing_required == ("spouse.eu_eea_country",)

    values["spouse.eu_eea_country"] = "FR"
    complete = validate_profile(values)
    assert complete.valid is True
    assert complete.missing_required == ()


def test_unknown_keys_do_not_block_validation_but_are_surfaced() -> None:
    values = _all_required_filled()
    values["bogus.key"] = "set"
    result = validate_profile(values)
    assert result.valid is True
    assert "bogus.key" in result.unknown_keys


def test_unknown_keys_are_sorted_for_stable_rendering() -> None:
    values = _all_required_filled()
    values["zeta"] = "z"
    values["alpha"] = "a"
    result = validate_profile(values)
    assert result.unknown_keys == ("alpha", "zeta")


def test_present_required_excludes_blank_values() -> None:
    values = {entry.key: "   " for entry in required_profile_keys()}
    result = validate_profile(values)
    assert result.present_required == ()
    assert result.valid is False


def test_validation_result_is_frozen() -> None:
    from pydantic import ValidationError

    result = validate_profile({})
    with pytest.raises(ValidationError):
        result.valid = True  # type: ignore[misc]


def test_missing_required_preserves_registry_order() -> None:
    """Field ordering matches the canonical PROFILE_KEYS order so renders are reproducible."""
    result = validate_profile({})
    expected = [entry.key for entry in PROFILE_KEYS if entry.requirement is ProfileKeyRequirement.REQUIRED]
    assert list(result.missing_required) == expected


def test_list_profile_key_records_returns_a_non_empty_typed_tuple() -> None:
    """The public accessor must return a non-empty tuple of ``ProfileKey`` records."""
    records = list_profile_key_records()
    assert isinstance(records, tuple)
    assert len(records) > 0
    assert all(isinstance(entry, ProfileKey) for entry in records)
