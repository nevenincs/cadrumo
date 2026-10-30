"""Word boundaries preserve dictionary input without concealing misspellings."""

from __future__ import annotations

import pytest

from cadrumo.core.i18n.render import tr

from ..signal_spelling_segments import _CATALAN_HYPHENATED_CLITIC_RE, locale_spelling_words
from ..signal_tokens import filtered_translation_text, translation_words

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_catalan_middle_dot_stays_in_dictionary_words_and_typos() -> None:
    words, excluded = locale_spelling_words("La instal·lació del col·legi conté instal·laciò", "ca")
    assert words == ("La", "instal·lació", "del", "col·legi", "conté", "instal·laciò")
    assert excluded == 0
    assert translation_words("instal·lació col·legi") == ("instal·lació", "col·legi")


@pytest.mark.parametrize("apostrophe", ["'", "’"])
def test_english_contractions_and_possessives_reach_dictionary_whole(apostrophe: str) -> None:
    value = f"You{apostrophe}ve read the taxpayer{apostrophe}s misspeling and taxpayre{apostrophe}s record."
    words, excluded = locale_spelling_words(value, "en")
    assert words == ("You've", "read", "the", "taxpayer's", "misspeling", "and", "taxpayre's", "record")
    assert excluded == 0


def test_catalan_elisions_still_expose_the_lexical_word() -> None:
    assert locale_spelling_words("l'instal·lació d'un col·legi", "ca") == (
        ("l", "instal·lació", "d", "un", "col·legi"),
        0,
    )


@pytest.mark.parametrize(
    ("value", "host"),
    [("Mantén-lo", "Mantén"), ("revisar-los", "revisar")],
)
def test_catalan_hyphenated_clitics_keep_the_host_as_dictionary_input(value: str, host: str) -> None:
    assert locale_spelling_words(value, "ca") == ((host,), 1)


@pytest.mark.parametrize("value", ["-ne", "-lo"])
def test_bare_or_malformed_catalan_clitics_are_not_silently_excluded(value: str) -> None:
    words, excluded = locale_spelling_words(value, "ca")
    assert excluded == 0
    assert words


@pytest.mark.parametrize("value", ["Manténn-lo", "revisarr-los", "Mantén-los", "revisar-lo"])
def test_unattested_catalan_clitic_forms_do_not_match_the_closed_exception(value: str) -> None:
    assert _CATALAN_HYPHENATED_CLITIC_RE.subn(lambda match: match.group("form").split("-")[0], value)[1] == 0


def test_catalan_clitic_exception_does_not_apply_to_other_locales() -> None:
    assert locale_spelling_words("Mantén-lo", "ca") == (("Mantén",), 1)
    assert locale_spelling_words("Mantén-lo", "es") != (("Mantén",), 1)


def test_acronym_masking_preserves_entire_mixed_case_prose_words() -> None:
    filtered, excluded = filtered_translation_text("OAuth OAUth misspeling AEAT MODE=fast API_KEY")
    assert filtered == "OAuth OAUth misspeling"
    assert excluded == 3


def test_identifiers_remain_excluded_while_malformed_tokens_and_typos_are_visible() -> None:
    words, excluded = locale_spelling_words(
        "base_total module.member A_0_0 code123 one-two-three a_0_é OAé misspeling",
        "es",
    )
    assert words == ("a", "é", "OAé", "misspeling")
    assert excluded == 5


def test_quotes_and_punctuation_do_not_join_neighboring_words() -> None:
    assert locale_spelling_words("'You've' read 'words'; taxpayer's, misspeling.", "en") == (
        ("You've", "read", "words", "taxpayer's", "misspeling"),
        0,
    )


def test_unicode_cli_options_are_excluded_as_a_whole() -> None:
    assert filtered_translation_text("Use --año and --modelo.") == ("Use and .", 2)


def test_english_amend_wizard_prompt_renders_line_breaks() -> None:
    rendered = tr(
        "cli.app.modelo.work.amend_wizard_select_prompt",
        modelo="303",
        year="2025",
        period="1T",
        summary="Box 01",
        locale="en",
    )
    assert rendered == (
        "Recorded as filed: 303 2025 1T,\ncurrent values:\nBox 01\n"
        "Which box numbers changed? (comma/space separated, blank for none)"
    )
