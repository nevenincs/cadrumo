"""Every suffered-withholding income class resolves to a real label in every supported language."""

from __future__ import annotations

import pytest

from cadrumo.core.external_constants import OUTPUT_LANGUAGE_ENV_VAR
from cadrumo.core.i18n.render import clear_output_language_cache
from cadrumo.core.retencion_soportada import RetencionSoportadaClase
from cadrumo.core.retencion_soportada_label import RETENCION_SOPORTADA_CLASE_LABEL_KEYS, retencion_soportada_clase_label

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_LANGUAGES = ("en", "es", "ca", "hu")
_SPANISH_OFFICIAL_TERMS = {
    RetencionSoportadaClase.TRABAJO: "Rendimientos del trabajo",
    RetencionSoportadaClase.CAPITAL_MOBILIARIO: "Rendimientos del capital mobiliario",
    RetencionSoportadaClase.GANANCIA_PATRIMONIAL: "Ganancias patrimoniales",
}


@pytest.fixture
def output_language(monkeypatch: pytest.MonkeyPatch):
    def select(language: str) -> None:
        monkeypatch.setenv(OUTPUT_LANGUAGE_ENV_VAR, language)
        clear_output_language_cache()

    yield select
    monkeypatch.delenv(OUTPUT_LANGUAGE_ENV_VAR, raising=False)
    clear_output_language_cache()


def test_every_class_has_exactly_one_label_key() -> None:
    assert set(RETENCION_SOPORTADA_CLASE_LABEL_KEYS) == set(RetencionSoportadaClase)
    assert len(set(RETENCION_SOPORTADA_CLASE_LABEL_KEYS.values())) == len(RetencionSoportadaClase)


@pytest.mark.parametrize("language", _LANGUAGES)
def test_every_class_resolves_to_a_distinct_translated_label(language: str, output_language) -> None:
    output_language(language)
    labels = {income_class: retencion_soportada_clase_label(income_class) for income_class in RetencionSoportadaClase}
    assert len(set(labels.values())) == len(RetencionSoportadaClase)
    for income_class, label in labels.items():
        assert label.strip()
        assert label != RETENCION_SOPORTADA_CLASE_LABEL_KEYS[income_class]
        assert "retencion_soportada" not in label


def test_spanish_labels_use_the_official_renta_terms(output_language) -> None:
    output_language("es")
    for income_class, term in _SPANISH_OFFICIAL_TERMS.items():
        assert retencion_soportada_clase_label(income_class) == term
