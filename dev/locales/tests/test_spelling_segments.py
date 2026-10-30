"""Language ownership and structural notation in spelling input."""

from __future__ import annotations

import pytest

from ..signal_spelling_segments import locale_spelling_words, spanish_word_context, translation_spelling_segments

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


def test_hungarian_acronym_suffix_keeps_the_acronym_inside_existing_identifier_rules() -> None:
    segments = translation_spelling_segments("Az AEAT-nál hibásszó", "filing", "hu")
    assert segments == (("hu", ("Az", "hibásszó"), 2),)


@pytest.mark.parametrize(
    ("token", "stem", "suffix"),
    [
        ("Sede-ről", "Sede", "ről"),
        ("Censal-tól", "Censal", "tól"),
        ("036-os", "036", "os"),
        ("110-es", "110", "es"),
        ("115-ös", "115", "ös"),
        ("2022-től", "2022", "től"),
        ("2025-ös", "2025", "ös"),
    ],
)
def test_hungarian_hyphenated_suffix_preserves_stem_and_excludes_only_suffix(
    token: str, stem: str, suffix: str
) -> None:
    words, excluded = locale_spelling_words(f"{token} hibásszó", "hu")
    if stem.isalpha():
        assert stem in words
    assert suffix not in words
    assert "hibásszó" in words
    assert excluded >= 1


def test_hungarian_hyphenated_suffix_does_not_hide_a_misspelled_alphabetic_stem() -> None:
    words = words_by_language("Censel-ről hibásszó", "hu")["hu"]
    assert {"Censel", "hibásszó"} <= words


@pytest.mark.parametrize("token", ["40 %-os", "100%-ot", "50%-ban", "33%-ig", "33%-tól"])
def test_hungarian_percentage_suffix_is_structural_but_surrounding_prose_is_checked(token: str) -> None:
    words, excluded = locale_spelling_words(f"{token} hibásszó", "hu")
    assert "hibásszó" in words
    assert not {"os", "ot", "ban", "ig", "tól"}.intersection(words)
    assert excluded >= 1


@pytest.mark.parametrize("token", ["40%-oss", "100%-ott", "50%-bann", "33%-igg", "33%-tóll"])
def test_malformed_hungarian_percentage_suffix_remains_spelling_input(token: str) -> None:
    words = words_by_language(f"{token} hibásszó", "hu")["hu"]
    assert "hibásszó" in words
    assert token.rsplit("-", 1)[1] in words


def test_malformed_date_and_suffix_are_not_suppressed() -> None:
    words = words_by_language("ÉÉÉÉ-HH-NNx AEAT-náll hibásszó", "hu")["hu"]
    assert {"ÉÉÉÉ", "náll", "hibásszó"} <= words


@pytest.mark.parametrize(
    "token",
    ["Sede-rőlx", "Sede-röle", "Sede-röl", "036-öös", "2025-tőll"],
)
def test_unattested_or_malformed_hungarian_suffix_tokens_remain_spelling_input(token: str) -> None:
    words = words_by_language(f"{token} hibásszó", "hu")["hu"]
    assert "hibásszó" in words
    assert any(part in words for part in token.replace("-", " ").split())


def test_hungarian_notation_rules_do_not_apply_to_other_languages() -> None:
    assert "nál" in words_by_language("AEAT-nál")["en"]
    words = words_by_language("AEAT-tól AEAT-től 2025-ös", "en")["en"]
    assert {"tól", "től", "ös"} <= words


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


@pytest.mark.parametrize("locale", ["en", "ca", "hu"])
def test_exact_spanish_tax_terms_own_their_words_only(locale: str) -> None:
    assert words_by_language("Read bienes de inversión and casillas misspeling", locale) == {
        locale: {"Read", "and", "misspeling"},
        "es": {"bienes", "de", "inversión", "casillas"},
    }


def test_tax_term_prepositions_and_near_misses_stay_in_the_surrounding_language() -> None:
    assert words_by_language("de bienes de inversióm casillass misspeling") == {
        "en": {"de", "bienes", "inversióm", "casillass", "misspeling"},
    }


def test_hyphen_connected_spanish_tax_phrase_is_not_reassigned() -> None:
    assert words_by_language("pre-situación catastral") == {
        "en": {"pre", "situación", "catastral"},
    }


@pytest.mark.parametrize(
    "term",
    [
        "domiciliación bancaria",
        "cuenta corriente tributaria",
        "autoliquidación conjunta",
        "referencia catastral",
        "situación catastral",
        "Diseño de Registros",
        "consulta de declaraciones presentadas",
        "Fichero BOE",
        "CSV cotejo",
    ],
)
def test_exact_aeat_terms_in_english_ui_copy_are_checked_as_spanish(term: str) -> None:
    expected_spanish = set(term.split()) - {"BOE", "CSV"}
    assert words_by_language(f"Select {term} below") == {
        "en": {"Select", "below"},
        "es": expected_spanish,
    }


@pytest.mark.parametrize(
    "term",
    [
        "domiciliación bancariaa",
        "cuenta corriente tributariaa",
        "autoliquidación conjuntas",
        "referencia catastrala",
        "diseño de registrosx",
        "consulta de declaraciones presentadax",
        "fichero BOEx",
        "csv cotejoo",
        "situación catastrall",
    ],
)
def test_near_miss_aeat_terms_remain_english_spelling_input(term: str) -> None:
    assert words_by_language(f"Select {term} below") == {
        "en": {"Select", *term.split(), "below"},
    }


def test_exact_tax_terms_inside_literals_do_not_add_prose() -> None:
    assert words_by_language("Read `bienes de inversión` misspeling") == {"en": {"Read", "misspeling"}}


@pytest.mark.parametrize("name", ["Cl@ve", "Cl@ve Móvil", "Cl@ve PIN", "Cl@ve Permanente"])
def test_exact_clave_service_names_are_checked_as_spanish(name: str) -> None:
    words = words_by_language(f"Read {name} misspeling")
    assert words["en"] == {"Read", "misspeling"}
    assert "ve" in words["es"]


def test_misspelled_clave_service_names_keep_unknown_fragments() -> None:
    assert "Móvill" in words_by_language("Cl@ve Móvill misspeling")["en"]
    assert "Móvilx" in words_by_language("Cl@ve Móvilx misspeling")["en"]
    assert "Móvil" in words_by_language("Cl@vee Móvil misspeling")["en"]


def test_explicit_language_wins_over_exact_tax_term_recognition() -> None:
    assert words_by_language('<span lang="ca">casillas errror</span> misspeling') == {
        "en": {"misspeling"},
        "ca": {"casillas", "errror"},
    }


def test_hungarian_abbreviation_keeps_dictionary_significant_period() -> None:
    assert words_by_language("pl. hibásszó. pl hibásszó", "hu") == {
        "hu": {"pl.", "hibásszó.", "pl", "hibásszó"},
    }
