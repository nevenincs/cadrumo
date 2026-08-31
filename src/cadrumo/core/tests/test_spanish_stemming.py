"""Real lexical normalization behavior shared by the shipped search indexes."""

from __future__ import annotations

import pytest

from ..spanish_stemming import spanish_stemmer, spanish_word_tokens, stem_spanish_terms, stem_spanish_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_spanish_stemming_normalises_accented_inflections_through_one_core_contract() -> None:
    stemmer = spanish_stemmer()
    terms = spanish_word_tokens("Declaraciones, declaración; transacciones.")

    assert terms == ("declaraciones", "declaración", "transacciones")
    assert stem_spanish_terms(stemmer, terms) == ("declar", "declar", "transaccion")
    assert stem_spanish_text(stemmer, "Declaraciones declaración") == "declar declar"
