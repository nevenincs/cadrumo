"""Area-unit notation leaves surrounding translated prose open to spelling."""

from pathlib import Path

import pytest

from ..signal_spelling import spellcheck_catalogues
from ..signal_tokens import filtered_translation_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_square_metre_symbol_is_one_structural_span() -> None:
    assert filtered_translation_text("Office area (m²) misspeling") == ("Office area ( ) misspeling", 1)


@pytest.mark.parametrize("text", ["xm²", "m²x", "m²²", "M²"])
def test_malformed_or_embedded_area_symbols_are_not_excluded(text: str) -> None:
    assert filtered_translation_text(text) == (text, 0)


@pytest.mark.parametrize("locale", ["en", "es", "ca", "hu"])
def test_area_notation_does_not_hide_a_neighboring_spelling_error(locale: str, monkeypatch: pytest.MonkeyPatch) -> None:
    class Dictionary:
        def lookup(self, word: str) -> bool:
            return word == "Area"

    monkeypatch.setattr("dev.locales.signal_spelling.load_dictionaries", lambda repository: {locale: Dictionary()})
    spelling, inventory, _findings = spellcheck_catalogues(
        {"area"}, {locale: {"area": "Area (m²) misspeling"}}, Path(".")
    )
    assert spelling[(locale, "area")] == ("misspeling",)
    assert inventory["excluded_structural_tokens"] == 1
