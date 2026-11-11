"""The periods the desktop fixtures serve are what the ledger's period read answers.

The window does no period arithmetic: it shows the periods ``ledger.entry-options``
serves, from a recording the producer
``native/desktop/frontend/scripts/ledger_entry_options.py`` writes into the build tree. These tests ask
the committed period questions of the ledger's period read and hold its answers to the calendar.
"""

from __future__ import annotations

import pytest

from ....core.external_constants import OutputLanguage
from .entry_option_periods_recording_support import committed_questions, parse_questions, recorded_periods

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: The quarter and month each probe day falls in, worked from the calendar.
_QUARTER_AND_MONTH = {
    "2003-07-01": ("3T", "07"),
    "2024-02-29": ("1T", "02"),
    "2024-12-31": ("4T", "12"),
    "2025-01-01": ("1T", "01"),
    "2025-02-28": ("1T", "02"),
    "2026-03-31": ("1T", "03"),
    "2026-04-01": ("2T", "04"),
    "2026-10-15": ("4T", "10"),
    "2026-11-04": ("4T", "11"),
    "2026-12-31": ("4T", "12"),
}


def test_the_periods_answer_the_committed_reference_day_and_every_probe() -> None:
    questions = committed_questions()
    answered = recorded_periods(questions)

    assert answered["reference_day"] == questions.reference_day.isoformat()
    assert len(answered["probes"]["days"]) == len(questions.probe_days)
    assert len(answered["probes"]["covering"]) == len(questions.probe_spans)


def test_the_periods_name_every_committed_year_in_every_language() -> None:
    questions = committed_questions()
    answered = recorded_periods(questions)["years"]

    assert set(answered) == {language.value for language in OutputLanguage}
    for language, years in answered.items():
        wanted = questions.every_language_years
        if language == OutputLanguage.EN.value:
            wanted += questions.english_years
        assert set(years) == {str(year) for year in wanted}, language


def test_the_period_a_day_falls_in_is_what_the_calendar_says() -> None:
    answered = recorded_periods(committed_questions())

    assert answered["annual_code"] == "0A"
    containing = answered["containing"]
    assert (containing["day"], containing["quarterly"]["code"], containing["monthly"]["code"]) == (
        "2026-11-04",
        "4T",
        "11",
    )
    found = {
        probe["day"]: (probe["quarterly"]["code"], probe["monthly"]["code"]) for probe in answered["probes"]["days"]
    }
    assert found == _QUARTER_AND_MONTH
    for probe in answered["probes"]["days"]:
        assert probe["annual"] == {"filing_year": int(probe["day"][:4]), "code": "0A"}


def test_a_period_question_file_with_a_missing_key_is_refused() -> None:
    with pytest.raises(ValueError, match="exactly the keys"):
        parse_questions({"probe_days": []})
