"""Project vocabulary must not conceal unrecognised prose."""

from collections import defaultdict
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT
from dev.locales._spelling import load_dictionaries
from dev.locales.signal_spelling import spellcheck_catalogues
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


def test_only_english_possessives_of_exact_project_stems_are_accepted() -> None:
    assert is_project_spelling("en", "Cadrumo's")
    assert is_project_spelling("en", "modelo's")
    assert not is_project_spelling("en", "Cadrmu's")
    assert not is_project_spelling("en", "modeloo's")
    assert not is_project_spelling("en", "Cadrumo'd")
    assert not is_project_spelling("hu", "Cadrumo's")


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


def test_spanish_tax_terms_are_dictionary_checked_with_adjacent_prose(monkeypatch: pytest.MonkeyPatch) -> None:
    class Dictionary:
        def __init__(self, accepted: set[str]) -> None:
            self.accepted = accepted

        def lookup(self, word: str) -> bool:
            return word in self.accepted

    dictionaries = {"en": Dictionary({"Read"}), "es": Dictionary({"bienes", "de"})}
    monkeypatch.setattr("dev.locales.signal_spelling.load_dictionaries", lambda repository: dictionaries)
    spelling, inventory, _findings = spellcheck_catalogues(
        {"guide"}, {"en": {"guide": "Read bienes de inversión misspeling"}}, Path(".")
    )

    assert set(spelling[("en", "guide")]) == {"inversión", "misspeling"}
    assert inventory["spelling_unknown_words"] == 2


def test_hungarian_abbreviations_require_the_complete_dictionary_form(monkeypatch: pytest.MonkeyPatch) -> None:
    class Dictionary:
        def lookup(self, word: str) -> bool:
            return word == "pl."

    monkeypatch.setattr("dev.locales.signal_spelling.load_dictionaries", lambda repository: {"hu": Dictionary()})
    spelling, _inventory, _findings = spellcheck_catalogues({"guide"}, {"hu": {"guide": "pl. pl hibásszó."}}, Path("."))

    assert set(spelling[("hu", "guide")]) == {"pl", "hibásszó."}


def test_real_dictionaries_check_names_abbreviations_and_sentence_ends(monkeypatch: pytest.MonkeyPatch) -> None:
    dictionaries = load_dictionaries(REPO_ROOT)
    monkeypatch.setattr("dev.locales.signal_spelling.load_dictionaries", lambda repository: dictionaries)
    spelling, _inventory, _findings = spellcheck_catalogues(
        {"guide", "name", "typo"},
        {
            "hu": {"guide": "őket. sorok. összeget. pl. pl hibásszó."},
            "en": {"name": "Cl@ve Móvil misspeling", "typo": "Cl@ve Móvill Cl@vee Móvil"},
        },
        REPO_ROOT,
    )

    assert set(spelling[("hu", "guide")]) == {"pl", "hibásszó."}
    assert spelling[("en", "name")] == ("misspeling",)
    assert set(spelling[("en", "typo")]) == {"Móvill", "vee", "Móvil"}
