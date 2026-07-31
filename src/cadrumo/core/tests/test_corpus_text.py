"""Behaviour and import-boundary tests for corpus-text normalisation."""

from __future__ import annotations

import subprocess
import sys

import pytest

from .. import normalise_corpus_text
from ..corpus_text import normalise_corpus_text as normalise_corpus_text_owner

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_core_facade_reexports_the_corpus_text_owner() -> None:
    """All consumers share the exact stdlib-only normaliser object."""
    assert normalise_corpus_text is normalise_corpus_text_owner


def test_core_facade_normaliser_imports_without_configuration_or_domain_loading() -> None:
    """Build tooling can use the facade without loading settings or registry code."""
    probe = (
        "import sys\n"
        "from cadrumo.core import normalise_corpus_text\n"
        "assert normalise_corpus_text('<p>Café&nbsp;2026</p>') == 'cafe 2026'\n"
        "assert 'cadrumo.core.config' not in sys.modules\n"
        "assert not any(name.startswith('cadrumo.domain') for name in sys.modules)\n"
    )
    completed = subprocess.run(  # noqa: S603 - fixed interpreter and inline probe exercise the import boundary.
        [sys.executable, "-c", probe],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


def test_math_notation_less_than_does_not_swallow_prose() -> None:
    corpus = "Reducción aplicable cuando el importe es < 500 euros y el plazo es < 3 años."

    normalised = normalise_corpus_text(corpus)

    assert "< 500 euros" in normalised
    assert "< 3 anos" in normalised
    assert "reduccion aplicable" in normalised


def test_well_formed_html_tags_are_stripped() -> None:
    corpus = "<p>escala autonómica</p> aplicable a <strong>base liquidable</strong>"

    normalised = normalise_corpus_text(corpus)

    assert "<p>" not in normalised
    assert "</p>" not in normalised
    assert "<strong>" not in normalised
    assert "escala autonomica" in normalised
    assert "base liquidable" in normalised


def test_html_entities_are_decoded_before_stripping() -> None:
    corpus = "escala auton&oacute;mica &amp; base liquidable general"

    normalised = normalise_corpus_text(corpus)

    assert "escala autonomica" in normalised
    assert "&" in normalised
    assert "base liquidable general" in normalised


def test_nfkd_nbsp_and_whitespace_normalisation_preserve_citation_grammar() -> None:
    corpus = "  Año\xa02025\n\npor\tatribución  "

    assert normalise_corpus_text(corpus) == "ano 2025 por atribucion"


def test_unbalanced_open_angle_at_end_of_input_is_preserved() -> None:
    corpus = "Importe inferior a <"

    normalised = normalise_corpus_text(corpus)

    assert "importe inferior a" in normalised
