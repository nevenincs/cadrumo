"""The questions the desktop's staged-check recording asks are answered as the check's rules say.

The questions are committed in ``dev/fixtures/ledger-staged-check-questions``; the producer
``native/desktop/frontend/scripts/ledger_staged_check.py`` records the answers into the build tree, and
these tests ask the check the same questions directly.
"""

from __future__ import annotations

import json

import pytest

from ....core.external_constants import OutputLanguage
from .staged_check_recording_support import (
    absent_answer,
    committed_questions,
    draft_answer,
    parse_questions,
    row_answer,
    served_words,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]


def test_questions_of_both_kinds_are_committed() -> None:
    questions = committed_questions()

    assert questions.rows, "no row question is committed"
    assert questions.drafts, "no draft question is committed"


def test_every_committed_row_question_is_answered_as_found_or_refused_with_a_blocker_list() -> None:
    for question in committed_questions().rows:
        answer = row_answer(question)
        assert answer["found"] is True, question
        assert isinstance(answer["blockers"], list), question


def test_a_personal_active_row_is_classified_and_skips_the_tax_set_as_personal() -> None:
    personal = next(
        question
        for question in committed_questions().rows
        if json.loads(question)["stored"]["business_classification"] == "PERSONAL"
        and json.loads(question)["lifecycle"] == "ACTIVE"
    )

    answer = row_answer(personal)

    assert (answer["classified"], answer["tax_set_skip"], answer["blockers"]) == (True, "personal", [])


def test_an_empty_draft_is_incomplete_in_the_five_fields_a_movement_needs_and_a_full_one_is_not() -> None:
    empty = draft_answer("[]")
    assert [(blocker["kind"], sorted(blocker["fields"])) for blocker in empty["blockers"]] == [
        ("draft_incomplete", ["amount", "booked_date", "currency", "description", "direction"])
    ]
    full = next(
        question
        for question in committed_questions().drafts
        if {entry["field"] for entry in json.loads(question)}
        >= {"amount", "booked_date", "currency", "description", "direction"}
    )
    assert "draft_incomplete" not in {blocker["kind"] for blocker in draft_answer(full)["blockers"]}


def test_the_served_sentences_name_every_language_for_every_kind() -> None:
    languages = {language.value for language in OutputLanguage}
    for kind, said in served_words()["blockers"].items():
        assert set(said) == languages, kind
        assert all(sentence["words"] and sentence["fix_words"] for sentence in said.values()), kind


def test_an_absent_row_is_answered_as_not_found() -> None:
    answer = absent_answer()

    assert answer["found"] is False
    assert answer["blockers"] == []


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
