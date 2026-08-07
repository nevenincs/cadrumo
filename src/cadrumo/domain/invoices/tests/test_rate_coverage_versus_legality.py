"""A refusal must not claim the law when the real limit is our own coverage.

The bundled IVA registry is a CURRENT-rates table refreshed in bulk: no record
for any member state starts before 2024. So a 2023 invoice line fails to
resolve -- not because its rate was unlawful, but because the table does not
reach back that far. Spain's general 21 % has stood since 2012.

Saying "was not in force" there is a false statement about Spanish law, and it
is the expensive kind of false: it sends a filer to correct a figure that was
right, and it invites the next maintainer to widen the rate table with a
guessed historical value rather than an authored, corpus-backed one.

The ledger path already drew this distinction. The invoice path did not, so the
same registry gap produced a truthful message on one surface and a false one on
the other. These tests pin the distinction on the invoice path and pin that
both paths answer from the SAME predicate, so they cannot drift back apart.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.application.aggregation._iva_ledger import _rate_table_covers
from cadrumo.domain.invoices import IvaRate, iva_rate_percentage
from cadrumo.domain.iva import (
    EUMemberState,
    IvaRateKind,
    IvaRateNotFoundError,
    rate_table_covers,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Inside the table's coverage, and the rate genuinely stood on this date.
_COVERED = date(2024, 6, 1)
#: Outside the table's coverage. 21 / 10 / 4 were all in force in Spain here.
_UNCOVERED = date(2023, 6, 1)


def test_coverage_is_asked_per_tier_not_per_date() -> None:
    """The premise every other test here rests on, asserted rather than assumed.

    Coverage must be asked PER TIER. The registry holds zero-tier and 5 % food
    records reaching back to 2023 while the general tier starts in 2024, so a
    date-only question answers "covered" for a 21 % line the table cannot price
    -- routing it back to the false legality message. This asserts the
    discrimination directly, because it is what broke when the 2023 food rows
    landed and it is invisible from any single-tier probe.
    """
    assert rate_table_covers(EUMemberState.ES, _COVERED, IvaRateKind.GENERAL)
    assert not rate_table_covers(EUMemberState.ES, _UNCOVERED, IvaRateKind.GENERAL)
    # The zero tier DOES reach 2023, which is exactly why "any tier" is the
    # wrong question for a general-rate caller.
    assert rate_table_covers(EUMemberState.ES, _UNCOVERED, IvaRateKind.ZERO)
    assert rate_table_covers(EUMemberState.ES, _UNCOVERED)


@pytest.mark.parametrize("rate", (IvaRate.RATE_21, IvaRate.RATE_10, IvaRate.RATE_4))
def test_an_uncovered_date_refuses_on_coverage_not_on_legality(rate: IvaRate) -> None:
    """These three rates WERE in force in 2023, so the refusal must not say otherwise."""
    with pytest.raises(IvaRateNotFoundError) as caught:
        iva_rate_percentage(rate, _UNCOVERED)

    message = str(caught.value)
    assert "no IVA rate is on record" in message
    assert "not a statement that the rate was unlawful" in message
    assert "was not in force" not in message, (
        "the refusal claims the rate was not in force, which is false for "
        f"{rate.name} in Spain on {_UNCOVERED.isoformat()} -- the limit is the "
        "registry's coverage, not the law"
    )


def test_a_covered_date_still_refuses_a_rate_that_truly_was_not_in_force() -> None:
    """The legality refusal must survive: RATE_2 existed only Oct-Dec 2024."""
    with pytest.raises(IvaRateNotFoundError) as caught:
        iva_rate_percentage(IvaRate.RATE_2, _COVERED)

    message = str(caught.value)
    assert "was not in force" in message
    assert "no IVA rate is on record" not in message, (
        "a genuinely out-of-window rate on a COVERED date must keep the legality "
        "message -- collapsing both into the coverage wording would excuse a real "
        "out-of-window claim as a registry limitation"
    )


def test_a_covered_date_resolves_normally() -> None:
    """Guards against a refusal that fires for every date and looks like a fix."""
    assert iva_rate_percentage(IvaRate.RATE_21, _COVERED) == Decimal("0.21")
    assert iva_rate_percentage(IvaRate.RATE_2, date(2024, 11, 1)) == Decimal("0.02")


def test_both_layers_answer_coverage_from_one_predicate() -> None:
    """The ledger predicate must DELEGATE, not reimplement.

    Two predicates over the same table can drift into disagreeing about the
    same date, which is exactly how this asymmetry arose. Comparing them across
    a span that crosses the coverage edge catches a reimplementation that agrees
    on the easy cases.

    The ledger asks a NARROWER question than the bare date form: it only reaches
    this branch for a positive declared rate, so it scopes coverage to the tiers
    bearing a positive ordinary rate. Comparing against that scoped reading
    rather than the any-tier one is the honest equivalence -- the earlier
    date-only comparison passed for the wrong reason once the zero tier gained
    2023 records, since both sides then said "covered" about different tiers.
    """
    positive_tiers = (IvaRateKind.GENERAL, IvaRateKind.REDUCED, IvaRateKind.SUPER_REDUCED)
    for year in (2022, 2023, 2024, 2025, 2026):
        for month in (1, 6, 12):
            probe = date(year, month, 1)
            expected = any(rate_table_covers(EUMemberState.ES, probe, kind) for kind in positive_tiers)
            assert _rate_table_covers(probe) == expected, (
                f"the ledger and domain coverage answers disagree on {probe.isoformat()}"
            )
