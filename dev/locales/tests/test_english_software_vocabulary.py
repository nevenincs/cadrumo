"""English software prose uses exact words without admitting typo families."""

import pytest

from ._spelling_support import assert_exact_english_spelling

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize(
    "word,typo,case_miss",
    [
        ("Quickstart", "Quickstrat", "QuickStart"),
        ("quickstart", "quickstrat", "QuickStart"),
        ("subpackages", "subpackges", "Subpackages"),
        ("docstrings", "docstrngs", "Docstrings"),
        ("plaintext", "plaintexxt", "Plaintext"),
        ("decrypting", "decryping", "Decrypting"),
        ("decrypted", "decrypetd", "Decrypted"),
        ("schemas", "schmeas", "Schemas"),
        ("invariants", "invaraints", "Invariants"),
    ],
)
def test_software_word_keeps_spelling_case_locale_and_adjacent_prose_checked(
    word: str, typo: str, case_miss: str
) -> None:
    assert_exact_english_spelling(word, typo, (typo, case_miss, word.upper(), word + "x"))
