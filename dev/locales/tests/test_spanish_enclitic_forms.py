"""Reviewed Spanish verb stems retain finite pronoun and accent boundaries."""

import unicodedata
from collections import defaultdict

import pytest

from cadrumo.core.i18n.render import tr

from ..signal_spelling_enrollment import (
    _spanish_reviewed_imperative,
    check_dictionary_spelling_words,
    is_project_spelling,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REVIEWED_FORMS = [
    "alinéalo",
    "aplázalo",
    "calcúlala",
    "combínalo",
    "comunícalo",
    "configúrala",
    "configúralo",
    "confírmalos",
    "consérvalo",
    "cópiala",
    "cópialo",
    "declárala",
    "desactívalo",
    "descárgalo",
    "desígnalas",
    "edítala",
    "edítalo",
    "elígelo",
    "gestiónalos",
    "guíalo",
    "impórtalos",
    "instálalo",
    "introdúcelo",
    "introdúcelos",
    "investígalos",
    "mantenlo",
    "muéstralo",
    "muéstralos",
    "márcalo",
    "nómbralo",
    "omítela",
    "omítelo",
    "preséntala",
    "previsualízalo",
    "quítalas",
    "quítalos",
    "reanúdala",
    "recargarlo",
    "reconciliarlos",
    "reconstrúyelos",
    "regístralas",
    "regístralo",
    "repítelo",
    "sepáralo",
    "termínala",
]
_REVIEWED_STEMS = [
    "alinéa",
    "apláza",
    "calcúla",
    "combína",
    "comuníca",
    "configúra",
    "confírma",
    "consérva",
    "cópia",
    "declára",
    "desactíva",
    "descárga",
    "desígna",
    "edíta",
    "elíge",
    "gestióna",
    "guía",
    "impórta",
    "instála",
    "introdúce",
    "investíga",
    "manten",
    "muéstra",
    "márca",
    "nómbra",
    "omíte",
    "presénta",
    "previsualíza",
    "quíta",
    "reanúda",
    "reconstrúye",
    "regístra",
    "repíte",
    "sepára",
    "termína",
]


class EmptyDictionary:
    def lookup(self, word: str) -> bool:
        return False


@pytest.mark.parametrize("word", _REVIEWED_FORMS)
def test_observed_forms_keep_language_case_and_adjacent_typo_checks(word: str) -> None:
    assert is_project_spelling("es", word)
    assert is_project_spelling("es", word.capitalize())
    assert not _spanish_reviewed_imperative(word.upper())
    assert not _spanish_reviewed_imperative(word[:2] + "x" + word[2:])
    assert all(not is_project_spelling(locale, word) for locale in ("en", "ca", "hu"))
    key = "application.test.prose"
    unknown_words: set[tuple[str, str]] = set()
    unknown_by_cell: dict[tuple[str, str], set[str]] = defaultdict(set)
    dictionaries = {locale: EmptyDictionary() for locale in ("en", "es", "ca", "hu")}
    for locale in dictionaries:
        check_dictionary_spelling_words(
            locale,
            {word: {(locale, key)}, "misspellledd": {(locale, key)}},
            dictionaries,
            {(locale, key): f"{word} misspellledd"},
            unknown_words,
            unknown_by_cell,
        )
    assert unknown_by_cell[("es", key)] == {"misspellledd"}
    for locale in ("en", "ca", "hu"):
        assert unknown_by_cell[(locale, key)] == {word, "misspellledd"}


@pytest.mark.parametrize("stem", [*_REVIEWED_STEMS, "recargar", "reconciliar"])
@pytest.mark.parametrize("suffix", ["lo", "la", "los", "las"])
def test_only_finite_direct_object_pronouns_attach_to_reviewed_stems(stem: str, suffix: str) -> None:
    assert _spanish_reviewed_imperative(stem + suffix)
    for bad_suffix in ("loo", "lass", "le", "les", "mente", "lós"):
        assert not _spanish_reviewed_imperative(stem + bad_suffix)
    assert not _spanish_reviewed_imperative("x" + stem + suffix)
    assert not _spanish_reviewed_imperative(stem.upper() + suffix)
    unaccented = "".join(c for c in unicodedata.normalize("NFD", stem) if unicodedata.category(c) != "Mn")
    if unaccented != stem:
        assert not _spanish_reviewed_imperative(unaccented + suffix)


@pytest.mark.parametrize(
    "word",
    [
        "casa",
        "casalo",
        "tablalo",
        "configurationlo",
        "registerlo",
        "descárguelo",
        "preséntela",
        "omítala",
        "manténlo",
        "reconstrúielos",
        "recargárlo",
        "reconciliárlos",
    ],
)
def test_unreviewed_words_and_wrong_stress_are_not_guessed(word: str) -> None:
    assert not _spanish_reviewed_imperative(word)


@pytest.mark.parametrize(
    "key,informal,formal",
    [
        ("application.live.notifications.errors.document_not_found", "Descárgalo", "Descárguelo"),
        ("application.modelo.work_form.finding_action.file_another_way", "Preséntala", "Preséntela"),
        ("cli.ledger.add.idempotency_key_help", "Omítela", "Omítala"),
    ],
)
def test_operator_instructions_use_informal_singular(key: str, informal: str, formal: str) -> None:
    rendered = tr(key, locale="es")
    assert informal in rendered
    assert formal not in rendered
