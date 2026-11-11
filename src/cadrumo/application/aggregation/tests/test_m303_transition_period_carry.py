"""Transition-period applicability answers for every bundled Modelo 303 edition.

The last period of a Modelo 303 filing cadence carries the prorrata option and
revocation, and the official record design states the condition in exactly
those terms: "SI para el ultimo periodo (12 y 4T)". Both cadences are therefore
checked here, for every edition the bundled authority publishes, through the
registry rather than against a period list held in the code under test.

Modelo 303 files monthly only under the editions that declare that cadence, so the
monthly cases are asked of the years whose selected edition declares it.
"""

from __future__ import annotations

from itertools import pairwise

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.tests.authored_editions import (
    authored_revisions,
    filing_grade_exercises,
    filing_year_envelope,
)
from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot

from ....core.period import Period
from ....domain.calculations.registry.bindings_previous_filing import periodic_carry_bindings_for_period
from ..m303_arrivals import transition_period_applicability_from_registry

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_QUARTERS = ("1T", "2T", "3T", "4T")


def _supported_editions() -> tuple[tuple[int, frozenset[str], str], ...]:
    """Return, per authored Modelo 303 edition inside the support envelope, its first year, periods and id."""
    floor = filing_year_envelope().floor
    return tuple(
        (
            revision.valid_from.year,
            frozenset(revision.period_selector.periods_for_year(revision.valid_from.year)),
            str(revision.id),
        )
        for revision in authored_revisions("303")
        if revision.valid_from.year >= floor
    )


def _edition_contexts() -> tuple[tuple[int, str, str], ...]:
    """Return one filing context per bundled Modelo 303 edition, with the edition it selects."""
    return tuple(
        (year, next(code for code in _QUARTERS if code in periods), revision_id)
        for year, periods, revision_id in _supported_editions()
    )


def _years_declaring(cadence: str) -> tuple[int, ...]:
    """Return the filing years whose Modelo 303 editions declare ``cadence``: the quarterly or the monthly one."""
    years: set[int] = set()
    for year, periods, _revision_id in _supported_editions():
        declared = [code for code in periods if (code in _QUARTERS if cadence == "quarterly" else code.isdigit())]
        if declared:
            years.add(year)
    return tuple(sorted(years))


def _last_periods_of_editions_replaced_mid_year() -> tuple[tuple[int, str], ...]:
    """Return the last quarterly and monthly period of each edition a later edition replaces in its own year."""
    floor = filing_year_envelope().floor
    cases: list[tuple[int, str]] = []
    for earlier, later in pairwise(authored_revisions("303")):
        year = earlier.valid_from.year
        if year != later.valid_from.year or year < floor:
            continue
        served = earlier.period_selector.periods_for_year(year)
        cases.append((year, max(code for code in served if code in _QUARTERS)))
        cases.append((year, max(code for code in served if code.isdigit())))
    return tuple(cases)


#: One filing context per bundled Modelo 303 edition, with the edition it selects.
_EDITION_CONTEXTS = _edition_contexts()
#: Filing years whose Modelo 303 editions declare the quarterly cadence.
_QUARTERLY_YEARS = _years_declaring("quarterly")
#: Filing years whose Modelo 303 editions declare the monthly cadence.
_MONTHLY_YEARS = _years_declaring("monthly")


@pytest.mark.parametrize(("filing_year", "period_code", "revision_id"), _EDITION_CONTEXTS)
def test_each_edition_is_selected_by_its_context(filing_year: int, period_code: str, revision_id: str) -> None:
    snapshot = published_snapshot("303", filing_year=filing_year, period=period_code)

    assert snapshot.snapshot_ref.revision_id == revision_id


@pytest.mark.parametrize(("filing_year", "period_code", "revision_id"), _EDITION_CONTEXTS)
def test_every_edition_declares_the_periodic_carry_the_applicability_is_read_from(
    filing_year: int,
    period_code: str,
    revision_id: str,
) -> None:
    """The compensacion carry is what places a period in a recurring filing chain."""
    revision = published_snapshot("303", filing_year=filing_year, period=period_code).revision

    carries = periodic_carry_bindings_for_period(revision)

    assert carries, revision_id
    assert "modelo-303-compensacion-pendiente-anteriores" in {str(binding.id) for binding, _ in carries}
    covered = {token for _binding, periods in carries for token in periods}
    assert covered == {token for schedule in revision.filing_schedules for token in schedule.periods}, revision_id


@pytest.mark.parametrize("filing_year", _QUARTERLY_YEARS)
def test_the_fourth_quarter_is_a_transition_period(filing_year: int) -> None:
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        assert (
            transition_period_applicability_from_registry(
                Period.from_year_and_code(filing_year, "4T"), operation=_authority_operation_for_test
            )
            is True
        )


@pytest.mark.parametrize("filing_year", _MONTHLY_YEARS)
def test_december_is_a_transition_period(filing_year: int) -> None:
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        assert (
            transition_period_applicability_from_registry(
                Period.from_year_and_code(filing_year, "12"), operation=_authority_operation_for_test
            )
            is True
        )


@pytest.mark.parametrize("filing_year", _QUARTERLY_YEARS)
def test_the_first_quarter_is_not_a_transition_period(filing_year: int) -> None:
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        assert (
            transition_period_applicability_from_registry(
                Period.from_year_and_code(filing_year, "1T"), operation=_authority_operation_for_test
            )
            is False
        )


@pytest.mark.parametrize("filing_year", _MONTHLY_YEARS)
def test_january_is_not_a_transition_period(filing_year: int) -> None:
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        assert (
            transition_period_applicability_from_registry(
                Period.from_year_and_code(filing_year, "01"), operation=_authority_operation_for_test
            )
            is False
        )


@pytest.mark.parametrize(
    ("filing_year", "period_code"),
    _last_periods_of_editions_replaced_mid_year(),
)
def test_the_last_period_of_an_edition_replaced_mid_year_is_not_a_transition_period(
    filing_year: int, period_code: str
) -> None:
    """A mid-year edition declares only the periods it governs; the cadence ends in its successor."""
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        assert (
            transition_period_applicability_from_registry(
                Period.from_year_and_code(filing_year, period_code), operation=_authority_operation_for_test
            )
            is False
        )


def test_a_revision_without_a_periodic_carry_answers_nothing_rather_than_guessing() -> None:
    """The carry is the evidence; a revision holding none must not name a transition period."""
    revision = published_snapshot("390", filing_year=filing_grade_exercises("390")[-1], period="0A").revision

    assert periodic_carry_bindings_for_period(revision) == ()
