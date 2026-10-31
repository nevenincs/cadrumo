"""Exact Spanish legal dictionary gaps retain their language boundaries."""

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
        ("enrutamiento", "enrutamieto"),
        ("deducibilidad", "deducibilidd"),
        ("transmitente", "trasmitentee"),
        ("transfronterizos", "transfronterisos"),
        ("plurianuales", "plurianualess"),
        ("autotaxis", "autotaxiss"),
        ("subclaves", "subclavess"),
        ("extracontables", "extracontabless"),
        ("registrales", "registraless"),
        ("reinversión", "reinversion"),
        ("aportante", "aportantee"),
        ("autoliquidar", "autoliquidár"),
        ("reutilizables", "reutilizabless"),
    ],
)
def test_exact_legal_vocabulary_and_adjacent_typo_keep_language_and_surface_boundaries(word: str, typo: str) -> None:
    assert is_project_spelling("es", word)
    for near_miss in (typo, word.capitalize(), word.upper()):
        assert not is_project_spelling("es", near_miss)
    assert all(not is_project_spelling(locale, word) for locale in ("en", "ca", "hu"))

    legal = "parallel:docs/_generated/legal/example.rst:line[5]:lang[en]"
    prose = "application.test.key"
    unknown_words: set[tuple[str, str]] = set()
    unknown_by_cell: dict[tuple[str, str], set[str]] = defaultdict(set)
    dictionaries = {"en": EmptyDictionary(), "es": EmptyDictionary()}
    check_dictionary_spelling_words(
        "en",
        {word: {("en", legal), ("en", prose)}, typo: {("en", legal)}},
        dictionaries,
        {("en", legal): f"{word} {typo}", ("en", prose): word},
        unknown_words,
        unknown_by_cell,
    )
    check_dictionary_spelling_words(
        "es",
        {word: {("es", prose)}, typo: {("es", prose)}},
        dictionaries,
        {("es", prose): f"{word} {typo}"},
        unknown_words,
        unknown_by_cell,
    )

    assert unknown_by_cell == {
        ("en", legal): {typo},
        ("en", prose): {word},
        ("es", prose): {typo},
    }
