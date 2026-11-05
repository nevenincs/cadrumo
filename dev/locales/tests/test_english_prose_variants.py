"""Attested English spelling variants keep exact spelling and locale scope."""

import pytest

from .spelling_support import assert_exact_english_spelling

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize(
    "word,typo,case_miss",
    [
        ("advisor", "advsior", "Advisor"),
        ("adapter", "adaptr", "Adapter"),
        # "Adapters" is enrolled separately: it opens a sentence in the architecture docs.
        ("adapters", "adpaters", "AdApters"),
        ("artifact", "artifcat", "Artifact"),
        ("amortization", "amortizaton", "Amortization"),
        ("proration", "proraton", "Proration"),
        ("formalization", "formalizaton", "Formalization"),
        ("formalized", "formalizd", "Formalized"),
    ],
)
def test_exact_english_variant_does_not_admit_near_misses_casing_or_other_locales(
    word: str, typo: str, case_miss: str
) -> None:
    assert_exact_english_spelling(word, typo, (typo, case_miss, word.upper(), word + "x"))
