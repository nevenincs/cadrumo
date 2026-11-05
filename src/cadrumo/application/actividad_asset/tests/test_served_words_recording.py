"""The sentences the desktop fixtures serve for the register are what the register says.

The recording holds exactly the committed questions, and each recorded sentence is
the register's own in every language. The producer
``native/desktop/frontend/scripts/assets_served_words.py`` writes the recording; this
test only reads it.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from ....core.external_constants import OutputLanguage
from .served_words_recording_support import RECORDING, answers, committed_questions, parse_questions

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _recording() -> dict[str, Any]:
    return json.loads(RECORDING.read_text(encoding="utf-8"))


def test_the_recording_holds_exactly_the_committed_questions() -> None:
    questions = committed_questions()

    assert questions, "no question is committed"
    assert sorted(_recording()["entries"]) == sorted(questions)


def test_every_recorded_sentence_is_what_the_register_says() -> None:
    entries = _recording()["entries"]
    for question in committed_questions():
        assert entries[question] == answers(question), question


def test_a_recorded_question_names_a_language_for_every_supported_one() -> None:
    for question_text, said in _recording()["entries"].items():
        assert set(said) == {language.value for language in OutputLanguage}, question_text


def test_a_question_of_an_unknown_kind_is_refused() -> None:
    with pytest.raises(ValueError, match="unknown question kind"):
        answers('{"kind":"weather"}')


@pytest.mark.parametrize(
    ("lines", "refusal"),
    [
        (["[1]"], "JSON object"),
        (['{"kind":"partial","count":2}', '{"kind":"partial","count":2}'], "asked twice"),
    ],
)
def test_a_malformed_question_file_is_refused(lines: list[str], refusal: str) -> None:
    with pytest.raises(ValueError, match=refusal):
        parse_questions(lines)
