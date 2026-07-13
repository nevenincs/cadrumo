"""Unit tests for typed Modelo 100 family profile records."""

from __future__ import annotations

from datetime import date

import pytest

from ..family import RentaAscendantProfile, RentaDescendantProfile, RentaFamilyProfile

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_renta_family_profile_round_trips_descendants_and_ascendants() -> None:
    profile = RentaFamilyProfile(
        descendants=(
            RentaDescendantProfile(
                tax_id="TAXIDABCD",
                display_name="Test Descendant",
                birth_date=date(2018, 1, 2),
                disability_grade="1",
            ),
        ),
        ascendants=(
            RentaAscendantProfile(
                tax_id="TAXIDWXYZ",
                display_name="Test Ascendant",
                birth_date=date(1940, 3, 4),
                cohabiting_descendant_count=1,
            ),
        ),
    )

    reparsed = RentaFamilyProfile.model_validate_json(profile.model_dump_json())

    assert reparsed == profile
    assert reparsed.descendants[0].birth_date == date(2018, 1, 2)
    assert reparsed.ascendants[0].cohabiting_descendant_count == 1


def test_renta_family_profile_rejects_unknown_schema_version() -> None:
    with pytest.raises(ValueError, match="schema_version"):
        RentaFamilyProfile(schema_version="2")


def test_renta_family_member_rejects_blank_optional_text() -> None:
    with pytest.raises(ValueError, match="blank"):
        RentaDescendantProfile(tax_id=" ", birth_date=date(2020, 1, 1))


def test_renta_ascendant_cohabiting_descendant_count_follows_dictionary_range() -> None:
    # Field constraint: le=10. Pydantic emits "less than or equal to 10"
    # for the violation.
    invalid_count: int = 11
    with pytest.raises(ValueError, match=r"less than or equal to 10"):
        RentaAscendantProfile(birth_date=date(1940, 1, 1), cohabiting_descendant_count=invalid_count)
