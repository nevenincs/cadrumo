"""Attested English spelling variants keep exact spelling and locale scope."""

from collections import defaultdict

import pytest

from ..signal_spelling_enrollment import check_dictionary_spelling_words, is_project_spelling

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class EmptyDictionary:
    def lookup(self, word: str) -> bool:
        return False


@pytest.mark.parametrize(
    "word,typo",
    [
        ("advisor", "advsior"),
        ("adapter", "adaptr"),
        ("adapters", "adpaters"),
        ("artifact", "artifcat"),
        ("amortization", "amortizaton"),
        ("proration", "proraton"),
        ("formalization", "formalizaton"),
        ("formalized", "formalizd"),
    ],
)
def test_exact_english_variant_does_not_admit_near_misses_casing_or_other_locales(word: str, typo: str) -> None:
    assert is_project_spelling("en", word)
    assert all(not is_project_spelling(locale, word) for locale in ("es", "ca", "hu"))
    for near_miss in (typo, word.capitalize(), word.upper(), word + "x"):
        assert not is_project_spelling("en", near_miss)

    cell = ("en", "application.test.key")
    unknown_words: set[tuple[str, str]] = set()
    unknown_by_cell: dict[tuple[str, str], set[str]] = defaultdict(set)
    check_dictionary_spelling_words(
        "en",
        {word: {cell}, typo: {cell}, "misspeling": {cell}},
        {"en": EmptyDictionary(), "es": EmptyDictionary()},
        {cell: f"{word} {typo} misspeling"},
        unknown_words,
        unknown_by_cell,
    )

    assert unknown_by_cell == {cell: {typo, "misspeling"}}
