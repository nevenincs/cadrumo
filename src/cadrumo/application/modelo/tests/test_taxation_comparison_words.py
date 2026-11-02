"""A taxation recommendation's reason is worded in every language from the results it compares."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.external_constants import SUPPORTED_OUTPUT_LANGUAGES, OutputLanguage
from ..taxation_comparison import MATERIALITY_THRESHOLD, TaxationRecommendationReason
from ..taxation_comparison_words import recommendation_reason_words

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
