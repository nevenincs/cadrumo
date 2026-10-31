"""English service names retain their exact public spellings."""

from collections import defaultdict

import pytest

from ..signal_spelling_enrollment import check_dictionary_spelling_words, is_project_spelling

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class EmptyDictionary:
    def lookup(self, word: str) -> bool:
        return False


@pytest.mark.parametrize(
    "name,typo",
    [
        ("DEHú", "DEHu"),
        ("Bizum", "Bizúm"),
        ("macOS", "MacOS"),
        ("Homebrew", "HomeBrew"),
        ("PyPI", "PyPi"),
        ("OpenSSL", "OpenSSl"),
        ("PowerShell", "Powershell"),
        ("Pagefind", "PageFind"),
    ],
)
def test_english_service_name_keeps_exact_case_accents_and_adjacent_spelling_checks(name: str, typo: str) -> None:
    assert is_project_spelling("en", name)
    for near_miss in (typo, name.lower(), name.upper(), name + "x"):
        assert not is_project_spelling("en", near_miss)

    cell = ("en", "application.test.key")
    unknown_words: set[tuple[str, str]] = set()
    unknown_by_cell: dict[tuple[str, str], set[str]] = defaultdict(set)
    check_dictionary_spelling_words(
        "en",
        {name: {cell}, typo: {cell}, "misspeling": {cell}},
        {"en": EmptyDictionary(), "es": EmptyDictionary()},
        {cell: f"{name} {typo} misspeling"},
        unknown_words,
        unknown_by_cell,
    )

    assert unknown_by_cell == {cell: {typo, "misspeling"}}
