"""English legal vocabulary keeps spelling, casing and language checks."""

import pytest

from ._spelling_support import assert_exact_english_spelling

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize(
    "word,typo,case_miss",
    [
        ("recapitulative", "recapitualtive", "recapiTulative"),
        ("unamended", "unammended", "Unamended"),
        ("citable", "cittable", "Citable"),
        ("unestablished", "unestablised", "Unestablished"),
        ("linkable", "linkabble", "Linkable"),
        ("exigibility", "exigibilty", "Exigibility"),
        ("intracommunity", "intracommunty", "Intracommunity"),
        ("telematically", "telematicaly", "Telematically"),
    ],
)
def test_exact_legal_word_preserves_case_language_and_adjacent_typos(word: str, typo: str, case_miss: str) -> None:
    assert_exact_english_spelling(word, typo, (typo, case_miss, word.upper(), word + "x"))
