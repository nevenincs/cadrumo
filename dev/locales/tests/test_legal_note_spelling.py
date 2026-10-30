"""The generated legal-note spelling surface contains curated English and Spanish."""

from collections import defaultdict

import pytest

from ..signal_spelling_enrollment import check_dictionary_spelling_words

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class Dictionary:
    def __init__(self, accepted: set[str]) -> None:
        self.accepted = accepted

    def lookup(self, word: str) -> bool:
        return word in self.accepted


def check(word: str, key: str) -> tuple[set[tuple[str, str]], dict[tuple[str, str], set[str]]]:
    unknown_words: set[tuple[str, str]] = set()
    unknown_by_cell: dict[tuple[str, str], set[str]] = defaultdict(set)
    check_dictionary_spelling_words(
        "en",
        {word: {("en", key)}},
        {"en": Dictionary(set()), "es": Dictionary({"instrucción"})},
        {("en", key): f"source contains {word}"},
        unknown_words,
        unknown_by_cell,
    )
    return unknown_words, unknown_by_cell


def test_generated_legal_note_accepts_a_spanish_dictionary_word() -> None:
    unknown_words, unknown_by_cell = check(
        "instrucción", "parallel:docs/_generated/legal/boe-a-1992-28740.rst:line[4939]:lang[en]"
    )

    assert unknown_words == set()
    assert unknown_by_cell == {}


def test_generated_legal_note_still_reports_words_unknown_to_both_dictionaries() -> None:
    unknown_words, unknown_by_cell = check(
        "misspeling", "parallel:docs/_generated/legal/boe-a-1992-28740.rst:line[4939]:lang[en]"
    )

    assert unknown_words == {("en", "misspeling")}
    assert unknown_by_cell == {
        ("en", "parallel:docs/_generated/legal/boe-a-1992-28740.rst:line[4939]:lang[en]"): {"misspeling"}
    }


def test_ordinary_english_prose_does_not_get_spanish_dictionary_fallback() -> None:
    unknown_words, unknown_by_cell = check("instrucción", "application.test.key")

    assert unknown_words == {("en", "instrucción")}
    assert unknown_by_cell == {("en", "application.test.key"): {"instrucción"}}


def test_nonlegal_document_prose_does_not_get_spanish_dictionary_fallback() -> None:
    unknown_words, _unknown_by_cell = check("instrucción", "parallel:docs/how-to/file-at-aeat.rst:line[4939]:lang[en]")

    assert unknown_words == {("en", "instrucción")}
