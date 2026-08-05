"""Behaviour tests for the canonical accent-folding primitive."""

from __future__ import annotations

import pytest

from ..text_fold import fold_diacritics

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_strips_precomposed_spanish_accents() -> None:
    assert fold_diacritics("Declaración") == "Declaracion"
    assert fold_diacritics("MODIFICACIÓN") == "MODIFICACION"
    assert fold_diacritics("año") == "ano"
    assert fold_diacritics("Coruña") == "Coruna"


def test_leaves_plain_ascii_unchanged() -> None:
    assert fold_diacritics("Presentar declaracion") == "Presentar declaracion"
    assert fold_diacritics("") == ""


def test_preserves_case() -> None:
    """Case is orthogonal to diacritic folding -- callers compose their own casefold."""
    assert fold_diacritics("ÓPTICA") == "OPTICA"
    assert fold_diacritics("Óptica") == "Optica"


def test_preserves_non_decomposable_non_ascii_characters() -> None:
    """A codepoint with no combining-mark decomposition passes through unchanged.

    This is the defining difference from an ``encode("ascii", "ignore")``
    fold: this function folds ACCENTS, it does not transliterate to ASCII.
    A caller that needs the stronger ascii-only guarantee composes its own
    ascii-encode pass on top of this primitive.
    """
    assert fold_diacritics("Presentación – confirmar") == "Presentacion – confirmar"
    assert fold_diacritics("Pagar 100€ ahora") == "Pagar 100€ ahora"
    assert fold_diacritics("Ørsted") == "Ørsted"


def test_whitespace_and_html_are_out_of_scope() -> None:
    """This primitive folds diacritics only -- trailing transforms are the caller's job."""
    assert fold_diacritics("Café&nbsp;2026") == "Cafe&nbsp;2026"
    assert fold_diacritics("uno   dos") == "uno   dos"
