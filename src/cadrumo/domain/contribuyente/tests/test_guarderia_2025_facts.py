"""Real guardería fact aggregation for the 2025 filing year."""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.domain.contribuyente import DescendantInfo, GuarderiaMonthSpend, RentaFamilyProfile

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_FILING_YEAR = 2025


def _monthly_spend(amounts: tuple[int, ...]) -> tuple[GuarderiaMonthSpend, ...]:
    """Build the real month-granular spend objects used by the profile."""
    return tuple(GuarderiaMonthSpend(month=month, amount_euros=amount) for month, amount in enumerate(amounts, start=1))


def test_2025_full_period_monthly_spend_is_retained_by_family_aggregation() -> None:
    child = DescendantInfo(
        birth_date=date(_FILING_YEAR - 2, 6, 1),
        gastos_guarderia_mensuales=_monthly_spend((150,) * 12),
    )

    profile = RentaFamilyProfile(descendientes=(child,))

    assert profile.gastos_guarderia_reales(_FILING_YEAR) == 1_800


def test_2025_turning_three_child_counts_only_months_after_birthday_month() -> None:
    child = DescendantInfo(
        birth_date=date(_FILING_YEAR - 3, 4, 15),
        gastos_guarderia_mensuales=_monthly_spend((100, 100, 100, 900, 200, 200, 200, 200, 200, 200, 200, 200)),
    )

    profile = RentaFamilyProfile(descendientes=(child,))

    assert profile.gastos_guarderia_reales(_FILING_YEAR) == 1_600


def test_2025_spend_outside_the_qualifying_period_yields_zero() -> None:
    child = DescendantInfo(
        birth_date=date(_FILING_YEAR - 4, 4, 15),
        gastos_guarderia_mensuales=_monthly_spend((210,) * 12),
    )

    profile = RentaFamilyProfile(descendientes=(child,))

    assert profile.gastos_guarderia_reales(_FILING_YEAR) == 0
