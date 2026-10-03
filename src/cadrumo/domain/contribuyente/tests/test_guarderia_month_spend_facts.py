"""Real guardería fact aggregation across the supported filing years."""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.domain.calculations.registry.tests.authored_editions import manual_editions_printing
from cadrumo.domain.calculations.registry.tests.published_authority import PublishedGovernedFactSource

from ..descendant import DescendantInfo
from ..family_fact_context import FamilyFactResolutionContext
from ..family_profile import RentaFamilyProfile
from ..family_types import GuarderiaMonthSpend

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SUPPORTED_YEARS = PublishedGovernedFactSource().supported_filing_years().years

# The AEAT Manual practico de Renta editions (Parte 1, capitulo 18) whose two worked
# guarderia cases print these figures: 500 euros for each complete month and 2.290
# euros of effective non-subsidised custody spend. The 166,67 and 500 euro cap results
# are deliberately not calculated or asserted here. Every supported edition that
# prints the cases is exercised.
_MANUAL_EXERCISES = tuple(
    year for year in manual_editions_printing("renta", "2.290 euros", "166,67 euros") if year in _SUPPORTED_YEARS
)
assert _MANUAL_EXERCISES, "no supported Renta manual edition prints the guarderia worked cases"
_OFFICIAL_COMPLETE_MONTH_SPEND_EUROS = 500
_OFFICIAL_EFFECTIVE_CUSTODY_SPEND_EUROS = 2_290


def _fact_context(filing_year: int) -> FamilyFactResolutionContext:
    return FamilyFactResolutionContext(
        PublishedGovernedFactSource(),
        date(filing_year, 12, 31),
        date(filing_year, 12, 31),
    )


def _guarderia_spend(profile: RentaFamilyProfile, filing_year: int, *, context: FamilyFactResolutionContext) -> int:
    """The Art. 81.2 spend every descendant contributes in *filing_year*, summed per child."""
    return sum(child.guarderia_contributing_spend(filing_year, context=context) for child in profile.descendientes)


def _monthly_spend(amounts: tuple[int, ...]) -> tuple[GuarderiaMonthSpend, ...]:
    """Build the real month-granular spend objects used by the profile."""
    return tuple(GuarderiaMonthSpend(month=month, amount_euros=amount) for month, amount in enumerate(amounts, start=1))


@pytest.mark.parametrize("filing_year", _SUPPORTED_YEARS)
def test_full_period_monthly_spend_is_retained_by_family_aggregation(filing_year: int) -> None:
    child = DescendantInfo(
        birth_date=date(filing_year - 2, 6, 1),
        gastos_guarderia_mensuales=_monthly_spend((150,) * 12),
    )

    profile = RentaFamilyProfile(descendientes=(child,))

    assert _guarderia_spend(profile, filing_year, context=_fact_context(filing_year)) == 1_800


@pytest.mark.parametrize("filing_year", _SUPPORTED_YEARS)
def test_turning_three_child_counts_every_declared_month(filing_year: int) -> None:
    """The birthday draws no line in the turning-three period.

    Capítulo 18's post-birthday sentence GRANTS the months after the third
    birthday; it does not withdraw the ones before it. The manual's own worked
    case settles it — a child who turns three in September is granted the
    increment over January to June. So every declared month aggregates, and the
    900 in the birthday month is retained rather than dropped.
    """
    child = DescendantInfo(
        birth_date=date(filing_year - 3, 4, 15),
        gastos_guarderia_mensuales=_monthly_spend((100, 100, 100, 900, 200, 200, 200, 200, 200, 200, 200, 200)),
    )

    profile = RentaFamilyProfile(descendientes=(child,))

    assert _guarderia_spend(profile, filing_year, context=_fact_context(filing_year)) == 2_800


@pytest.mark.parametrize("filing_year", _SUPPORTED_YEARS)
def test_spend_outside_the_qualifying_period_yields_zero(filing_year: int) -> None:
    child = DescendantInfo(
        birth_date=date(filing_year - 4, 4, 15),
        gastos_guarderia_mensuales=_monthly_spend((210,) * 12),
    )

    profile = RentaFamilyProfile(descendientes=(child,))

    assert _guarderia_spend(profile, filing_year, context=_fact_context(filing_year)) == 0


@pytest.mark.parametrize("manual_exercise", _MANUAL_EXERCISES)
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
def test_manual_examples_retain_raw_months_and_effective_spend_inputs(
    qualifying_month_spend: tuple[tuple[int, int], ...],
    manual_exercise: int,
) -> None:
    """The canonical source retains both accepted spend-input shapes.

    ``DescendantInfo`` deliberately makes annual and monthly spend authorities
    mutually exclusive.  Keep the raw qualifying-month map and the official
    effective annual spend in separate real profiles here; combining them would
    invent a source contract that production does not currently expose.
    """
    # Keep the child under three for the whole filing period so this source test
    # isolates month aggregation from the separate turning-three eligibility rule.
    child_birth_date = date(manual_exercise - 2, 1, 1)
    raw_child = DescendantInfo(
        birth_date=child_birth_date,
        gastos_guarderia_mensuales=tuple(
            GuarderiaMonthSpend(month=month, amount_euros=amount) for month, amount in qualifying_month_spend
        ),
    )
    raw_profile = RentaFamilyProfile(descendientes=(raw_child,))

    effective_child = DescendantInfo(
        birth_date=child_birth_date,
        gastos_guarderia_euros=_OFFICIAL_EFFECTIVE_CUSTODY_SPEND_EUROS,
    )
    effective_profile = RentaFamilyProfile(descendientes=(effective_child,))

    manual_context = _fact_context(manual_exercise)
    assert _guarderia_spend(raw_profile, manual_exercise, context=manual_context) == sum(
        amount for _month, amount in qualifying_month_spend
    )
    assert (
        _guarderia_spend(effective_profile, manual_exercise, context=manual_context)
        == _OFFICIAL_EFFECTIVE_CUSTODY_SPEND_EUROS
    )
