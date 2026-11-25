"""Every refusal of the capital-goods declaration serves a sentence a frontend can show verbatim."""

from __future__ import annotations

import re

import pytest

from cadrumo.application.bienes_inversion.refusal_words import served_refusal_words
from cadrumo.application.bienes_inversion.registered_contracts import BIENES_INVERSION_VALIDATION_REFUSAL_CODE
from cadrumo.core.config import override_settings
from cadrumo.core.external_constants import OutputLanguage

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _all_sentences() -> list[str]:
    code = BIENES_INVERSION_VALIDATION_REFUSAL_CODE
    return [
        served_refusal_words("validation", error_code=code)[0],
        served_refusal_words("disposal_incomplete", error_code=code, missing="year")[0],
        served_refusal_words("disposal_incomplete", error_code=code, missing="regime")[0],
        served_refusal_words("duplicate_identifier", error_code=code, identifier="BI-77")[0],
    ]


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_each_refusal_serves_a_finished_sentence_in_the_workers_language(language: OutputLanguage) -> None:
    with override_settings(cadrumo_output_language=language.value):
        sentences = _all_sentences()
        _words, served_language = served_refusal_words(
            "validation", error_code=BIENES_INVERSION_VALIDATION_REFUSAL_CODE
        )

    assert served_language is language
    assert len(set(sentences)) == 4
    for sentence in sentences:
        assert len(sentence) > 20
        assert not re.search(r"\bapplication\.|\{|\}|%\(", sentence)
    assert "BI-77" in sentences[3]
