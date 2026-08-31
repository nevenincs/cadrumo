"""Every surface that handles an AEAT CSV agrees on its shape.

A Código Seguro de Verificación crosses three unrelated layers: the inbound
justificante extractor lifts one out of PDF text, the outbound sede adapters
read one out of a cotejo URL, and the public verifier round-trips one back to
AEAT. Each previously carried its own width. A narrower copy is not the safe
choice -- it refuses identifiers AEAT really issues, and the artefact behind
one is filing evidence.
"""

from __future__ import annotations

import pytest

from ..aeat_csv import AEAT_CSV_MAX_LENGTH, AEAT_CSV_MIN_LENGTH, is_aeat_csv

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class TestCanonicalShape:
    @pytest.mark.parametrize("length", [AEAT_CSV_MIN_LENGTH, 16, 24, 25, AEAT_CSV_MAX_LENGTH])
    def test_documented_widths_are_accepted(self, length: int) -> None:
        assert is_aeat_csv("A" * length) is True

    @pytest.mark.parametrize("length", [0, 1, AEAT_CSV_MIN_LENGTH - 1, AEAT_CSV_MAX_LENGTH + 1, 64])
    def test_out_of_range_widths_are_refused(self, length: int) -> None:
        assert is_aeat_csv("A" * length) is False

    @pytest.mark.parametrize("value", ["abcdefgh", "ABCD-EFGH", "ABCD EFGH", "ABCDEFG.", "ÁBCDEFGH"])
    def test_non_uppercase_alphanumeric_is_refused(self, value: str) -> None:
        assert is_aeat_csv(value) is False

    def test_match_is_anchored_at_both_ends(self) -> None:
        """A well-shaped run inside a longer token is not a CSV."""
        assert is_aeat_csv("PREFIX" + "A" * 16 + "SUFFIX!") is False
