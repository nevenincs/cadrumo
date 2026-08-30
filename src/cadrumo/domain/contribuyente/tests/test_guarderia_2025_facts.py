"""Real guardería fact aggregation for the 2025 filing year."""

from __future__ import annotations

from datetime import date

import pytest

from ..descendant import DescendantInfo
from ..family_profile import RentaFamilyProfile
from ..family_types import GuarderiaMonthSpend

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_FILING_YEAR = 2025

# AEAT Manual práctico de Renta 2025, Parte 1, pp. 1391 and 1393:
# both worked cases use 500 euros for each complete month and report 2,290
# euros of effective non-subsidised custody spend.  The manual's 166.67 and
# 500 euro cap results are deliberately not calculated or asserted here.
# Keep the child under three for the whole filing period so this source test
# isolates month aggregation from the separate turning-three eligibility rule.
_OFFICIAL_CHILD_BIRTH_DATE = date(2023, 1, 1)
_OFFICIAL_COMPLETE_MONTH_SPEND_EUROS = 500
_OFFICIAL_EFFECTIVE_CUSTODY_SPEND_EUROS = 2_290


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


def test_2025_turning_three_child_counts_every_declared_month() -> None:
    """The birthday draws no line in the turning-three period.

    Capítulo 18's post-birthday sentence GRANTS the months after the third
    birthday; it does not withdraw the ones before it. The manual's own worked
    case settles it — a child who turns three in September is granted the
    increment over January to June. So every declared month aggregates, and the
    900 in the birthday month is retained rather than dropped.
    """
    child = DescendantInfo(
        birth_date=date(_FILING_YEAR - 3, 4, 15),
        gastos_guarderia_mensuales=_monthly_spend((100, 100, 100, 900, 200, 200, 200, 200, 200, 200, 200, 200)),
    )

    profile = RentaFamilyProfile(descendientes=(child,))

    assert profile.gastos_guarderia_reales(_FILING_YEAR) == 2_800


def test_2025_spend_outside_the_qualifying_period_yields_zero() -> None:
    child = DescendantInfo(
        birth_date=date(_FILING_YEAR - 4, 4, 15),
        gastos_guarderia_mensuales=_monthly_spend((210,) * 12),
    )

    profile = RentaFamilyProfile(descendientes=(child,))

    assert profile.gastos_guarderia_reales(_FILING_YEAR) == 0


@pytest.mark.parametrize(
    "qualifying_month_spend",
    [
        pytest.param(
            ((5, _OFFICIAL_COMPLETE_MONTH_SPEND_EUROS), (6, _OFFICIAL_COMPLETE_MONTH_SPEND_EUROS)),
            id="manual-case-a-two-qualifying-months",
        ),
        pytest.param(
            (
                (1, _OFFICIAL_COMPLETE_MONTH_SPEND_EUROS),
                (2, _OFFICIAL_COMPLETE_MONTH_SPEND_EUROS),
                (3, _OFFICIAL_COMPLETE_MONTH_SPEND_EUROS),
                (4, _OFFICIAL_COMPLETE_MONTH_SPEND_EUROS),
                (5, _OFFICIAL_COMPLETE_MONTH_SPEND_EUROS),
                (6, _OFFICIAL_COMPLETE_MONTH_SPEND_EUROS),
            ),
            id="manual-case-b-six-qualifying-months",
        ),
    ],
)
def test_2025_manual_examples_retain_raw_months_and_effective_spend_inputs(
    qualifying_month_spend: tuple[tuple[int, int], ...],
) -> None:
    """The canonical source retains both accepted spend-input shapes.

    ``DescendantInfo`` deliberately makes annual and monthly spend authorities
    mutually exclusive.  Keep the raw qualifying-month map and the official
    effective annual spend in separate real profiles here; combining them would
    invent a source contract that production does not currently expose.
    """
    raw_child = DescendantInfo(
        birth_date=_OFFICIAL_CHILD_BIRTH_DATE,
        gastos_guarderia_mensuales=tuple(
            GuarderiaMonthSpend(month=month, amount_euros=amount) for month, amount in qualifying_month_spend
        ),
    )
    raw_profile = RentaFamilyProfile(descendientes=(raw_child,))

    effective_child = DescendantInfo(
        birth_date=_OFFICIAL_CHILD_BIRTH_DATE,
        gastos_guarderia_euros=_OFFICIAL_EFFECTIVE_CUSTODY_SPEND_EUROS,
    )
    effective_profile = RentaFamilyProfile(descendientes=(effective_child,))

    assert raw_profile.gastos_guarderia_reales(_FILING_YEAR) == sum(amount for _month, amount in qualifying_month_spend)
    assert effective_profile.gastos_guarderia_reales(_FILING_YEAR) == _OFFICIAL_EFFECTIVE_CUSTODY_SPEND_EUROS
