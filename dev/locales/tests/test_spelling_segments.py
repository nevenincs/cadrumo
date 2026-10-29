"""Language ownership and structural notation in spelling input."""

from __future__ import annotations

import pytest

from ..signal_spelling_segments import spanish_word_context, translation_spelling_segments

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def words_by_language(value: str, locale: str = "en") -> dict[str, set[str]]:
    """Collect each dictionary's prose without masking duplicate segments."""
    words: dict[str, set[str]] = {}
    for language, segment, _excluded in translation_spelling_segments(value, "guide", locale):
        words.setdefault(language, set()).update(segment)
    return words


@pytest.mark.parametrize("target", ["https://www.boe.es/example", "https://sede.agenciatributaria.gob.es/example"])
@pytest.mark.parametrize("markup", ["[{label}]({target})", "`{label} <{target}>`_"])
def test_authority_destination_preserves_english_label(target: str, markup: str) -> None:
    value = "See " + markup.format(label="Official guidance with misspeling", target=target)
    assert words_by_language(value) == {"en": {"See", "Official", "guidance", "with", "misspeling"}}


@pytest.mark.parametrize("markup", ["[{label}]({target})", "`{label} <{target}>`_"])
def test_spanish_official_label_routes_its_typos_to_spanish(markup: str) -> None:
    value = "Read " + markup.format(label="Ley 37/1992 de diciembree", target="https://www.boe.es/example")
    assert words_by_language(value) == {"en": {"Read"}, "es": {"Ley", "de", "diciembree"}}


def test_explicit_language_inside_link_controls_only_annotated_words() -> None:
    value = '[Read <span lang="es">texto errro</span> here](https://www.boe.es/example)'
    assert words_by_language(value) == {"en": {"Read", "here"}, "es": {"texto", "errro"}}


def test_english_legal_title_stays_english() -> None:
    assert words_by_language("Royal Decree 1/2026 guidance") == {"en": {"Royal", "Decree", "guidance"}}


@pytest.mark.parametrize("notation", ["ÉÉÉÉ-HH-NN", "ÉÉÉÉ-HH-NNTÓÓ:PP:MMZ"])
def test_hungarian_date_notation_excludes_structure_and_preserves_prose(notation: str) -> None:
    segments = translation_spelling_segments(f"Dátum ({notation}) hibásszó", "date", "hu")
    assert segments == (("hu", ("Dátum", "hibásszó"), 1),)


def test_hungarian_acronym_case_ending_does_not_become_a_word() -> None:
    segments = translation_spelling_segments("Az AEAT-nál hibásszó", "filing", "hu")
    assert segments == (("hu", ("Az", "hibásszó"), 1),)


def test_malformed_date_and_suffix_are_not_suppressed() -> None:
    words = words_by_language("ÉÉÉÉ-HH-NNx AEAT-náll hibásszó", "hu")["hu"]
    assert {"ÉÉÉÉ", "náll", "hibásszó"} <= words


def test_hungarian_notation_rules_do_not_apply_to_other_languages() -> None:
    assert "nál" in words_by_language("AEAT-nál")["en"]


def test_spanish_title_does_not_reassign_surrounding_english_typo() -> None:
    class Dictionary:
        def lookup(self, word: str) -> bool:
            return word == "Ley"

    assert not spanish_word_context(
        "Read Ley 37/1992 misspeling",
        "parallel:docs/_generated/legal/guide.rst:line[5]",
        "misspeling",
        owner_locale="en",
        dictionary=Dictionary(),
        spanish_dictionary=Dictionary(),
    )
