"""Sidecar-mechanism tests for the manual-PDF corpus text pathway.

Covers two behavioural contracts:

1. ``_read_manual_pdf_sidecar`` serves the shipped normalised text when the
   source PDF's sha256 matches the sidecar, and refuses (returns ``None``) when
   it does not — proving the sha256 guard is live end-to-end and that
   :func:`packaged_data` resolution actually finds the sidecar.

2. The ``_normalise_corpus_text`` function inlined in
   ``dev/corpus/extract_manual_corpus_text.py`` is byte-equal to the
   canonical :func:`normalise_corpus_text` in :mod:`cadrumo.domain.calculations.registry._text`
   over a battery of representative inputs, so a future edit to either side that
   does not mirror to the other fails loudly.

These tests live here (inside the registry test package) so they can use
intra-package relative imports for the private symbols they exercise, in
accordance with ``service-imports-via-top-level-reexports``.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from .._text import normalise_corpus_text
from .._validate_evidence import _read_manual_pdf_sidecar

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# src/cadrumo/domain/calculations/registry/tests/ -> parents[6] is repo root.
_REPO_ROOT = Path(__file__).resolve().parents[6]
_CORPUS_ROOT = _REPO_ROOT / "src" / "cadrumo" / "_data" / "corpus"
_MANUAL_CORPUS_TEXT_ROOT = _REPO_ROOT / "src" / "cadrumo" / "_data" / "manual_corpus_text"
_CORPUS_TEXT_SUFFIX = ".corpus_text.json"


def test_manual_pdf_corpus_text_sidecar_mismatch_returns_none() -> None:
    """_read_manual_pdf_sidecar serves sidecar text on match and refuses it on mismatch.

    Real-behavior test with two assertions:

    1. A matching sha256 (real source PDF) returns the sidecar's normalised_text,
       proving that :func:`packaged_data` resolution and the sha256 verification
       path both work correctly end-to-end.

    2. A mismatched sha256 (wrong bytes) returns ``None``, proving that stale text
       is refused rather than served to the caller.

    Without assertion 1 the test would pass for the wrong reason if packaged_data
    resolution broke (``None`` from a lookup failure satisfies the ``None``
    assertion).
    """
    sidecars = sorted(_MANUAL_CORPUS_TEXT_ROOT.rglob(f"*{_CORPUS_TEXT_SUFFIX}"))
    assert sidecars, "no manual corpus text sidecars found — S05 must run first"

    first_sidecar = sidecars[0]
    data: dict[str, object] = json.loads(first_sidecar.read_text(encoding="utf-8"))
    corpus_path = data["corpus_path"]
    expected_text = data["normalised_text"]
    assert isinstance(corpus_path, str)
    assert isinstance(expected_text, str)

    # Derive the real source PDF path for the positive assertion.
    relative = corpus_path[len("corpus/") :]
    real_source_path = _CORPUS_ROOT / Path(relative)
    assert real_source_path.is_file(), f"source PDF missing for sidecar {first_sidecar.name}: {corpus_path}"

    # Assertion 1: matching sha256 returns the sidecar's normalised_text, proving
    # packaged_data resolution finds the sidecar and the sha256 check passes.
    result_match = _read_manual_pdf_sidecar(corpus_path, real_source_path)
    assert result_match == expected_text, (
        f"_read_manual_pdf_sidecar returned unexpected text for {corpus_path!r}; expected the sidecar's normalised_text"
    )

    # Assertion 2: mismatched sha256 returns None — stale text must be refused.
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(b"not-the-real-pdf-bytes")
        tmp_path = Path(tmp.name)

    try:
        result_mismatch = _read_manual_pdf_sidecar(corpus_path, tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    assert result_mismatch is None, (
        f"_read_manual_pdf_sidecar returned non-None for mismatched bytes "
        f"(corpus_path={corpus_path!r}); stale text must be refused"
    )


def test_corpus_text_normaliser_inlined_copy_is_byte_equal_to_canonical() -> None:
    """The inlined _normalise_corpus_text in the build script is byte-equal to the canonical.

    ``dev/corpus/extract_manual_corpus_text.py`` inlines
    :func:`normalise_corpus_text` from
    :mod:`cadrumo.domain.calculations.registry._text` to avoid triggering cadrumo
    package initialisation (pydantic Settings) in a plain ``python -m`` invocation.
    The two implementations must produce identical output: any future edit to either
    side that does not mirror to the other would silently change the normalised text
    in the shipped sidecars vs. what the runtime validator compares against.

    The battery covers every branch in the normaliser:

    - HTML tag stripping: tags removed, non-tag ``<`` (followed by space/digit) kept
    - HTML entity unescaping: ``&amp;`` ``&lt;`` ``&gt;`` ``&nbsp;``
    - Combining-mark stripping via NFKD: U+0300-U+036F combining diacritics
    - NBSP ``\\xa0`` → space
    - Whitespace collapsing
    - Lowercasing
    """
    from dev.corpus.extract_manual_corpus_text import (  # type: ignore[reportMissingImports]  # dev/ tooling module; resolves at runtime, not on the type-check src roots
        _normalise_corpus_text as inlined,
    )

    battery: list[str] = [
        # HTML tag stripping
        "<b>bold</b> and <em>italic</em> text",
        "<p>paragraph</p>",
        # Non-tag ``<`` must pass through (no letter immediately follows ``<``)
        "menos de < 500 euros anuales",
        "comparación: a < b y c > d",
        # HTML entities
        "precio &amp; impuesto",
        "importe &lt; 100 &euro;",
        "sección &gt; 3",
        "&nbsp;espacio&nbsp;",
        # Combining marks U+0300-U+036F (NFKD decomposition + strip)
        "café",  # precomposed é (U+00E9)
        "café",  # e + combining acute (U+0301)
        "ño",  # n + combining tilde (U+0303)
        "àb́ĉ",  # multiple combining marks
        # NBSP
        "no\xa0breaking\xa0space",
        # Whitespace collapsing
        "  multiple   internal   spaces  ",
        "line\n\nbreak\ttab",
        # Lowercasing
        "UPPERCASE and MixedCase",
        # Mixed: entity + tag + combining + NBSP
        "&lt;b&gt;café\xa0au\xa0lait&lt;/b&gt;",
        # Empty and whitespace-only
        "",
        "   ",
    ]

    mismatches: list[str] = []
    for text in battery:
        canon = normalise_corpus_text(text)
        inline = inlined(text)
        if canon != inline:
            mismatches.append(f"input={text!r}\n  canonical={canon!r}\n  inlined={inline!r}")

    assert not mismatches, (
        f"{len(mismatches)} input(s) produced different output between canonical "
        f"and inlined normalise_corpus_text:\n" + "\n".join(mismatches)
    )
