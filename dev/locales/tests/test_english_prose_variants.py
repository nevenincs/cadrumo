"""Attested English spelling variants keep exact spelling and locale scope."""

import pytest

from ._spelling_support import assert_exact_english_spelling

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize(
    "word,typo",
    [
        ("advisor", "advsior"),
        ("adapter", "adaptr"),
        ("adapters", "adpaters"),
        ("artifact", "artifcat"),
        ("amortization", "amortizaton"),
        ("proration", "proraton"),
        ("formalization", "formalizaton"),
        ("formalized", "formalizd"),
    ],
)
def test_exact_english_variant_does_not_admit_near_misses_casing_or_other_locales(word: str, typo: str) -> None:
    assert_exact_english_spelling(word, typo, (typo, word.capitalize(), word.upper(), word + "x"))
