"""The sentences the desktop fixtures serve for the register are what the register says.

Each committed question is answered in every language. The producer
``native/desktop/frontend/scripts/assets_served_words.py`` records the answers into the build
tree; these tests ask the register the same questions directly.
"""

from __future__ import annotations

import json

import pytest

from ....core.external_constants import OutputLanguage
from .served_words_recording_support import answers, committed_questions, parse_questions

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_questions_are_committed() -> None:
    assert committed_questions(), "no question is committed"


def test_every_committed_question_is_answered_in_every_supported_language() -> None:
    for question in committed_questions():
        said = answers(question)
        assert set(said) == {language.value for language in OutputLanguage}, question
        if json.loads(question)["kind"] == "gap":
            assert all(said.values()), question


def test_a_gap_sentence_names_the_asset_the_span_and_the_amount_in_each_language() -> None:
    question = next(
        text
        for text in committed_questions()
        if (asked := json.loads(text))["kind"] == "gap"
        and asked["name"] == "Compresor de taller"
        and asked["covered_from"] == "2027-01-01"
    )

    said = answers(question)

    assert said["en"] is not None
    assert said["en"].startswith(
        "Modelo 100: Compresor de taller has no depreciation charge recorded from Jan 1, 2027 to Dec 31, 2027."
    )
    assert said["es"] is not None
    assert "Compresor de taller" in said["es"]
    assert "360,00" in said["es"]


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
