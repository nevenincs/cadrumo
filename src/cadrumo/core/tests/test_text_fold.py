"""Behaviour tests for the canonical accent-folding primitive."""

from __future__ import annotations

import pytest

from ..text_fold import ascii_slug, fold_diacritics

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


def test_a_slug_folds_accents_and_collapses_every_other_character() -> None:
    """The shared behaviour both annual-Orden callers now depend on."""
    assert ascii_slug("Carpintería y cerrajería") == "carpinteria-y-cerrajeria"
    assert ascii_slug("Diseño de moda") == "diseno-de-moda"
    assert ascii_slug("  Café -- bar  ") == "cafe-bar"


def test_text_with_no_slug_characters_returns_empty_rather_than_raising() -> None:
    """Callers disagree on what an absent slug means, so each owes its own error.

    One caller is parsing an HTML source and raises a parse error; the other is
    compiling a registry declaration and raises a validation error. The shared
    helper must not pick one of those for them.
    """
    assert ascii_slug("---") == ""
    assert ascii_slug("€—") == ""


def test_a_compatibility_digit_survives_into_the_slug() -> None:
    """NFKD is a COMPATIBILITY decomposition, so fractions become digits.

    ``1/2`` decomposes to the digits 1 and 2 and ``2`` (superscript) to 2, so a
    heading carrying them slugs with those digits rather than dropping them.
    Pinned because it is surprising, and because both annual-Orden callers
    inherit it from the shared helper.
    """
    assert ascii_slug("½²") == "122"
    assert ascii_slug("Superficie 100 m²") == "superficie-100-m2"


def test_dropping_combining_marks_is_redundant_under_the_ascii_pass() -> None:
    """Pins the equivalence that let the two Orden slug paths merge.

    The registry compiler previously spelled this as NFKD followed by
    ``encode("ascii", "ignore")``, without the explicit nonspacing-mark drop
    that :func:`fold_diacritics` performs. The two agree for every input
    because every combining mark NFKD exposes is itself non-ASCII, so the
    ASCII pass discards it either way. If that ever stops holding, the two
    annual-Orden identities would silently disagree and this fails first.
    """
    import re
    from unicodedata import normalize

    slug_run = re.compile(r"[^a-z0-9]+")
    for sample in (
        "Peluquería de señoras",
        "Grupo 1.º actividad",
        "Epígrafe 2.ª sección",
        "Superficie 100 m²",
        "Æsculapio",
        "Straße",
        "Fabricación – acabado",
    ):
        decomposed = normalize("NFKD", sample).encode("ascii", "ignore").decode("ascii").casefold()
        assert ascii_slug(sample) == slug_run.sub("-", decomposed).strip("-"), sample
