"""Unit tests for the application profile-key model and catalogue."""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority as _indexed_authority_for_test

from ....core.i18n.translatable import Translatable as tr
from ....core.requirement import Requirement
from ..keys_validation import validate_profile_values
from ..profile_key import ProfileKey
from ..profile_keys import optional_profile_keys, profile_key, profile_keys

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_catalogue_is_non_empty_and_unique() -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        entries = profile_keys(operation=_authority_operation_for_test)
        assert len(entries) >= 1
        keys = [entry.key for entry in entries]
        assert len(keys) == len(set(keys)), "every profile key must be unique"


def test_required_and_optional_partition_covers_catalogue() -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        required = tuple(
            entry
            for entry in profile_keys(operation=_authority_operation_for_test)
            if entry.requirement is Requirement.REQUIRED
        )
        optional = optional_profile_keys(operation=_authority_operation_for_test)
        assert {entry.key for entry in required + optional} == {
            entry.key for entry in profile_keys(operation=_authority_operation_for_test)
        }
        assert all(entry.requirement is Requirement.REQUIRED for entry in required)
        assert all(entry.requirement is Requirement.OPTIONAL for entry in optional)


def test_catalogue_lookup_returns_canonical_record() -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        entry = profile_key("identity.tax_id", operation=_authority_operation_for_test)
        assert isinstance(entry, ProfileKey)
        assert entry.key == "identity.tax_id"
        assert entry.requirement is Requirement.REQUIRED
        assert entry.description


def test_catalogue_lookup_raises_keyerror_for_unknown_key() -> None:
    with (
        _indexed_authority_for_test().operation() as _authority_operation_for_test,
        pytest.raises(KeyError, match=r"unknown profile key"),
    ):
        profile_key("not.a.profile.key", operation=_authority_operation_for_test)


def test_every_entry_carries_authoritative_profile_description() -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        for entry in profile_keys(operation=_authority_operation_for_test):
            assert entry.description.strip(), f"{entry.key}: missing description"


def test_profile_key_rejects_blank_keys() -> None:
    # Empty key is rejected by the pydantic Field(min_length=1) constraint
    # BEFORE the custom _validate_key validator runs.
    with pytest.raises(ValueError, match=r"at least 1 character"):
        ProfileKey(
            key="",
            requirement=Requirement.OPTIONAL,
            description=tr("profile.keys.description"),
        )


def test_profile_key_rejects_padded_keys() -> None:
    with pytest.raises(ValueError, match=r"key must not be padded with whitespace"):
        ProfileKey(
            key=" tax.id ",
            requirement=Requirement.OPTIONAL,
            description=tr("profile.keys.description"),
        )


def test_profile_key_rejects_descriptions_without_profile_prefix() -> None:
    with pytest.raises(ValueError, match=r"description must use a profile translation key"):
        ProfileKey(
            key="x",
            requirement=Requirement.OPTIONAL,
            description=tr("translation"),
        )


def test_profile_key_conditional_requirement_fields_must_be_paired() -> None:
    with pytest.raises(ValueError, match=r"required_when_key and required_when_value must be set together"):
        ProfileKey(
            key="spouse.tax.id",
            requirement=Requirement.OPTIONAL,
            description=tr("profile.keys.description"),
            required_when_key="declaration.type",
        )


def test_spouse_tax_id_is_required_only_for_the_married_joint_unit() -> None:
    """A joint return of the married unit owes the spouse NIF; a single-parent one has no spouse.

    Art. 82.1 LIRPF: the first unit is the spouses, the second a single parent
    with the children. The catalogue entry is optional; the completeness rules
    promote it while the joint return may be the married unit's, which includes
    an unstated situation.
    """
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        entry = profile_key("renta_spouse.tax_id", operation=_authority_operation_for_test)
        assert entry.requirement is Requirement.OPTIONAL
        assert entry.required_when_key is None

        def owed(values: dict[str, str]) -> bool:
            return (
                "renta_spouse.tax_id"
                in validate_profile_values(values, operation=_authority_operation_for_test).missing_required
            )

        assert owed({"renta_filing.declaration_type": "2", "renta_family.situacion_familiar": "casado"})
        assert owed({"renta_filing.declaration_type": "2"})
        assert not owed({"renta_filing.declaration_type": "2", "renta_family.situacion_familiar": "soltero"})
        assert not owed({"renta_filing.declaration_type": "1", "renta_family.situacion_familiar": "casado"})


def test_optional_spouse_keys_carry_no_conditional_requirement() -> None:
    """The remaining spouse identity keys are optional even for joint filing."""
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        for key in (
            "renta_spouse.name",
            "renta_spouse.surnames",
            "renta_spouse.birth_date",
            "renta_spouse.sex",
        ):
            entry = profile_key(key, operation=_authority_operation_for_test)
            assert entry.requirement is Requirement.OPTIONAL
            assert entry.required_when_key is None
            assert entry.required_when_value is None


def test_renta_family_profile_keys_cover_official_scalar_family_fields() -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
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

        assert expected.issubset(
            {entry.key for entry in optional_profile_keys(operation=_authority_operation_for_test)}
        )
        assert (
            profile_key("renta_spouse.eu_eea_resident", operation=_authority_operation_for_test).required_when_key
            is None
        )
        assert (
            profile_key("renta_spouse.eu_eea_country", operation=_authority_operation_for_test).required_when_key
            == "renta_spouse.eu_eea_resident"
        )
        assert (
            profile_key("renta_spouse.eu_eea_country", operation=_authority_operation_for_test).required_when_value
            == "true"
        )
