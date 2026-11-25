"""Legislative-decree references are notation; their neighboring prose is checked."""

from pathlib import Path

import pytest

from ..signal_spelling import spellcheck_catalogues
from ..signal_tokens import NUMBERED_ARTICLE_REFERENCE_RE, filtered_translation_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_complete_legislative_decree_reference_is_one_structural_span() -> None:
    assert filtered_translation_text("Read RDLeg 5/2004 misspeling") == ("Read misspeling", 1)


@pytest.mark.parametrize("word", ["RDLegg", "RDLeq", "rdleg", "xRDLeg"])
def test_misspelled_decree_abbreviation_is_not_hidden_by_its_citation_number(word: str) -> None:
    assert word in filtered_translation_text(f"Read {word} 5/2004 misspeling")[0]


def test_bare_decree_abbreviation_is_not_enrolled_as_vocabulary() -> None:
    assert filtered_translation_text("RDLeg misspeling") == ("RDLeg misspeling", 0)


def test_bis_is_structural_only_as_a_complete_numbered_article_suffix() -> None:
    assert filtered_translation_text("30 bis cikk misspeling") == ("cikk misspeling", 1)
    for text in ("bis", "30 biss", "R30 bis", "30bis", "30 bis-level"):
        assert NUMBERED_ARTICLE_REFERENCE_RE.search(text) is None
    assert filtered_translation_text("bis misspeling")[0] == "bis misspeling"


@pytest.mark.parametrize("locale", ["en", "es", "ca", "hu"])
def test_decree_reference_keeps_adjacent_spelling_errors_visible(locale: str, monkeypatch: pytest.MonkeyPatch) -> None:
    class Dictionary:
        def lookup(self, word: str) -> bool:
            return word == "Read"

    monkeypatch.setattr("dev.locales.signal_spelling.load_dictionaries", lambda repository: {locale: Dictionary()})
    spelling, inventory, _findings = spellcheck_catalogues(
        {"citation"}, {locale: {"citation": "Read RDLeg 5/2004 misspeling"}}, Path(".")
    )
    assert spelling[(locale, "citation")] == ("misspeling",)
    assert inventory["excluded_structural_tokens"] == 1
