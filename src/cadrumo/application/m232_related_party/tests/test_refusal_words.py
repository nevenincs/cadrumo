"""Every refusal reason of the Modelo 232 related-party operations has a sentence a frontend can show verbatim."""

from __future__ import annotations

import re
from typing import cast, get_args

import pytest

from ....core.config import override_settings
from ....core.external_constants import OutputLanguage
from ...aggregation.m232_related_party_repository import Modelo232RefusalReason
from ..contracts import (
    M232_RELATED_PARTY_REFUSAL_CODE,
    M232_RELATED_PARTY_REVISION_REFUSAL_CODE,
    Modelo232RelatedPartyOperationRefusalReason,
)
from ..refusal_words import served_m232_related_party_refusal_words

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_REASONS = cast(
    tuple[Modelo232RelatedPartyOperationRefusalReason, ...],
    get_args(Modelo232RelatedPartyOperationRefusalReason.__value__),
)


def _code(reason: Modelo232RelatedPartyOperationRefusalReason) -> str:
    return M232_RELATED_PARTY_REVISION_REFUSAL_CODE if reason == "stale_revision" else M232_RELATED_PARTY_REFUSAL_CODE


def test_the_operations_serve_every_reason_of_the_write_path_and_their_own() -> None:
    assert set(_REASONS) == {*get_args(Modelo232RefusalReason.__value__), "stale_revision", "validation"}


@pytest.mark.parametrize("language", list(OutputLanguage))
@pytest.mark.parametrize("reason", _REASONS)
def test_each_reason_serves_a_finished_sentence_that_names_no_command_option(
    reason: Modelo232RelatedPartyOperationRefusalReason, language: OutputLanguage
) -> None:
    with override_settings(cadrumo_output_language=language.value):
        words, served_language = served_m232_related_party_refusal_words(reason, error_code=_code(reason))

    assert served_language is language
    assert words.strip() == words
    assert len(words) > 20
    assert not re.search(r"\baggregation\.|\{|\}|%\(|--[a-z]", words)


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_the_sentences_of_one_language_are_all_different(language: OutputLanguage) -> None:
    with override_settings(cadrumo_output_language=language.value):
        sentences = {
            served_m232_related_party_refusal_words(reason, error_code=_code(reason))[0] for reason in _REASONS
        }

    assert len(sentences) == len(_REASONS)
