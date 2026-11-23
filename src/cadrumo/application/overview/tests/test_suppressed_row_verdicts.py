"""A held-off calendar row carries only a verdict the calendar serves a sentence for.

The read projects each held-off row with the worker's words for its verdict;
a row built with any other verdict failed the whole calendar read when it was
projected. It is refused where it is built instead.
"""

from datetime import date

import pytest

from ....core.period import Period
from ....domain.calculations.registry.applicability_models import ApplicabilityVerdict
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ..calendar_models import SuppressedCalendarEntry
from ..suppressed_verdict_words import SUPPRESSING_VERDICTS

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _row(verdict: ApplicabilityVerdict) -> SuppressedCalendarEntry:
    year = filing_year_envelope().horizon
    return SuppressedCalendarEntry(
        modelo="303",
        period=Period.from_year_and_code(year, "1T"),
        opens_on=date(year, 4, 1),
        closes_on=date(year, 4, 20),
        adjusted_closes_on=date(year, 4, 20),
        verdict=verdict,
        reason="undecided",
    )


@pytest.mark.parametrize("verdict", sorted(set(ApplicabilityVerdict) - SUPPRESSING_VERDICTS, key=str))
def test_a_held_off_row_refuses_a_verdict_it_has_no_sentence_for(verdict: ApplicabilityVerdict) -> None:
    with pytest.raises(ValueError, match="holds nothing off the schedule"):
        _row(verdict)


@pytest.mark.parametrize("verdict", sorted(SUPPRESSING_VERDICTS, key=str))
def test_a_held_off_row_accepts_every_verdict_with_a_sentence(verdict: ApplicabilityVerdict) -> None:
    assert _row(verdict).verdict is verdict
