"""Reviewed terminology spellings retain exact language, case and phrase bounds."""

from collections import defaultdict

import pytest

from cadrumo.domain.modelos.calculation_revision import CalculationRevisionState

from ..signal_spelling_enrollment import _known_latin_phrase_word, check_dictionary_spelling_words, is_project_spelling
from ..signal_spelling_segments import hungarian_suffix_spelling_text, translation_spelling_segments

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_WORDS = {
    "en": (
        "embeddings",
        "artifacts",
        "normalized",
        "indexable",
        "preprocessor",
        "preprocessors",
        "materializes",
        "redemptions",
        "regularization",
        "capitalization",
        "integrations",
    ),
    "es": (
        "autorrepercute",
        "superreducido",
        "transfronterizas",
        "indexador",
        "preprocesador",
        "preprocesadores",
        "terminológica",
    ),
    "ca": ("autorepercuteix",),
    "hu": (
        "artefaktumokból",
        "artefaktumba",
        "artefaktumok",
        "szabadfoglalkozásúak",
        "prorratából",
        "prorratát",
        "rentát",
        "recargo",
        "autónomos",
        "presentado",
    ),
}


@pytest.mark.parametrize("locale,word", [(locale, word) for locale, words in _WORDS.items() for word in words])
def test_reviewed_words_do_not_admit_near_misses_or_arbitrary_casing(locale: str, word: str) -> None:
    assert is_project_spelling(locale, word)
    assert not is_project_spelling(locale, word + "x")
    assert not is_project_spelling(locale, word.upper())


@pytest.mark.parametrize(
    "word,owner",
    [("preprocessor", "en"), ("preprocesador", "es"), ("autorepercuteix", "ca"), ("artefaktumokból", "hu")],
)
def test_native_word_gaps_remain_locale_specific(word: str, owner: str) -> None:
    for locale in ("en", "es", "ca", "hu"):
        assert is_project_spelling(locale, word) is (locale == owner)


@pytest.mark.parametrize("word", ["Pagefind", "Ceuta", "Melilla"])
def test_shared_proper_names_keep_their_actual_spelling(word: str) -> None:
    for locale in ("en", "es", "ca", "hu"):
        assert is_project_spelling(locale, word)
        assert not is_project_spelling(locale, word.lower())
        assert not is_project_spelling(locale, word + "x")


def test_presentado_is_the_actual_lifecycle_name() -> None:
    assert CalculationRevisionState.PRESENTADO.value == "presentado"


@pytest.mark.parametrize("suffix", ["lo", "la", "los", "las"])
def test_reviewed_indexar_infinitive_accepts_only_its_attested_grammatical_attachment(suffix: str) -> None:
    assert is_project_spelling("es", "indexar" + suffix)
    assert not is_project_spelling("es", "indexarr" + suffix)
    assert not is_project_spelling("es", "indexár" + suffix)
    assert not is_project_spelling("es", "indexar" + suffix + "x")


@pytest.mark.parametrize("phrase", ["ad hoc", "pro rata"])
def test_latin_words_require_the_complete_phrase_and_keep_code_separate(phrase: str) -> None:
    for word in phrase.split():
        assert _known_latin_phrase_word(phrase, word)
        assert not _known_latin_phrase_word(phrase.upper(), word)
        assert not _known_latin_phrase_word("x" + phrase, word)
        assert not _known_latin_phrase_word(phrase + "x", word)
        assert not _known_latin_phrase_word("`" + phrase + "` " + word, word)
        assert not _known_latin_phrase_word(word, word)
    assert not _known_latin_phrase_word(phrase + " misspellledd", "misspellledd")


class EmptyDictionary:
    def lookup(self, word: str) -> bool:
        return False


