"""Every refusal reason of the suffered-withholding absence operations has a sentence a frontend can show verbatim."""

from __future__ import annotations

import re
from typing import cast, get_args

import pytest

from cadrumo.application.retencion_soportada_absence.contracts import (
    RETENCION_SOPORTADA_ABSENCE_REFUSAL_CODE,
    RETENCION_SOPORTADA_ABSENCE_REVISION_REFUSAL_CODE,
    RetencionSoportadaAbsenceOperationRefusalReason,
)
from cadrumo.application.retencion_soportada_absence.refusal_words import served_absence_refusal_words
from cadrumo.core.config import override_settings
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.i18n.render import tr

_REASONS = cast(
    tuple[RetencionSoportadaAbsenceOperationRefusalReason, ...],
    get_args(RetencionSoportadaAbsenceOperationRefusalReason.__value__),
)
_CLI_PREFIX = "aggregation.retencion_soportada_absence.errors."


def _code(reason: RetencionSoportadaAbsenceOperationRefusalReason) -> str:
    if reason == "stale_revision":
        return RETENCION_SOPORTADA_ABSENCE_REVISION_REFUSAL_CODE
    return RETENCION_SOPORTADA_ABSENCE_REFUSAL_CODE


def test_the_operations_have_six_refusal_reasons() -> None:
    assert len(_REASONS) == 6


@pytest.mark.parametrize("language", list(OutputLanguage))
@pytest.mark.parametrize("reason", _REASONS)
def test_each_reason_serves_a_finished_sentence_that_names_no_command_option(
    reason: RetencionSoportadaAbsenceOperationRefusalReason, language: OutputLanguage
) -> None:
    with override_settings(cadrumo_output_language=language.value):
        words, served_language = served_absence_refusal_words(reason, error_code=_code(reason))

    assert served_language is language
    assert words.strip() == words
    assert len(words) > 20
    assert not re.search(r"\baggregation\.|\{|\}|%\(|--[a-z]", words)


@pytest.mark.parametrize("reason", _REASONS)
def test_a_served_sentence_is_not_the_command_lines_message_for_the_same_reason(
    reason: RetencionSoportadaAbsenceOperationRefusalReason,
) -> None:
    with override_settings(cadrumo_output_language="en"):
        words, _language = served_absence_refusal_words(reason, error_code=_code(reason))
        assert words != tr(_CLI_PREFIX + reason, locale="en")


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_the_sentences_of_one_language_are_all_different(language: OutputLanguage) -> None:
    with override_settings(cadrumo_output_language=language.value):
        sentences = {served_absence_refusal_words(reason, error_code=_code(reason))[0] for reason in _REASONS}

    assert len(sentences) == len(_REASONS)
