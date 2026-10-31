"""English software prose uses exact words without admitting typo families."""

from collections import defaultdict

import pytest

from ..signal_spelling_enrollment import check_dictionary_spelling_words, is_project_spelling

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class EmptyDictionary:
    def lookup(self, word: str) -> bool:
        return False


@pytest.mark.parametrize(
    "word,typo,case_miss",
    [
        ("Quickstart", "Quickstrat", "QuickStart"),
        ("quickstart", "quickstrat", "QuickStart"),
        ("subpackages", "subpackges", "Subpackages"),
        ("docstrings", "docstrngs", "Docstrings"),
        ("plaintext", "plaintexxt", "Plaintext"),
        ("decrypting", "decryping", "Decrypting"),
        ("decrypted", "decrypetd", "Decrypted"),
        ("schemas", "schmeas", "Schemas"),
        ("invariants", "invaraints", "Invariants"),
    ],
)
def test_software_word_keeps_spelling_case_locale_and_adjacent_prose_checked(
    word: str, typo: str, case_miss: str
) -> None:
    assert is_project_spelling("en", word)
    assert all(not is_project_spelling(locale, word) for locale in ("es", "ca", "hu"))
    for near_miss in (typo, case_miss, word.upper(), word + "x"):
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
