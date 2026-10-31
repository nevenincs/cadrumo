"""Retained Spanish labels keep complete boundaries and dictionary checks."""

import re

import pytest

from ..signal_spelling import spellcheck_catalogues
from ..signal_spelling_segments import translation_spelling_segments

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def words_by_language(value: str, locale: str = "en") -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for language, words, _excluded in translation_spelling_segments(value, "guide", locale):
        result.setdefault(language, set()).update(words)
    return result


@pytest.mark.parametrize("locale", ["en", "ca", "hu"])
@pytest.mark.parametrize(
    "label",
    [
        "base imponible",
        "base liquidable",
        "cuota devengada",
        "régimen general",
        "régimen-general",
        "régimen simplificado",
        "régimen de atribución",
        "régimen-de-atribución",
        "Registro Civil",
        "Registro de Operadores Intracomunitarios",
        "Registro de Devolución Mensual",
        "Registro Especial de Buques y Empresas Navieras de Canarias",
    ],
)
def test_complete_labels_route_only_their_words_to_spanish(locale: str, label: str) -> None:
    words = words_by_language(f"outside {label} misspeling", locale)

    assert words[locale] == {"outside", "misspeling"}
    assert words["es"] == set(re.findall(r"[^\W\d_]+", label))


@pytest.mark.parametrize(
    "value,typo",
    [
        ("base imponiblex", "imponiblex"),
        ("baseliquidable", "baseliquidable"),
        ("cuota devengadaa", "devengadaa"),
        ("régimen-generalx", "generalx"),
        ("régimen simplificaddo", "simplificaddo"),
        ("régimen-de-atribucíon", "atribucíon"),
        ("régimen deatribución", "deatribución"),
        ("Registro Civill", "Civill"),
        ("registro Civil", "registro"),
        ("Registro de Operadores Intracomunitariosx", "Intracomunitariosx"),
    ],
)
def test_misspelled_incomplete_and_unattested_case_labels_remain_in_the_owner_language(value: str, typo: str) -> None:
    words = words_by_language(value)

    assert typo in words["en"]
    assert "es" not in words


def test_component_words_do_not_become_spanish_prose_exemptions() -> None:
    value = "base, imponible; liquidable; cuota; devengada; régimen; general; simplificado; atribución; Registro; Civil"

    assert words_by_language(value, "hu") == {"hu": set(re.findall(r"[^\W\d_]+", value))}


@pytest.mark.parametrize("language", ["en", "ca"])
def test_explicit_language_takes_precedence_over_automatic_label_routing(language: str) -> None:
    words = words_by_language(f'<span lang="{language}">cuota devengada</span> misspeling', "hu")

    assert words == {"hu": {"misspeling"}, language: {"cuota", "devengada"}}


@pytest.mark.parametrize("label", ["régimen general", "Registro Civil"])
def test_literal_code_label_stays_structural(label: str) -> None:
    assert words_by_language(f"Known `{label}` misspeling") == {"en": {"Known", "misspeling"}}


def test_matched_label_still_requires_spanish_dictionary_recognition(tmp_path, monkeypatch) -> None:
    class Dictionary:
        def __init__(self, known: set[str]) -> None:
            self.known = known

        def lookup(self, word: str) -> bool:
            return word in self.known

    monkeypatch.setattr(
        "dev.locales.signal_spelling.load_dictionaries",
        lambda _repository: {"en": Dictionary({"Known"}), "es": Dictionary({"devengada"})},
    )
    spelling, _inventory, _findings = spellcheck_catalogues(
        {"guide"}, {"en": {"guide": "Known cuota devengada misspeling"}}, tmp_path
    )

    # cuota is an enrolled English loanword. Its Spanish label ownership must
    # still require the Spanish dictionary, even if that dictionary rejects it.
    assert set(spelling[("en", "guide")]) == {"cuota", "misspeling"}
