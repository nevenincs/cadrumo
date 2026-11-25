"""Every refusal reason of the suffered-withholding record operation has a sentence a frontend can show verbatim."""

from __future__ import annotations

import re
from typing import cast, get_args

import pytest

from cadrumo.application.retencion_soportada_certificado.contracts import (
    RETENCION_SOPORTADA_REVISION_REFUSAL_CODE,
    RETENCION_SOPORTADA_WRITE_REFUSAL_CODE,
    RetencionSoportadaCertificadoRefusalReason,
)
from cadrumo.application.retencion_soportada_certificado.refusal_words import served_refusal_words
from cadrumo.core.config import override_settings
from cadrumo.core.external_constants import OutputLanguage

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_REASONS = cast(
    tuple[RetencionSoportadaCertificadoRefusalReason, ...],
    get_args(RetencionSoportadaCertificadoRefusalReason.__value__),
)


def _code(reason: RetencionSoportadaCertificadoRefusalReason) -> str:
    if reason == "stale_revision":
        return RETENCION_SOPORTADA_REVISION_REFUSAL_CODE
    return RETENCION_SOPORTADA_WRITE_REFUSAL_CODE


def test_the_operation_has_fourteen_refusal_reasons() -> None:
    assert len(_REASONS) == 14


@pytest.mark.parametrize("language", list(OutputLanguage))
@pytest.mark.parametrize("reason", _REASONS)
def test_each_reason_serves_a_finished_sentence_that_names_no_command_option(
    reason: RetencionSoportadaCertificadoRefusalReason, language: OutputLanguage
) -> None:
    with override_settings(cadrumo_output_language=language.value):
        words, served_language = served_refusal_words(reason, error_code=_code(reason))

    assert served_language is language
    assert words.strip() == words
    assert len(words) > 20
    assert not re.search(r"\baggregation\.|\{|\}|%\(|--[a-z]", words)
    assert "SHA-256" not in words


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_the_sentences_of_one_language_are_all_different(language: OutputLanguage) -> None:
    with override_settings(cadrumo_output_language=language.value):
        sentences = {served_refusal_words(reason, error_code=_code(reason))[0] for reason in _REASONS}

    assert len(sentences) == len(_REASONS)
