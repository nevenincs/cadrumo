"""A refusal must not claim the law when the real limit is our own coverage.

The bundled IVA registry once reached back a different distance PER TIER for
Spain: general and reducido from September 2012 (RDL 20/2012), super-reducido
only from 2024 despite the 4 % tipo superreducido standing since Ley 37/1992.
That gap meant a lawful 2023 line at 4 % failed to resolve -- not because its
rate was unlawful, but because the table did not reach that tier back that far.

Saying "was not in force" there was a false statement about Spanish law, and it
was the expensive kind of false: it sends a filer to correct a figure that was
right, and it invites the next maintainer to widen the rate table with a
guessed historical value rather than an authored, corpus-backed one. The ledger
path already drew this distinction; the invoice path did not, so the same
registry gap once produced a truthful message on one surface and a false one on
the other.

**The ES per-tier gap that motivated this module is closed.** The super-reducido
record was corrected to its true 1995-01-01 start (Ley 41/1994 art. 78), which
predates the general/reducido 2012-09-01 start by seventeen years -- so there is
no longer a date where general and reducido are covered while super-reducido is
not, the exact shape these tests pinned. The anchor test below still runs and
would red the moment a live instance reappears (a tier window narrows again, or
a fourth tier joins with its own gap), naming the premise instead of going quiet.
The tests that verify the mechanism survives on tiers/dates it can still reach --
the closed general/reducido gap, a genuinely out-of-window rate, a covered date,
and the positive-tier scoping -- are kept below.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority as _indexed_authority_for_test

from ...iva.errors import IvaRateNotFoundError
from ...iva.lookup import rate_table_covers, rate_table_covers_any_positive_tier
from ...iva.schema import EUMemberState, IvaRateKind
from ..enums import IvaRate, iva_rate_percentage

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(autouse=True)
def _authority_operation() -> Iterator[None]:
    """Resolve rate slots under the generation-pinned authority production uses."""
    with _indexed_authority_for_test().operation():
        yield


#: Inside every tier's coverage, and the rates genuinely stood on this date.
_COVERED = date(2024, 6, 1)
#: The tiers bearing a positive ordinary rate, spelled out rather than imported
#: so an edit to the predicate's own tuple cannot move this in step with it.
_POSITIVE_TIERS = (IvaRateKind("general"), IvaRateKind("reduced"), IvaRateKind("super_reduced"))
#: The coverage-limit refusal's key, spelled out here so the legality test can
#: assert it is NOT the key raised, which is the whole point of the module.
_COVERAGE_GAP_KEY = "errors.iva.rate_registry_coverage_gap"


def test_no_es_tier_currently_exhibits_an_uncovered_but_lawful_date() -> None:
    """The tripwire that replaces the deleted uncovered-date fixture.

    Every ES tier's coverage reaches back past the supported floor (the standing
    tiers open in 2012, super-reducido earlier still), so no supported date is
    covered for one tier and uncovered for another -- the exact shape the
    coverage-versus-legality distinction needs a live example of. This asserts
    the closure at the floor, the earliest date the registry serves: the day it
    goes false, a tier has narrowed again and the refusal tests this module used
    to carry should be restored against the date that reopens.
    """
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        floor = _authority_operation_for_test.supported_filing_years().date_envelope().floor
        for kind in _POSITIVE_TIERS:
            assert rate_table_covers(
                EUMemberState.from_registry("es"), floor, kind, operation=_authority_operation_for_test
            ), (
                f"{kind.value} no longer covers the supported floor {floor.isoformat()} -- a per-tier "
                "coverage gap may have reopened; restore a refusal test pinned to the date that exposes it"
            )


@pytest.mark.parametrize("rate", (IvaRate.from_registry("RATE_21"), IvaRate.from_registry("RATE_10")))
def test_the_general_and_reducido_gap_is_closed_and_stays_closed(rate: IvaRate) -> None:
    """These two once refused on 2023 and must not again.

    Their records were corrected to the September 2012 start RDL 20/2012 fixed,
    which closed the coverage gap for both tiers outright. Asserting the closure
    rather than deleting the case keeps the correction pinned: re-truncating
    those windows to a later start would resurrect exactly the false-legality
    refusal this module exists to prevent, and would otherwise do it silently.
    """
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        on_date = date(2023, 6, 1)
        assert iva_rate_percentage(rate, on_date) is not None
        assert rate_table_covers(
            EUMemberState.from_registry("es"), on_date, IvaRateKind("general"), operation=_authority_operation_for_test
        )
        assert rate_table_covers(
            EUMemberState.from_registry("es"), on_date, IvaRateKind("reduced"), operation=_authority_operation_for_test
        )


def test_a_covered_date_still_refuses_a_rate_that_truly_was_not_in_force() -> None:
    """The legality refusal must survive: RATE_2 existed only Oct-Dec 2024.

    The distinction is now carried by the refusal's KEY and by the
    ``rate_registry_covers_date`` machine fact rather than by an English
    sentence, so it holds in every locale instead of only the one the sentence
    was written in. Collapsing the two conditions onto one key would excuse a
    real out-of-window claim as a registry limitation, which is the failure
    this module exists to prevent.
    """
    with pytest.raises(IvaRateNotFoundError) as caught:
        iva_rate_percentage(IvaRate.from_registry("RATE_2"), _COVERED)

    assert caught.value.translated_message == "errors.iva.rate_slot_not_in_force"
    assert caught.value.translated_message != _COVERAGE_GAP_KEY, (
        "a genuinely out-of-window rate on a COVERED date must keep the legality "
        "condition -- collapsing both onto the coverage key would excuse a real "
        "out-of-window claim as a registry limitation"
    )
    context = caught.value.context or {}
    assert context["rate_registry_covers_date"] is True
    assert context["rate_in_force"] is False
    assert context["iva_rate_slot"] == IvaRate.from_registry("RATE_2").name
    assert context["on_date"] == _COVERED.isoformat()


def test_a_covered_date_resolves_normally() -> None:
    """Guards against a refusal that fires for every date and looks like a fix."""
    assert iva_rate_percentage(IvaRate.from_registry("RATE_21"), _COVERED) == Decimal("0.21")
    assert iva_rate_percentage(IvaRate.from_registry("RATE_2"), date(2024, 11, 1)) == Decimal("0.02")


def test_the_positive_tier_reading_is_exactly_the_three_positive_tiers() -> None:
    """The scoped predicate both layers ask, pinned by definition rather than by probe.

    A caller resolving a POSITIVE declared rate asks a narrower question than
    the bare date form: only the tiers bearing a positive ordinary rate can say
    whether such a rate could have been priced.

    Asserted as an equality against a locally spelled-out tier tuple, because a
    behavioural probe cannot currently distinguish the two readings at all --
    see :func:`test_no_es_tier_currently_exhibits_an_uncovered_but_lawful_date`,
    which is the test that will tell us when one can.
    """
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        for year in _authority_operation_for_test.supported_filing_years().years:
            for month in (1, 6, 12):
                probe = date(year, month, 1)
                expected = any(
                    rate_table_covers(
                        EUMemberState.from_registry("es"), probe, kind, operation=_authority_operation_for_test
                    )
                    for kind in _POSITIVE_TIERS
                )
                assert (
                    rate_table_covers_any_positive_tier(
                        EUMemberState.from_registry("es"), probe, operation=_authority_operation_for_test
                    )
                    == expected
                ), f"the positive-tier coverage answer is not the three positive tiers on {probe.isoformat()}"


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
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        envelope = _authority_operation_for_test.supported_filing_years().date_envelope()
        day = envelope.floor
        separating: list[date] = []
        while day <= envelope.horizon:
            if rate_table_covers(
                EUMemberState.from_registry("es"), day, operation=_authority_operation_for_test
            ) != rate_table_covers_any_positive_tier(
                EUMemberState.from_registry("es"), day, operation=_authority_operation_for_test
            ):
                separating.append(day)
            day += timedelta(days=1)

        assert separating == [], (
            "a zero-tier record now reaches a date no positive tier does, starting "
            f"{separating[0].isoformat() if separating else ''} -- the positive-tier scoping is "
            "observable again, so replace this containment anchor with a probe asserting the two "
            "readings differ on that date"
        )
