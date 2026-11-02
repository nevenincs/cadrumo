"""A taxation recommendation's reason is worded in every language from the results it compares."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.external_constants import SUPPORTED_OUTPUT_LANGUAGES, OutputLanguage
from ..taxation_comparison import MATERIALITY_THRESHOLD, TaxationRecommendationReason
from ..taxation_comparison_words import individual_branch_caveat_words, recommendation_reason_words

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# The grouping and decimal marks each language writes, from the catalogue's own number rules.
_MARKS = {"en": ("1,450.00", "2,350.50"), "es": ("1.450,00", "2.350,50"), "ca": ("1.450,00", "2.350,50")}
_NARROW_NO_BREAK = chr(0x202F)
_NO_BREAK = chr(0xA0)


def _words(reason: TaxationRecommendationReason, language: str) -> str:
    return recommendation_reason_words(
        reason,
        conjunta_resultado=Decimal("-900.50"),
        individual_resultado=Decimal("1450.00"),
        delta_resultado=Decimal("2350.50"),
        language=OutputLanguage(language),
    )


@pytest.mark.parametrize("language", SUPPORTED_OUTPUT_LANGUAGES)
@pytest.mark.parametrize("reason", tuple(TaxationRecommendationReason))
def test_every_reason_names_the_results_and_the_difference_it_rests_on(
    reason: TaxationRecommendationReason, language: str
) -> None:
    words = _words(reason, language).replace(_NARROW_NO_BREAK, " ").replace(_NO_BREAK, " ")

    assert "{" not in words
    assert "_" not in words
    figures = _MARKS.get(language)
    if figures is None:
        # Hungarian groups thousands with a space and keeps a decimal comma.
        figures = ("1 450,00", "2 350,50")
    individual, difference = figures
    assert difference in words
    if reason is not TaxationRecommendationReason.BELOW_MATERIALITY:
        assert individual in words


@pytest.mark.parametrize("reason", tuple(TaxationRecommendationReason))
def test_each_reason_is_translated_into_every_other_language(reason: TaxationRecommendationReason) -> None:
    sentences = {language: _words(reason, language) for language in SUPPORTED_OUTPUT_LANGUAGES}

    assert len(set(sentences.values())) == len(SUPPORTED_OUTPUT_LANGUAGES)


def test_the_difference_is_a_magnitude_whichever_way_the_results_differ() -> None:
    reversed_sign = recommendation_reason_words(
        TaxationRecommendationReason.INDIVIDUAL_LOWER_RESULT,
        conjunta_resultado=Decimal("1450.00"),
        individual_resultado=Decimal("-900.50"),
        delta_resultado=Decimal("-2350.50"),
        language=OutputLanguage.EN,
    )

    assert f"a difference of 2,350.50{_NO_BREAK}€" in reversed_sign
    assert "−2,350.50" not in reversed_sign


def test_below_materiality_names_the_threshold_the_comparison_applies() -> None:
    words = recommendation_reason_words(
        TaxationRecommendationReason.BELOW_MATERIALITY,
        conjunta_resultado=Decimal("100.00"),
        individual_resultado=Decimal("100.40"),
        delta_resultado=Decimal("0.40"),
        language=OutputLanguage.EN,
    )

    assert Decimal(1) == MATERIALITY_THRESHOLD
    assert words == (
        f"The two results differ by 0.40{_NO_BREAK}€, less than 1.00{_NO_BREAK}€, so either filing mode is acceptable."
    )


# One distinctive phrase of the caveat per language: the household's two incomes are not two returns.
_CAVEAT_PHRASES = {
    "en": "two separate returns",
    "es": "dos declaraciones separadas",
    "ca": "dues declaracions separades",
    "hu": "két külön bevallást",
}


@pytest.mark.parametrize("language", SUPPORTED_OUTPUT_LANGUAGES)
def test_the_individual_branch_caveat_is_worded_in_the_requested_language(language: str) -> None:
    caveat = individual_branch_caveat_words(OutputLanguage(language))

    assert _CAVEAT_PHRASES[language] in caveat
    assert "{" not in caveat
    assert "_" not in caveat
    assert 0 < len(caveat) <= 1_024


@pytest.mark.parametrize("language", tuple(language for language in SUPPORTED_OUTPUT_LANGUAGES if language != "en"))
def test_the_individual_branch_caveat_is_not_english_outside_english(language: str) -> None:
    english = individual_branch_caveat_words(OutputLanguage.EN)
    caveat = individual_branch_caveat_words(OutputLanguage(language))

    assert caveat != english
    assert _CAVEAT_PHRASES["en"] not in caveat
    assert "household" not in caveat
    assert "single return" not in caveat


def test_every_language_words_the_individual_branch_caveat_differently() -> None:
    caveats = {
        language: individual_branch_caveat_words(OutputLanguage(language)) for language in SUPPORTED_OUTPUT_LANGUAGES
    }

    assert len(set(caveats.values())) == len(SUPPORTED_OUTPUT_LANGUAGES)
