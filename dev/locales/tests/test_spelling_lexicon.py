"""Project vocabulary must not conceal unrecognised prose."""

from collections import defaultdict

import pytest

from dev.locales.signal_spelling_enrollment import check_dictionary_spelling_words, is_project_spelling

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_project_spelling_is_exact_and_language_scoped() -> None:
    for locale in ("ca", "en", "es", "hu"):
        assert is_project_spelling(locale, "Cadrumo")
        assert is_project_spelling(locale, "AEAT")
        assert not is_project_spelling(locale, "Cadrmu")
    for locale in ("en", "hu"):
        assert is_project_spelling(locale, "modelo")
        assert is_project_spelling(locale, "Modelo")
        assert not is_project_spelling(locale, "modello")
    assert not is_project_spelling("ca", "modelo")


def test_spelling_enrollment_preserves_unknown_words() -> None:
    class EmptyDictionary:
        def lookup(self, word: str) -> bool:
            return False

    words = {word: {("en", "test.key")} for word in ("Cadrumo", "modelo", "reciept")}
    unknown_words: set[tuple[str, str]] = set()
    unknown_by_cell: dict[tuple[str, str], set[str]] = defaultdict(set)
    check_dictionary_spelling_words(
        "en",
        words,
        {"en": EmptyDictionary(), "es": EmptyDictionary()},
        {("en", "test.key"): "Cadrumo modelo reciept"},
        unknown_words,
        unknown_by_cell,
    )
    assert unknown_words == {("en", "reciept")}
    assert unknown_by_cell == {("en", "test.key"): {"reciept"}}
