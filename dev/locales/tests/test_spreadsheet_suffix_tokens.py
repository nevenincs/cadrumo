"""Dotted spreadsheet suffixes do not turn adjacent prose into syntax."""

from pathlib import Path

import pytest

from ..signal_spelling import spellcheck_catalogues
from ..signal_tokens import filtered_translation_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize("suffix", [".xlsx", ".csv"])
def test_complete_spreadsheet_suffix_is_one_structural_span(suffix: str) -> None:
    assert filtered_translation_text(f"Read {suffix} misspeling") == ("Read misspeling", 1)


@pytest.mark.parametrize("text", ["xlsx", "csv", ".xslx", ".xlsxx", ".cvs", ".csvx"])
def test_bare_names_and_suffix_typos_remain_visible(text: str) -> None:
    assert filtered_translation_text(text) == (text, 0)


@pytest.mark.parametrize("locale", ["en", "es", "ca", "hu"])
def test_spreadsheet_suffixes_do_not_hide_adjacent_spelling_errors(
    locale: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Dictionary:
        def lookup(self, word: str) -> bool:
            return word == "Read"

    monkeypatch.setattr("dev.locales.signal_spelling.load_dictionaries", lambda repository: {locale: Dictionary()})
    spelling, inventory, _findings = spellcheck_catalogues(
        {"export"}, {locale: {"export": "Read .xlsx .csv misspeling"}}, Path(".")
    )
    assert spelling[(locale, "export")] == ("misspeling",)
    assert inventory["excluded_structural_tokens"] == 2
