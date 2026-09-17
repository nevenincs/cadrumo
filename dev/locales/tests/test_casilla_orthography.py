"""Diacritic-loss detection over stored casilla values."""

from __future__ import annotations

import pytest

from dev.locales import casilla_orthography
from dev.locales.casilla_orthography import unaccented_words

pytestmark = [pytest.mark.hex_domain]

_KEY = "modelo.schema.100.casilla.continuidad.x.label"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("word", "table", "known", "expected"),
    [
        ("regimen", {"e": "é", "i": "í"}, {"régimen"}, ("régimen",)),
        ("anios", {"n": "ñ", "o": "ó"}, {"años"}, ("años",)),
        ("Codigo", {"o": "ó"}, {"Código"}, ("Código",)),
        ("tenyleges", {"e": "é"}, {"tényleges", "tényléges"}, ("tényleges", "tényléges")),
        ("sucesion", {"o": "ó"}, set(), ()),
    ],
)
def test_restorations_return_every_dictionary_form(
    word: str, table: dict[str, str], known: set[str], expected: tuple[str, ...]
) -> None:
    assert casilla_orthography._restorations(word, table, known.__contains__) == expected


@pytest.mark.integration
@pytest.mark.external_tool
def test_unaccented_words_are_reported_and_correct_text_is_not() -> None:
    values = {
        "es": {
            _KEY: "Régimen de estimación objetiva",
            "modelo.schema.100.casilla.continuidad.y.label": "Regimen de estimacion objetiva",
            "modelo.schema.100.casilla.continuidad.z.label": None,
        },
        "ca": {_KEY: "Identificacio del declarant"},
        "hu": {_KEY: "Az adózó személy azonosítása"},
    }

    found = {(item.locale, item.key, item.word): item.candidates for item in unaccented_words(values)}

    assert found == {
        ("es", "modelo.schema.100.casilla.continuidad.y.label", "Regimen"): ("Régimen",),
        ("es", "modelo.schema.100.casilla.continuidad.y.label", "estimacion"): ("estimación",),
        ("ca", _KEY, "Identificacio"): ("Identificació",),
    }


@pytest.mark.integration
@pytest.mark.external_tool
def test_a_reviewed_word_is_not_reported() -> None:
    values = {"es": {_KEY: "Regimen especial"}}

    assert {item.word for item in unaccented_words(values)} == {"Regimen"}
    found = {item.word for item in unaccented_words(values, reviewed={"es": frozenset({"Regimen"})})}

    assert found == set()


@pytest.mark.integration
@pytest.mark.external_tool
def test_quoted_identifiers_and_truncated_words_are_not_prose() -> None:
    values = {"es": {_KEY: "Ver contraparte.pais-codigo y m131-modulos-coeficientes; ejerci... Codigo"}}

    assert {item.word for item in unaccented_words(values)} == {"Codigo"}
