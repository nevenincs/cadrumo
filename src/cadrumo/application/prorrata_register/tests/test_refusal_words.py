"""Every refusal reason of the prorrata register operations serves a sentence a frontend can show verbatim."""

from __future__ import annotations

import re
from typing import cast, get_args

import pytest

from ....core.config import override_settings
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import tr
from ..mutation_steps import build_prorrata_refusal_projection
from ..projection_contracts import (
    PRORRATA_ELECTION_REFUSAL_CODE,
    PRORRATA_SECTOR_LIFECYCLE_REFUSAL_CODE,
    PRORRATA_VALIDATION_REFUSAL_CODE,
    PRORRATA_WHOLE_SEED_REFUSAL_CODE,
    ProrrataRefusalCode,
    ProrrataRefusalReason,
)
from ..refusal_words import served_refusal_words

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_REASONS = cast(tuple[ProrrataRefusalReason, ...], get_args(ProrrataRefusalReason.__value__))
_CODES: dict[str, ProrrataRefusalCode] = {
    "provenance_not_electable": PRORRATA_ELECTION_REFUSAL_CODE,
    "reference_required": PRORRATA_ELECTION_REFUSAL_CODE,
    "reference_not_permitted": PRORRATA_ELECTION_REFUSAL_CODE,
    "seed_source_absent": PRORRATA_WHOLE_SEED_REFUSAL_CODE,
    "seed_source_blocked": PRORRATA_WHOLE_SEED_REFUSAL_CODE,
    "seed_existing_blocked": PRORRATA_WHOLE_SEED_REFUSAL_CODE,
    "regulated_override_standing": PRORRATA_WHOLE_SEED_REFUSAL_CODE,
    "sector_prior_definitive_absent": PRORRATA_SECTOR_LIFECYCLE_REFUSAL_CODE,
    "sector_settlement_entry_absent": PRORRATA_SECTOR_LIFECYCLE_REFUSAL_CODE,
}


def _code(reason: ProrrataRefusalReason) -> ProrrataRefusalCode:
    return _CODES.get(reason, PRORRATA_VALIDATION_REFUSAL_CODE)


def test_the_operations_have_fourteen_refusal_reasons() -> None:
    assert len(_REASONS) == 14


@pytest.mark.parametrize("language", list(OutputLanguage))
@pytest.mark.parametrize("reason", _REASONS)
def test_each_reason_serves_a_finished_sentence_that_names_no_command_option(
    reason: ProrrataRefusalReason, language: OutputLanguage
) -> None:
    with override_settings(cadrumo_output_language=language.value):
        words, served_language = served_refusal_words(reason, error_code=_code(reason))

    assert served_language is language
    assert words.strip() == words
    assert len(words) > 20
    assert not re.search(r"\bapplication\.|\{|\}|%\(|--[a-z]", words)


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_the_sentences_of_one_language_are_all_different(language: OutputLanguage) -> None:
    with override_settings(cadrumo_output_language=language.value):
        sentences = {served_refusal_words(reason, error_code=_code(reason))[0] for reason in _REASONS}

    assert len(sentences) == len(_REASONS)


@pytest.mark.parametrize("reason", ["provenance_not_electable", "reference_required", "reference_not_permitted"])
def test_an_election_reason_serves_its_own_sentence_rather_than_the_codes_general_one(
    reason: ProrrataRefusalReason,
) -> None:
    with override_settings(cadrumo_output_language="en"):
        words, _language = served_refusal_words(reason, error_code=PRORRATA_ELECTION_REFUSAL_CODE)
        general = tr("errors.refused.canonical_prorrata_election", locale="en")

    assert words != general


def test_the_refusal_projection_carries_the_sentence_and_its_language() -> None:
    with override_settings(cadrumo_output_language="es"):
        refusal = build_prorrata_refusal_projection(reason="seed_source_absent", detail="x", ejercicio=2026)
        expected, _ = served_refusal_words("seed_source_absent", error_code=PRORRATA_VALIDATION_REFUSAL_CODE)

    assert refusal.refusal_words == expected
    assert refusal.refusal_words_language is OutputLanguage.ES
