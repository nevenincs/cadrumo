"""Unit tests for the Comunidad de Madrid nacimiento/adopción deducción
framework primitives (DL 1/2010 arts. 4 y 18.1) on the family profile.

Ground truth (bundled AEAT Renta 2025 manual, parte 2, deducciones autonómicas,
Comunidad de Madrid, "Por nacimiento o adopción de hijos"):

    Ámbito temporal: the deducción applies in the period of nacimiento/adopción
    AND in each of the two following periods (a three-period window keyed on the
    entry year).
    Requisito: only parents who cohabit with the child.
    Prorrateo: split by halves when the child cohabits with both parents who file
    individually.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ..family import (
    DescendantInfo,
    RentaFamilyProfile,
    within_multi_year_applicability_window,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_applicability_window_three_period_span_for_filing_year_2025() -> None:
    """The window is the closed interval [entry_year, entry_year + 2]."""
    cases = (
        ("entry-year", 2023, True),
        ("first-following-period", 2024, True),
        ("second-following-period", 2025, True),
        ("before-window", 2022, False),
        ("future-entry", 2026, False),
    )
    for case_id, entry_year, expected in cases:
        assert within_multi_year_applicability_window(entry_year, 2025, following_periods=2) is expected, case_id


def test_applicability_window_single_year_when_no_following_periods() -> None:
    assert within_multi_year_applicability_window(2025, 2025, following_periods=0) is True
    assert within_multi_year_applicability_window(2024, 2025, following_periods=0) is False


def test_applicability_window_rejects_negative_following_periods() -> None:
    from .._errors import ProfileValidationError

    with pytest.raises(ProfileValidationError):
        within_multi_year_applicability_window(2025, 2025, following_periods=-1)


def _child(*, birth: date, adoption: date | None = None, convive: bool = True, shared: bool = False) -> DescendantInfo:
    return DescendantInfo(
        birth_date=birth,
        adoption_date=adoption,
        convive_con_contribuyente=convive,
        custodia_compartida=shared,
    )


def test_eligibility_uses_adoption_date_as_entry_when_present() -> None:
    """A child born in 2018 but adopted in 2024 is in the 2025 window via adoption_date."""
    child = _child(birth=date(2018, 5, 1), adoption=date(2024, 3, 10))
    assert child.entry_year() == 2024
    assert child.is_nacimiento_adopcion_eligible(2025) is True


def test_eligibility_excludes_non_cohabiting_and_out_of_window_children() -> None:
    cases = (
        ("non-cohabiting", _child(birth=date(2024, 2, 1), convive=False)),
        ("out-of-window", _child(birth=date(2020, 1, 1))),
    )
    for case_id, child in cases:
        assert child.is_nacimiento_adopcion_eligible(2025) is False, case_id


def test_prorrateo_share_reflects_shared_custody() -> None:
    cases = (
        ("not-shared", _child(birth=date(2024, 1, 1)), Decimal("1")),
        ("shared", _child(birth=date(2024, 1, 1), shared=True), Decimal("0.5")),
    )
    for case_id, child, expected in cases:
        assert child.nacimiento_adopcion_prorrateo_share() == expected, case_id


def test_profile_eligible_count_ignores_out_of_window_and_non_cohabiting() -> None:
    profile = RentaFamilyProfile(
        descendientes=(
            _child(birth=date(2024, 6, 1)),  # eligible
            _child(birth=date(2023, 2, 1)),  # eligible (entry year 2023, in window)
            _child(birth=date(2020, 1, 1)),  # out of window
            _child(birth=date(2025, 1, 1), convive=False),  # non-cohabiting
        ),
    )
    assert profile.madrid_nacimiento_adopcion_eligible_count(2025) == 2


def test_profile_weighted_count_embeds_prorrateo() -> None:
    """Two eligible children, one under shared custody → weighted count 1 + 0,5 = 1,5."""
    profile = RentaFamilyProfile(
        descendientes=(
            _child(birth=date(2024, 6, 1)),
            _child(birth=date(2025, 1, 1), shared=True),
        ),
    )
    assert profile.madrid_nacimiento_adopcion_weighted_count(2025) == Decimal("1.5")


def test_profile_weighted_count_zero_when_no_eligible_descendants() -> None:
    profile = RentaFamilyProfile(descendientes=(_child(birth=date(2019, 1, 1)),))
    assert profile.madrid_nacimiento_adopcion_weighted_count(2025) == Decimal("0")


def test_unidad_familiar_otros_miembros_base_is_zero_for_single_filer() -> None:
    """The single/monoparental filer's other-members base is zero; the filer's own
    base (0435 + 0460) is added by the registry formula."""
    profile = RentaFamilyProfile(descendientes=(_child(birth=date(2024, 6, 1)),))
    assert profile.unidad_familiar_otros_miembros_base() == Decimal("0")
