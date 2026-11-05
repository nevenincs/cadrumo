"""The desktop fixtures' recorded staged-check answers stay what the backend answers.

The recording holds exactly the committed questions, and each recorded answer is
what ``ledger.staged.check`` answers now. The producer
``native/desktop/frontend/scripts/ledger_staged_check.py`` writes the recording; this
test only reads it.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from .staged_check_recording_support import (
    RECORDING,
    absent_answer,
    committed_questions,
    draft_answer,
    parse_questions,
    row_answer,
    served_words,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]


def _recording() -> dict[str, Any]:
    return json.loads(RECORDING.read_text(encoding="utf-8"))


def test_the_recording_holds_exactly_the_committed_questions() -> None:
    questions = committed_questions()
    recording = _recording()

    assert questions.rows, "no row question is committed"
    assert questions.drafts, "no draft question is committed"
    assert sorted(recording["rows"]) == sorted(questions.rows)
    assert sorted(recording["drafts"]) == sorted(questions.drafts)


def test_every_recorded_answer_is_what_the_backend_answers() -> None:
    recording = _recording()
    assert recording["absent"] == absent_answer()
    for question in committed_questions().rows:
        assert recording["rows"][question] == row_answer(question), question


def test_the_recorded_sentences_are_what_the_backend_says_in_every_language() -> None:
    assert _recording()["words"] == served_words()


def test_every_recorded_draft_is_what_the_backend_answers() -> None:
    recording = _recording()
    for question in committed_questions().drafts:
        assert recording["drafts"][question] == draft_answer(question), question


def test_an_absent_row_is_answered_as_not_found() -> None:
    assert absent_answer()["found"] is False


@pytest.mark.parametrize(
    ("lines", "refusal"),
    [
        (['{"kind":"cell","question":"[]"}'], "row or draft"),
        (['{"kind":"draft"}'], "row or draft"),
        (['{"kind":"draft","question":"[]"}', '{"kind":"draft","question":"[]"}'], "asked twice"),
    ],
)
def test_a_malformed_question_file_is_refused(lines: list[str], refusal: str) -> None:
    with pytest.raises(ValueError, match=refusal):
        parse_questions(lines)


def test_question_lines_keep_their_kind_and_exact_text() -> None:
    parsed = parse_questions(['{"kind":"draft","question":"[]"}', "", '{"kind":"row","question":"{\\"a\\":1}"}'])

    assert parsed.drafts == ("[]",)
    assert parsed.rows == ('{"a":1}',)
