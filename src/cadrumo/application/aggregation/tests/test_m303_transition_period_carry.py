"""Transition-period applicability answers for every bundled Modelo 303 edition.

The last period of a Modelo 303 filing cadence carries the prorrata option and
revocation, and the official record design states the condition in exactly
those terms: "SI para el ultimo periodo (12 y 4T)". Both cadences are therefore
checked here, for every edition the bundled authority publishes, through the
registry rather than against a period list held in the code under test.

Modelo 303 files monthly only from the 2023 edition onwards, so the monthly
cases are asked of the years whose selected edition declares that cadence.
"""

from __future__ import annotations

import pytest

from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.bindings_previous_filing import periodic_carry_bindings_for_period
from ..m303_arrivals import _transition_period_applicability_from_registry

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: One filing context per bundled Modelo 303 edition, with the edition it selects.
_EDITION_CONTEXTS: tuple[tuple[int, str, str], ...] = (
    (2022, "1T", "2022"),
    (2023, "1T", "2023"),
    (2024, "1T", "2024-hasta-08-y-2t"),
    (2024, "3T", "2024-desde-09-y-3t"),
    (2025, "1T", "2025"),
    (2026, "1T", "2026-y-siguientes"),
)
#: Filing years whose Modelo 303 editions declare the quarterly cadence.
_QUARTERLY_YEARS: tuple[int, ...] = (2022, 2023, 2024, 2025, 2026)
#: Filing years whose Modelo 303 editions declare the monthly cadence.
_MONTHLY_YEARS: tuple[int, ...] = (2023, 2024, 2025, 2026)


@pytest.mark.parametrize(("filing_year", "period_code", "revision_id"), _EDITION_CONTEXTS)
def test_each_edition_is_selected_by_its_context(filing_year: int, period_code: str, revision_id: str) -> None:
    snapshot = bundled_authority().snapshot("303", filing_year=filing_year, period=period_code)

    assert snapshot.snapshot_ref.revision_id == revision_id


@pytest.mark.parametrize(("filing_year", "period_code", "revision_id"), _EDITION_CONTEXTS)
def test_every_edition_declares_the_periodic_carry_the_applicability_is_read_from(
    filing_year: int,
    period_code: str,
    revision_id: str,
) -> None:
    """The compensacion carry is what places a period in a recurring filing chain."""
    revision = bundled_authority().snapshot("303", filing_year=filing_year, period=period_code).revision

    carries = periodic_carry_bindings_for_period(revision)

    assert carries, revision_id
    assert "modelo-303-compensacion-pendiente-anteriores" in {str(binding.id) for binding, _ in carries}
    covered = {token for _binding, periods in carries for token in periods}
    assert covered == {token for schedule in revision.filing_schedules for token in schedule.periods}, revision_id


@pytest.mark.parametrize("filing_year", _QUARTERLY_YEARS)
def test_the_fourth_quarter_is_a_transition_period(filing_year: int) -> None:
    assert _transition_period_applicability_from_registry(Period.from_year_and_code(filing_year, "4T")) is True


@pytest.mark.parametrize("filing_year", _MONTHLY_YEARS)
def test_december_is_a_transition_period(filing_year: int) -> None:
    assert _transition_period_applicability_from_registry(Period.from_year_and_code(filing_year, "12")) is True


@pytest.mark.parametrize("filing_year", _QUARTERLY_YEARS)
def test_the_first_quarter_is_not_a_transition_period(filing_year: int) -> None:
    assert _transition_period_applicability_from_registry(Period.from_year_and_code(filing_year, "1T")) is False


@pytest.mark.parametrize("filing_year", _MONTHLY_YEARS)
def test_january_is_not_a_transition_period(filing_year: int) -> None:
    assert _transition_period_applicability_from_registry(Period.from_year_and_code(filing_year, "01")) is False


def test_a_revision_without_a_periodic_carry_answers_nothing_rather_than_guessing() -> None:
    """The carry is the evidence; a revision holding none must not name a transition period."""
    revision = bundled_authority().snapshot("390", filing_year=2025, period="0A").revision

    assert periodic_carry_bindings_for_period(revision) == ()
