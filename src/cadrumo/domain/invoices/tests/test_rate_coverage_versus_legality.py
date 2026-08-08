"""A refusal must not claim the law when the real limit is our own coverage.

The bundled IVA registry reaches back a different distance PER TIER. Spain's
general and reducido records run from September 2012, when RDL 20/2012 fixed
21 % and 10 %; the super-reducido records begin only in 2024, while the 4 % tipo
superreducido has stood since Ley 37/1992. So a 2023 line at 4 % fails to
resolve -- not because its rate was unlawful, but because the table does not
reach that tier back that far.

Saying "was not in force" there is a false statement about Spanish law, and it
is the expensive kind of false: it sends a filer to correct a figure that was
right, and it invites the next maintainer to widen the rate table with a
guessed historical value rather than an authored, corpus-backed one.

The ledger path already drew this distinction. The invoice path did not, so the
same registry gap produced a truthful message on one surface and a false one on
the other. These tests pin the distinction on the invoice path.

**The premise is data-dependent, so it is anchored rather than assumed.** These
tests were once written against a table whose general and reducido records also
began in 2024; correcting those windows to their true 2012 start closed the
coverage gap for both tiers and left the assertions passing for reasons that had
stopped being true. Every date literal below is therefore paired with an anchor
asserting the tier window that makes it the date it claims to be, so the next
window move reds the anchor with a message naming the premise instead of going
quiet.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from cadrumo.domain.invoices import IvaRate, iva_rate_percentage
from cadrumo.domain.iva import (
    EUMemberState,
    IvaRateKind,
    IvaRateNotFoundError,
    rate_table_covers,
    rate_table_covers_any_positive_tier,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Inside every tier's coverage, and the rates genuinely stood on this date.
_COVERED = date(2024, 6, 1)
#: Outside the SUPER-REDUCIDO tier's coverage, and inside the other two. 4 % was
#: in force in Spain here, so this is the surviving lawful-but-uncovered date.
_UNCOVERED_SUPER_REDUCED = date(2023, 6, 1)
#: The tiers bearing a positive ordinary rate, spelled out rather than imported
#: so an edit to the predicate's own tuple cannot move this in step with it.
_POSITIVE_TIERS = (IvaRateKind.GENERAL, IvaRateKind.REDUCED, IvaRateKind.SUPER_REDUCED)


def test_the_uncovered_date_is_uncovered_for_the_tier_it_is_used_for() -> None:
    """The anchor under every refusal assertion below.

    Without this, backdating the super-reducido records to their true statutory
    start turns each refusal test below into an assertion about nothing --
    silently, because the refusal simply stops happening and the test that
    expected it is the one that fails, pointing at the rate rather than at the
    premise. This names the premise directly.
    """
    assert not rate_table_covers(EUMemberState.ES, _UNCOVERED_SUPER_REDUCED, IvaRateKind.SUPER_REDUCED), (
        "the super-reducido records now reach 2023, so there is no longer a lawful-but-uncovered "
        "date for that tier and these tests need a new anchor -- or, if no tier retains a gap, "
        "the coverage-versus-legality distinction has no live instance left to pin"
    )
    assert rate_table_covers(EUMemberState.ES, _COVERED, IvaRateKind.SUPER_REDUCED)


def test_coverage_is_asked_per_tier_not_per_date() -> None:
    """The property the refusal branch turns on: reach differs between tiers.

    A date-only question answers "covered" for a 4 % line the table cannot
    price, routing it back to the false legality message. This asserts the
    discrimination on the pair that currently exhibits it.
    """
    assert rate_table_covers(EUMemberState.ES, _UNCOVERED_SUPER_REDUCED, IvaRateKind.GENERAL)
    assert not rate_table_covers(EUMemberState.ES, _UNCOVERED_SUPER_REDUCED, IvaRateKind.SUPER_REDUCED)
    # The bare date form says "covered", which is exactly why it is the wrong
    # question for a caller resolving one tier.
    assert rate_table_covers(EUMemberState.ES, _UNCOVERED_SUPER_REDUCED)


def test_an_uncovered_date_refuses_on_coverage_not_on_legality() -> None:
    """4 % WAS in force in Spain in 2023, so the refusal must not say otherwise."""
    with pytest.raises(IvaRateNotFoundError) as caught:
        iva_rate_percentage(IvaRate.RATE_4, _UNCOVERED_SUPER_REDUCED)

    message = str(caught.value)
    assert "no IVA rate is on record" in message
    assert "not a statement that the rate was unlawful" in message
    assert "was not in force" not in message, (
        "the refusal claims the rate was not in force, which is false for RATE_4 in Spain on "
        f"{_UNCOVERED_SUPER_REDUCED.isoformat()} -- the limit is the registry's coverage of that "
        "tier, not the law"
    )


def test_the_coverage_refusal_names_the_tier_rather_than_the_whole_table() -> None:
    """A tier-scoped gap must not be reported as the table reaching nothing.

    The message once said the registry "carries no rates for Spain on that
    date". That was true while every tier began in 2024 and became false the
    moment one tier was backdated: on this date the table carries the general
    and reducido rates and only lacks the super-reducido one. A filer told the
    table is empty for 2023 cannot act on it; a filer told which tier is
    missing can.
    """
    with pytest.raises(IvaRateNotFoundError) as caught:
        iva_rate_percentage(IvaRate.RATE_4, _UNCOVERED_SUPER_REDUCED)

    message = str(caught.value)
    assert IvaRateKind.SUPER_REDUCED.value in message
    assert "carries no rates for Spain on that date" not in message


@pytest.mark.parametrize("rate", (IvaRate.RATE_21, IvaRate.RATE_10))
def test_the_general_and_reducido_gap_is_closed_and_stays_closed(rate: IvaRate) -> None:
    """These two once refused on 2023 and must not again.

    Their records were corrected to the September 2012 start RDL 20/2012 fixed,
    which closed the coverage gap for both tiers outright. Asserting the closure
    rather than deleting the case keeps the correction pinned: re-truncating
    those windows to a later start would resurrect exactly the false-legality
    refusal this module exists to prevent, and would otherwise do it silently.
    """
    assert iva_rate_percentage(rate, _UNCOVERED_SUPER_REDUCED) is not None
    assert rate_table_covers(EUMemberState.ES, _UNCOVERED_SUPER_REDUCED, IvaRateKind.GENERAL)
    assert rate_table_covers(EUMemberState.ES, _UNCOVERED_SUPER_REDUCED, IvaRateKind.REDUCED)


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


def test_the_positive_tier_reading_is_exactly_the_three_positive_tiers() -> None:
    """The scoped predicate both layers ask, pinned by definition rather than by probe.

    A caller resolving a POSITIVE declared rate asks a narrower question than
    the bare date form: only the tiers bearing a positive ordinary rate can say
    whether such a rate could have been priced.

    Asserted as an equality against a locally spelled-out tier tuple, because a
    behavioural probe cannot currently distinguish the two readings at all --
    see the anchor below, which is the test that will tell us when one can.
    """
    for year in (2011, 2012, 2013, 2023, 2024, 2025, 2026):
        for month in (1, 6, 12):
            probe = date(year, month, 1)
            expected = any(rate_table_covers(EUMemberState.ES, probe, kind) for kind in _POSITIVE_TIERS)
            assert rate_table_covers_any_positive_tier(EUMemberState.ES, probe) == expected, (
                f"the positive-tier coverage answer is not the three positive tiers on {probe.isoformat()}"
            )


def test_the_zero_tier_currently_hides_inside_the_positive_tiers() -> None:
    """The scoping is real but presently unobservable, and that must be stated.

    Excluding the zero tier exists because zero-tier records once reached dates
    the general tier did not, so counting them made a 2023 date look priceable
    for a 21 % line. After the general and reducido windows were corrected back
    to 2012, the zero-tier windows fall strictly INSIDE them, so no date
    separates "any tier covers" from "a positive tier covers" -- which means the
    guard above cannot fail by probing, whatever span it walks.

    This asserts that containment directly. When a zero-tier window next reaches
    outside the positive ones, this reds and says so, and a behavioural probe
    becomes possible again and should be restored.
    """
    day = date(2010, 1, 1)
    separating: list[date] = []
    while day < date(2027, 1, 1):
        if rate_table_covers(EUMemberState.ES, day) != rate_table_covers_any_positive_tier(EUMemberState.ES, day):
            separating.append(day)
        day += timedelta(days=1)

    assert separating == [], (
        "a zero-tier record now reaches a date no positive tier does, starting "
        f"{separating[0].isoformat() if separating else ''} -- the positive-tier scoping is "
        "observable again, so replace this containment anchor with a probe asserting the two "
        "readings differ on that date"
    )
