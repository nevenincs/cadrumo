"""Every refusal reason of the contribution record operations has a sentence a frontend can show verbatim."""

from __future__ import annotations

import re
from typing import cast, get_args

import pytest

from cadrumo.application.aggregation.prevision_social_contribution_repository import (
    PrevisionSocialContributionWriteRefusal,
)
from cadrumo.application.prevision_social_contribution.contracts import (
    PREVISION_SOCIAL_REVISION_REFUSAL_CODE,
    PREVISION_SOCIAL_WRITE_REFUSAL_CODE,
    PrevisionSocialRefusalReason,
)
from cadrumo.application.prevision_social_contribution.refusal_words import served_refusal_words
from cadrumo.core.config import override_settings
from cadrumo.core.external_constants import OutputLanguage

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_REASONS = cast(tuple[PrevisionSocialRefusalReason, ...], get_args(PrevisionSocialRefusalReason.__value__))


def _code(reason: PrevisionSocialRefusalReason) -> str:
    if reason == "stale_revision":
        return PREVISION_SOCIAL_REVISION_REFUSAL_CODE
    return PREVISION_SOCIAL_WRITE_REFUSAL_CODE


def test_every_refusal_of_the_write_path_is_a_reason_the_operation_serves() -> None:
    assert set(get_args(PrevisionSocialContributionWriteRefusal.__value__)) <= set(_REASONS)
    assert len(_REASONS) == 15


@pytest.mark.parametrize("language", list(OutputLanguage))
@pytest.mark.parametrize("reason", _REASONS)
def test_each_reason_serves_a_finished_sentence_that_names_no_command_option(
    reason: PrevisionSocialRefusalReason, language: OutputLanguage
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
