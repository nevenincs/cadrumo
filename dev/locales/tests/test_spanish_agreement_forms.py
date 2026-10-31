"""Finite Spanish agreement keeps native morphology and typo boundaries."""

import unicodedata

import pytest

from ..signal_spelling_enrollment import is_project_spelling
from ..signal_spelling_spanish_forms import is_reviewed_spanish_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_FORMS = [
    *[
        stem + ending
        for stem in ("tipad", "intracomunitari", "desactualizad", "malformad", "contrafirmad", "atómic")
        for ending in ("o", "a", "os", "as")
    ],
    *[
        stem + ending
        for stem, plural in (
            ("subcomando", "s"),
            ("reanudable", "s"),
            ("auditable", "s"),
            ("contrafirmante", "s"),
            ("exigibilidad", "es"),
            ("sobrescritura", "s"),
        )
        for ending in ("", plural)
    ],
    "previsualizar",
    "contrafirmar",
    "atómicamente",
    *[stem + ending for stem in ("apruéba", "reinténta", "lísta") for ending in ("lo", "la", "los", "las")],
]


@pytest.mark.parametrize("word", _FORMS)
def test_reviewed_native_forms_preserve_language_case_stem_and_ending(word: str) -> None:
    assert is_reviewed_spanish_form(word)
    assert is_project_spelling("es", word.capitalize())
    assert not is_reviewed_spanish_form(word.upper())
    assert not is_reviewed_spanish_form("x" + word)
    assert not is_reviewed_spanish_form(word + "x")
    assert not is_reviewed_spanish_form(word[:2] + "x" + word[2:])
    assert not is_reviewed_spanish_form(word[:-1] + "z")
    for locale in ("en", "ca", "hu"):
        # These two homographs were already enrolled in their own languages.
        assert is_project_spelling(locale, word) == ((locale, word) in {("en", "auditable"), ("ca", "tipada")})
    unaccented = "".join(c for c in unicodedata.normalize("NFD", word) if unicodedata.category(c) != "Mn")
    if unaccented != word:
        assert not is_reviewed_spanish_form(unaccented)


@pytest.mark.parametrize(
    "word",
    [
        "unico",
        "unica",
        "disposicion",
        "tipadó",
        "tipadases",
        "malformed",
        "typed",
        "intracommunitarios",
        "atomicamente",
        "atómicomente",
        "auditableses",
        "apruebalo",
    ],
)
def test_nearby_typos_foreign_prose_and_missing_legal_accents_remain_unknown(word: str) -> None:
    assert not is_reviewed_spanish_form(word)
