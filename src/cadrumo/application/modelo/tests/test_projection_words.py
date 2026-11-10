"""The projection's unresolved lists are worded in every language, from the catalogue and no token."""

from __future__ import annotations

import re

import pytest

from ....core.aggregation import BindingSourceKind
from ....core.external_constants import SUPPORTED_OUTPUT_LANGUAGES, OutputLanguage
from ....core.retencion_soportada import RetencionSoportadaClase
from ....domain.calculations.registry.formula_runtime_ops import RegistryUnresolvedOutcomeReason
from ....domain.modelos.calculation_revision_sources import CalculationNoteFact, CalculationNoteSentence
from ..projection_unresolved import UNRESOLVED_OPERAND_REASON
from ..projection_words import binding_source_words, unresolved_binding_words, unresolved_casilla_reason_words

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CASILLA_REASONS = (
    UNRESOLVED_OPERAND_REASON,
    *(reason.value for reason in RegistryUnresolvedOutcomeReason),
    "a-reason-no-catalogue-knows",
)
_RAW = re.compile(r"_|\{|\}|%\{|m210", re.IGNORECASE)
_ENGLISH_ONLY = OutputLanguage.EN


@pytest.mark.parametrize("language", SUPPORTED_OUTPUT_LANGUAGES)
@pytest.mark.parametrize("reason", _CASILLA_REASONS)
def test_every_reason_a_computed_box_can_carry_reads_in_words(reason: str, language: str) -> None:
    words = unresolved_casilla_reason_words(reason, language=OutputLanguage(language))

    assert words.strip() == words
    assert len(words) > 20
    assert _RAW.search(words) is None, words


@pytest.mark.parametrize("reason", _CASILLA_REASONS)
def test_a_reason_is_translated_not_repeated_in_english(reason: str) -> None:
    english = unresolved_casilla_reason_words(reason, language=_ENGLISH_ONLY)

    for language in SUPPORTED_OUTPUT_LANGUAGES:
        if language != _ENGLISH_ONLY.value:
            assert unresolved_casilla_reason_words(reason, language=OutputLanguage(language)) != english


def test_each_known_reason_has_its_own_sentence_and_an_unknown_one_a_general_sentence() -> None:
    sentences = {reason: unresolved_casilla_reason_words(reason, language=_ENGLISH_ONLY) for reason in _CASILLA_REASONS}

    assert len(set(sentences.values())) == len(_CASILLA_REASONS)
    assert "never shown as zero" in sentences["a-reason-no-catalogue-knows"]


@pytest.mark.parametrize("language", SUPPORTED_OUTPUT_LANGUAGES)
@pytest.mark.parametrize(
    "sentence",
    [
        CalculationNoteSentence.RETENCION_SOPORTADA_EVIDENCE_REQUIRED,
        CalculationNoteSentence.RETENCION_SOPORTADA_ABSENCE_CONTRADICTED,
    ],
)
@pytest.mark.parametrize("income_class", tuple(RetencionSoportadaClase))
def test_an_unresolved_credit_is_worded_from_its_own_note_and_names_its_income_class(
    sentence: CalculationNoteSentence, income_class: RetencionSoportadaClase, language: str
) -> None:
    fact = CalculationNoteFact.of(sentence, income_class=income_class.value)

    words = unresolved_binding_words(fact, language=OutputLanguage(language))

    assert _RAW.search(words) is None, words
    # The two states are told apart in words, as they are by their tokens.
    other = (
        CalculationNoteSentence.RETENCION_SOPORTADA_ABSENCE_CONTRADICTED
        if sentence is CalculationNoteSentence.RETENCION_SOPORTADA_EVIDENCE_REQUIRED
        else CalculationNoteSentence.RETENCION_SOPORTADA_EVIDENCE_REQUIRED
    )
    other_words = unresolved_binding_words(
        CalculationNoteFact.of(other, income_class=income_class.value), language=OutputLanguage(language)
    )
    assert words != other_words


@pytest.mark.parametrize("language", SUPPORTED_OUTPUT_LANGUAGES)
def test_a_binding_with_no_note_is_worded_without_a_class_and_never_as_zero(language: str) -> None:
    words = unresolved_binding_words(None, language=OutputLanguage(language))

    assert _RAW.search(words) is None, words
    if language != _ENGLISH_ONLY.value:
        assert words != unresolved_binding_words(None, language=_ENGLISH_ONLY)


def test_a_binding_source_is_named_in_a_few_words_and_an_unknown_one_is_not_invented() -> None:
    assert binding_source_words(BindingSourceKind.RETENCION_SOPORTADA.value, language=_ENGLISH_ONLY) == (
        "Withholding suffered"
    )
    assert binding_source_words("a-source-no-one-declared", language=_ENGLISH_ONLY) is None
    named = {
        language: binding_source_words(BindingSourceKind.RETENCION_SOPORTADA.value, language=OutputLanguage(language))
        for language in SUPPORTED_OUTPUT_LANGUAGES
    }
    assert None not in named.values()
    assert len(set(named.values())) == len(SUPPORTED_OUTPUT_LANGUAGES)
