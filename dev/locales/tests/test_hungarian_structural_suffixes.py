"""Hungarian endings retain stems and language ownership during segmentation."""

import pytest

from ..signal_spelling import spellcheck_catalogues
from ..signal_spelling_segments import hungarian_suffix_spelling_text, translation_spelling_segments

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def words_by_language(value: str, locale: str = "hu") -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for language, words, _excluded in translation_spelling_segments(value, "test", locale):
        result.setdefault(language, set()).update(words)
    return result


@pytest.mark.parametrize(
    "token",
    [
        "`core`-tól",
        "``core``-tól",
        "`previous_filing`-nek",
        "`counter-sign`-ból",
        "`1T`-től",
        "`4T`-ig",
        "`3T`-vel",
        "`0.21`-et",
        "IVA-jának",
        "IVA-jával",
        "PDF-jét",
        "PDF-jének",
        "UUID-jával",
        "NIF-jét",
        "NIF-jének",
        "URL-jét",
        "Cl@ve-vel",
        "Cl@ve-nél",
        "Modelo 111-et",
        "Modelo 100-ban",
        "**Modelo 349**-et",
        "Modelo 130-nál",
        "2025-02-03-tól",
        "1-jén",
        "{expected}-nek",
    ],
)
def test_attested_structural_stem_keeps_offsets_and_adjacent_words(token: str) -> None:
    value = f"{token} hibásszó"
    stem, suffix = token.rsplit("-", 1)
    masked, excluded = hungarian_suffix_spelling_text(value)

    assert len(masked) == len(value)
    assert masked.startswith(stem)
    assert masked.endswith("hibásszó")
    assert excluded == 1
    words = words_by_language(value)
    assert "hibásszó" in words["hu"]
    assert all(suffix not in segment for segment in words.values())


def test_hungarian_case_does_not_detach_from_spanish_form_before_language_routing() -> None:
    words = words_by_language("A Modelo 111-et hibásszó")

    assert words == {"hu": {"A", "hibásszó"}, "es": {"Modelo"}}


@pytest.mark.parametrize("language", ["en", "es", "ca"])
def test_explicit_foreign_language_inside_hungarian_prose_does_not_lose_its_suffix(language: str) -> None:
    words = words_by_language(f'<span lang="{language}">PDF-jét misspeling</span> hibásszó')

    assert words == {"hu": {"hibásszó"}, language: {"jét", "misspeling"}}


def test_explicit_hungarian_body_inside_english_prose_uses_hungarian_ending_rules() -> None:
    words = words_by_language('<span lang="hu">PDF-jét hibásszó</span> misspeling', "en")

    assert words == {"en": {"misspeling"}, "hu": {"hibásszó"}}


@pytest.mark.parametrize(
    "token,retained",
    [
        ("Censel-ről", "Censel"),
        ("PDF-jétx", "jétx"),
        ("Pdf-jét", "jét"),
        ("PDFF-jét", "jét"),
        ("UUID-jének", "jének"),
        ("word-jának", "jának"),
        ("1-jéén", "jéén"),
        ("2025-02-03-tóll", "tóll"),
        ("{expcted}-nek", "nek"),
        ("`core`-jét", "jét"),
        ("`core`-tóll", "tóll"),
        ("``core`-tól", "tól"),
        ("Modeloo 111-et", "Modeloo"),
    ],
)
def test_typo_stems_suffixes_unattested_pairs_and_markup_stay_checked(token: str, retained: str) -> None:
    words = words_by_language(f"{token} hibásszó")

    assert retained in words["hu"]
    assert "hibásszó" in words["hu"]


def test_suffix_fragments_are_not_enrolled_as_bare_words() -> None:
    assert words_by_language("nál ból jét jének vel nek") == {"hu": {"nál", "ból", "jét", "jének", "vel", "nek"}}


@pytest.mark.parametrize("token", ["word-nek", "Modelo111-et", "Modeloo 111-et", "PDF-jának", "{expcted}-nek"])
def test_unattested_stem_ending_combinations_are_not_normalized(token: str) -> None:
    assert hungarian_suffix_spelling_text(token) == (token, 0)


@pytest.mark.parametrize("locale", ["en", "es", "ca"])
@pytest.mark.parametrize("token,suffix", [("PDF-jét", "jét"), ("`1T`-től", "től")])
def test_new_hungarian_ending_handling_does_not_apply_to_other_languages(locale: str, token: str, suffix: str) -> None:
    words = words_by_language(token, locale)

    assert suffix in words[locale]


def test_dictionary_check_keeps_stem_ending_pair_case_and_foreign_language_findings(tmp_path, monkeypatch) -> None:
    class Dictionary:
        def __init__(self, known: set[str]) -> None:
            self.known = known

        def lookup(self, word: str) -> bool:
            return word in self.known

    monkeypatch.setattr(
        "dev.locales.signal_spelling.load_dictionaries",
        lambda _repository: {"hu": Dictionary(set()), "es": Dictionary({"Modelo"}), "en": Dictionary(set())},
    )
    leaves: dict[str, object] = {
        "valid": "Modelo 111-et hibásszó",
        "stem": "Censel-ről hibásszó",
        "ending": "PDF-jéét hibásszó",
        "case": "Pdf-jét hibásszó",
        "pair": "UUID-jének hibásszó",
        "foreign": '<span lang="en">PDF-jét misspeling</span> hibásszó',
    }
    spelling, _inventory, _findings = spellcheck_catalogues(set(leaves), {"hu": leaves}, tmp_path)

    assert {key: set(words) for (locale, key), words in spelling.items() if locale == "hu"} == {
        "valid": {"hibásszó"},
        "stem": {"Censel", "hibásszó"},
        "ending": {"jéét", "hibásszó"},
        "case": {"Pdf", "jét", "hibásszó"},
        "pair": {"jének", "hibásszó"},
        "foreign": {"jét", "misspeling", "hibásszó"},
    }
