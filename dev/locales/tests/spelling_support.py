"""Shared exact-spelling proof for the English vocabulary tests."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from ..signal_spelling_enrollment import check_dictionary_spelling_words, is_project_spelling


class EmptyDictionary:
    def lookup(self, word: str) -> bool:
        return False


def assert_exact_english_spelling(word: str, typo: str, near_misses: Iterable[str]) -> None:
    """The word is project spelling for English only; near misses and typos are not."""
    assert is_project_spelling("en", word)
    assert all(not is_project_spelling(locale, word) for locale in ("es", "ca", "hu"))
    for near_miss in near_misses:
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