@pytest.mark.parametrize("locale", ["ca", "en", "es", "hu"])
def test_latin_recognition_preserves_adjacent_typos(locale: str) -> None:
    key = "application.example"
    unknown_words: set[tuple[str, str]] = set()
    unknown_by_cell: dict[tuple[str, str], set[str]] = defaultdict(set)
    check_dictionary_spelling_words(
        locale,
        {word: {(locale, key)} for word in ("ad", "hoc", "pro", "rata", "hooc", "rataa", "misspellledd")},
        {locale: EmptyDictionary()},
        {(locale, key): "ad hoc pro rata hooc rataa misspellledd"},
        unknown_words,
        unknown_by_cell,
    )
    assert unknown_by_cell[(locale, key)] == {"hooc", "rataa", "misspellledd"}


@pytest.mark.parametrize("locale", ["ca", "es", "hu"])
def test_full_english_system_name_is_still_dictionary_checked(locale: str) -> None:
    text = "VAT Information Exchange System misspellledd"
    segments = translation_spelling_segments(text, "application.example", locale)
    assert {"Information", "Exchange", "System"} <= {
        w for language, words, _ in segments if language == "en" for w in words
    }
    assert "misspellledd" in {w for language, words, _ in segments if language == locale for w in words}
    typo = translation_spelling_segments("VAT Informtion Exchange System", "application.example", locale)
    assert "Informtion" in {w for language, words, _ in typo if language == locale for w in words}
    literal = translation_spelling_segments(
        "`VAT Information Exchange System` misspellledd", "application.example", locale
    )
    assert not {"Information", "Exchange", "System"} & {w for _, words, _ in literal for w in words}
    explicit = translation_spelling_segments(
        '<span lang="es">VAT Information Exchange System</span>', "application.example", locale
    )
    assert "Information" in {w for language, words, _ in explicit if language == "es" for w in words}


@pytest.mark.parametrize("stem", ["IGIC", "IPSI"])
def test_only_reviewed_hungarian_tax_acronym_endings_are_structural(stem: str) -> None:
    masked, excluded = hungarian_suffix_spelling_text(stem + "-jére")
    assert masked.strip() == stem
    assert excluded == 1
    for text in (stem + "-jéree", stem + "X-jére", "word-jére"):
        masked, _ = hungarian_suffix_spelling_text(text)
        assert masked == text


def test_catalan_and_spanish_compound_spelling_are_not_confused() -> None:
    # IEC OIEC 2.4.2 gives autoretrat for the Catalan auto- + r convention:
    # https://oiec.iec.cat/textortografia/codi/2.4.2
    assert is_project_spelling("ca", "autorepercuteix")
    assert not is_project_spelling("ca", "autorrepercuteix")
    assert is_project_spelling("es", "autorrepercute")
    assert not is_project_spelling("es", "autorepercute")


@pytest.mark.parametrize("locale", ["en", "ca", "hu"])
def test_spanish_group_name_routes_every_word_without_admitting_components(locale: str) -> None:
    segments = translation_spelling_segments("grupo de entidades de IVA grupo entidades", "application.example", locale)
    assert {"grupo", "entidades"} <= {w for language, words, _ in segments if language == "es" for w in words}
    assert {"grupo", "entidades"} <= {w for language, words, _ in segments if language == locale for w in words}
    misspelled = translation_spelling_segments("grupo de entidaddes de IVA", "application.example", locale)
    assert "entidaddes" in {w for language, words, _ in misspelled if language == locale for w in words}


@pytest.mark.parametrize("prefix", ["simplified VAT regime", "objective-estimation"])
def test_modulos_is_spanish_only_in_the_complete_retained_regime_context(prefix: str) -> None:
    segments = translation_spelling_segments(prefix + " (módulos) módulos", "application.example", "en")
    assert "módulos" in {w for language, words, _ in segments if language == "es" for w in words}
    assert "módulos" in {w for language, words, _ in segments if language == "en" for w in words}
    for typo in ("modulos", "móduloss"):
        segments = translation_spelling_segments(prefix + " (" + typo + ")", "application.example", "en")
        assert typo in {w for language, words, _ in segments if language == "en" for w in words}
