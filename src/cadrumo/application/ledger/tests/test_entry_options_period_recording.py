"""The periods the desktop fixtures serve are what the ledger's period read answers.

The window does no period arithmetic: it shows the periods ``ledger.entry-options``
serves, from a recording kept in the entry-options fixture. These tests hold that
recording to the committed period questions and to the backend's own projection.
The producer ``native/desktop/frontend/scripts/ledger_entry_options.py`` writes it;
these tests only read it.
"""

from __future__ import annotations

import json

import pytest

from ....core.external_constants import OutputLanguage
from .entry_option_periods_recording_support import (
    RECORDING,
    committed_questions,
    parse_questions,
    recorded_periods,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_the_recorded_periods_are_what_the_backend_answers() -> None:
    stored = json.loads(RECORDING.read_text(encoding="utf-8"))

    assert stored["periods"] == recorded_periods(committed_questions())


def test_the_recording_answers_the_committed_reference_day_and_every_probe() -> None:
    questions = committed_questions()
    stored = json.loads(RECORDING.read_text(encoding="utf-8"))["periods"]

    assert stored["reference_day"] == questions.reference_day.isoformat()
    assert len(stored["probes"]["days"]) == len(questions.probe_days)
    assert len(stored["probes"]["covering"]) == len(questions.probe_spans)


def test_the_recording_names_every_committed_year_in_every_language() -> None:
    questions = committed_questions()
    stored = json.loads(RECORDING.read_text(encoding="utf-8"))["periods"]

    assert set(stored["years"]) == {language.value for language in OutputLanguage}
    for language, years in stored["years"].items():
        wanted = questions.every_language_years
        if language == OutputLanguage.EN.value:
            wanted += questions.english_years
        assert set(years) == {str(year) for year in wanted}, language


def test_a_period_question_file_with_a_missing_key_is_refused() -> None:
    with pytest.raises(ValueError, match="exactly the keys"):
        parse_questions({"probe_days": []})
