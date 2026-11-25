"""Official province labels remain bound to their actual declared codes."""

from importlib.resources import files

import pytest
import yaml

from cadrumo.core.spanish_postcode import SPANISH_PROVINCE_CODES

from ..signal_spelling import spellcheck_catalogues
from ..signal_spelling_segments import is_known_official_province_label, official_province_labels_from_table

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize("locale", ("ca", "en", "es", "hu"))
def test_all_actual_choice_labels_match_the_official_code_pair(locale: str) -> None:
    source = files("cadrumo").joinpath("locales", locale, "application.yml").read_text(encoding="utf-8")
    catalogue = yaml.safe_load(source)
    choices = catalogue["application"]["modelo"]["edit_choice"]["province_code"]
    assert set(choices) == set(SPANISH_PROVINCE_CODES)
    for code, value in choices.items():
        key = f"application.modelo.edit_choice.province_code.{code}"
        assert is_known_official_province_label(key, value)
        assert not is_known_official_province_label(key, value + " typo")
        assert not is_known_official_province_label(key + ".extra", value)
    assert not is_known_official_province_label("application.modelo.edit_choice.province_code.03", choices["04"])
    assert not is_known_official_province_label("unrelated.prose", choices["03"])


def test_incomplete_or_ambiguous_official_source_is_refused() -> None:
    source = (
        files("cadrumo")
        .joinpath("_data", "corpus", "normatives", "html", "orden-eha-3481-2008.html.extracted.md")
        .read_text(encoding="utf-8")
    )
    assert len(official_province_labels_from_table(source)) == len(SPANISH_PROVINCE_CODES)
    for malformed in (source.replace("Albacete\n02\n", "", 1), source + source):
        with pytest.raises(ValueError):
            official_province_labels_from_table(malformed)


def test_spelling_exempts_only_the_verified_complete_choice(monkeypatch, tmp_path) -> None:
    class EmptyDictionary:
        def lookup(self, word: str) -> bool:
            return False

    monkeypatch.setattr(
        "dev.locales.signal_spelling.load_dictionaries",
        lambda _repository: {language: EmptyDictionary() for language in ("ca", "en", "es", "hu")},
    )
    choice = "application.modelo.edit_choice.province_code.03"
    values: dict[str, object] = {
        choice: "Alicante",
        "application.modelo.edit_choice.province_code.04": "Alicante",
        "other": "Alicante",
    }
    spelling, _, _ = spellcheck_catalogues(set(values), {"hu": values}, tmp_path)
    assert ("hu", choice) not in spelling
    assert spelling[("hu", "application.modelo.edit_choice.province_code.04")] == ("Alicante",)
    assert spelling[("hu", "other")] == ("Alicante",)
