"""The generated legal-note spelling surface contains curated English and Spanish."""

from collections import defaultdict

import pytest

from ..signal_spelling_enrollment import check_dictionary_spelling_words, is_project_spelling

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class Dictionary:
    def __init__(self, accepted: set[str]) -> None:
        self.accepted = accepted

    def lookup(self, word: str) -> bool:
        return word in self.accepted


def check(word: str, key: str, locale: str = "en") -> tuple[set[tuple[str, str]], dict[tuple[str, str], set[str]]]:
    unknown_words: set[tuple[str, str]] = set()
    unknown_by_cell: dict[tuple[str, str], set[str]] = defaultdict(set)
    check_dictionary_spelling_words(
        locale,
        {word: {(locale, key)}},
        {"en": Dictionary(set()), "es": Dictionary({"instrucción"}), "hu": Dictionary(set())},
        {(locale, key): f"source contains {word}"},
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


@pytest.mark.parametrize(
    "word",
    [
        "Minoración",
        "intracomunitaria",
        "intracomunitarias",
        "intracomunitario",
        "recapitulativa",
        "impatriados",
        "subclave",
        "bloqueantes",
        "registral",
        "fiscalmente",
    ],
)
def test_bilingual_legal_reference_accepts_exact_reviewed_spanish_vocabulary(word: str) -> None:
    assert is_project_spelling("es", word)
    unknown_words, unknown_by_cell = check(word, "parallel:docs/_generated/legal/example.rst:line[5]:lang[en]")

    assert unknown_words == set()
    assert unknown_by_cell == {}


@pytest.mark.parametrize(
    "word", ["intracomunitarías", "recapitulativaa", "MINORACIÓN", "Intracomunitarias", "modificacion"]
)
def test_legal_vocabulary_fallback_preserves_typos_case_and_literal_id_findings(word: str) -> None:
    key = "parallel:docs/_generated/legal/example.rst:line[5]:lang[en]"
    unknown_words, unknown_by_cell = check(word, key)

    assert unknown_words == {("en", word.casefold())}
    assert unknown_by_cell == {("en", key): {word}}


@pytest.mark.parametrize(
    "key,locale",
    [
        ("application.test.key", "en"),
        ("parallel:docs/how-to/example.rst:line[5]", "en"),
        ("parallel:docs/_generated/legal/example.rst:description", "en"),
        ("parallel:docs/_generated/legal/example.rst:line[5]", "hu"),
    ],
)
def test_reviewed_spanish_legal_vocabulary_keeps_existing_surface_and_language_boundary(key: str, locale: str) -> None:
    unknown_words, unknown_by_cell = check("intracomunitarias", key, locale)

    assert unknown_words == {(locale, "intracomunitarias")}
    assert unknown_by_cell == {(locale, key): {"intracomunitarias"}}


def test_shared_word_retains_nonlegal_finding_and_adjacent_legal_typo() -> None:
    legal = "parallel:docs/_generated/legal/example.rst:line[5]:lang[en]"
    runtime = "application.test.key"
    unknown_words: set[tuple[str, str]] = set()
    unknown_by_cell: dict[tuple[str, str], set[str]] = defaultdict(set)

    check_dictionary_spelling_words(
        "en",
        {"intracomunitarias": {("en", legal), ("en", runtime)}, "intracomunitarías": {("en", legal)}},
        {"en": Dictionary(set()), "es": Dictionary(set())},
        {("en", legal): "intracomunitarias intracomunitarías", ("en", runtime): "intracomunitarias"},
        unknown_words,
        unknown_by_cell,
    )

    assert unknown_words == {("en", "intracomunitarias"), ("en", "intracomunitarías")}
    assert unknown_by_cell == {("en", legal): {"intracomunitarías"}, ("en", runtime): {"intracomunitarias"}}
