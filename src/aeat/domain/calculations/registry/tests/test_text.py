"""Unit tests for the corpus-normalisation helper used by citation checks."""

from __future__ import annotations

import pytest

from .._text import normalise_corpus_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_math_notation_less_than_does_not_swallow_prose() -> None:
    """AEAT manuals use ``< 500 euros`` and ``< 3 años`` as inline math
    notation. ``normalise_corpus_text`` must preserve such inline math
    in the corpus so required-text citation checks see the literal
    AEAT prose, not a truncated form where stretches between ``<``
    and ``>`` were stripped as if HTML tags.
    """
    corpus = "Reducción aplicable cuando el importe es < 500 euros y el plazo es < 3 años."

    normalised = normalise_corpus_text(corpus)

    assert "< 500 euros" in normalised
    assert "< 3 anos" in normalised
    assert "reduccion aplicable" in normalised


def test_well_formed_html_tags_are_stripped() -> None:
    """Tags whose ``<`` is followed by a tag-name character are still removed."""
    corpus = "<p>escala autonómica</p> aplicable a <strong>base liquidable</strong>"

    normalised = normalise_corpus_text(corpus)

    assert "<p>" not in normalised
    assert "</p>" not in normalised
    assert "<strong>" not in normalised
    assert "escala autonomica" in normalised
    assert "base liquidable" in normalised


def test_html_entities_are_decoded_before_stripping() -> None:
    """``html.unescape`` runs before the tag stripper so entities survive."""
    corpus = "escala auton&oacute;mica &amp; base liquidable general"

    normalised = normalise_corpus_text(corpus)

    assert "escala autonomica" in normalised
    assert "&" in normalised
    assert "base liquidable general" in normalised


def test_diacritics_are_stripped_via_nfkd_decomposition() -> None:
    """``á``, ``ó``, ``ñ`` must collapse to ASCII so required-text checks
    written against bare ASCII (citation fixtures often are) still hit."""
    corpus = "Año 2025 — escala autonómica para residentes en España"

    normalised = normalise_corpus_text(corpus)

    assert "ano 2025" in normalised
    assert "escala autonomica" in normalised
    assert "espana" in normalised


def test_whitespace_runs_collapse_to_single_space() -> None:
    """Newlines, tabs, and double spaces collapse so multi-line corpus blocks
    compare cleanly against single-line required_text fixtures."""
    corpus = "Renta\n2025\t\tpor   atribución"

    normalised = normalise_corpus_text(corpus)

    assert normalised == "renta 2025 por atribucion"


def test_unbalanced_open_angle_at_end_of_input_is_preserved() -> None:
    """A trailing ``<`` with no matching ``>`` must not consume the prefix
    (which the old regex would have done, returning the empty string)."""
    corpus = "Importe inferior a <"

    normalised = normalise_corpus_text(corpus)

    assert "importe inferior a" in normalised
