"""Statutory numbering is structural; surrounding prose still needs spelling."""

import pytest

from ..signal_spelling_segments import locale_spelling_words
from ..signal_tokens import filtered_translation_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize("locale", ["en", "es", "ca", "hu"])
@pytest.mark.parametrize(
    "ordinal",
    [
        "quater",
        "nonies",
        "noniesdecies",
        "octiesdecies",
        "quatervicies",
        "quinquies",
        "quinvicies",
        "sexies",
        "unvicies",
        "terdecies",
        "quaterdecies",
        "undecies",
        "decies",
        "duodecies",
        "quinquiesdecies",
        "duovicies",
        "sexvicies",
        "tervicies",
        "vicies",
        "octovicies",
    ],
)
def test_exact_numbered_article_suffixes_leave_adjacent_prose_checked(locale: str, ordinal: str) -> None:
    words, excluded = locale_spelling_words(f"art. 163 {ordinal}: misspeling", locale)

    assert "misspeling" in words
    assert ordinal not in words
    assert excluded == 1


@pytest.mark.parametrize("connector", ["a", "to"])
def test_numbered_article_range_keeps_both_exact_endpoints_structural(connector: str) -> None:
    text, excluded = filtered_translation_text(f"art. 163 octiesdecies {connector} vicies; misspeling")

    assert text == "art. misspeling"
    assert excluded == 1


@pytest.mark.parametrize(
    "value,retained",
    [
        ("quater", "quater"),
        ("art. quater", "quater"),
        ("x163 quater", "quater"),
        ("163.5 quater", "quater"),
        ("163 Quater", "Quater"),
        ("163 quaterr", "quaterr"),
        ("163 noniesdeciesx", "noniesdeciesx"),
        ("163 unreviewed", "unreviewed"),
        ("163 octiesdecies to viciesx", "viciesx"),
        ("163 octiesdecies plus vicies", "vicies"),
        ("163 octiesdecies; quater", "quater"),
    ],
)
def test_missing_numeric_context_case_and_near_misses_remain_visible(value: str, retained: str) -> None:
    words, _excluded = locale_spelling_words(value, "en")

    assert retained in words


def test_article_number_does_not_exempt_the_same_suffix_elsewhere_in_the_cell() -> None:
    words, _excluded = locale_spelling_words("163 quater; quater is a misspeling elsewhere", "en")

    assert words.count("quater") == 1
    assert "misspeling" in words
