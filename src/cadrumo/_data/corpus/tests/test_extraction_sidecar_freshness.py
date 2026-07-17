"""Freshness gate for committed extraction sidecars."""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
from pathlib import Path

import pytest
from dev.docs.preprocess import (
    EXTRACTED_JSON_SUFFIX,
    EXTRACTED_TEXT_SUFFIX,
    PreprocessOutput,
)
from dev.docs.preprocess._html import HTML_EXTRACTOR_ID, build_outputs

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# src/cadrumo/_data/corpus/tests/test_extraction_sidecar_freshness.py -> parents[5] is repo root.
_REPO_ROOT = Path(__file__).resolve().parents[5]
_CORPUS_ROOT = _REPO_ROOT / "src" / "cadrumo" / "_data" / "corpus"
_MANUAL_CORPUS_TEXT_ROOT = _REPO_ROOT / "src" / "cadrumo" / "_data" / "manual_corpus_text"
_CORPUS_TEXT_SUFFIX = ".corpus_text.json"
_PART_SUFFIX = re.compile(r"\.part-\d+$")


def _sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _matches_origin_name(sidecar_name: str, origin_name: str) -> bool:
    stand_in_name = sidecar_name.removesuffix(EXTRACTED_JSON_SUFFIX)
    return stand_in_name == origin_name or _PART_SUFFIX.sub("", stand_in_name) == origin_name


def test_normative_html_sources_use_canonical_lf_bytes() -> None:
    """Normative HTML hashes must be identical on Windows and Unix checkouts."""
    html_root = _CORPUS_ROOT / "normatives" / "html"
    sources = sorted(html_root.glob("*.html"))
    noncanonical = [source.name for source in sources if b"\r" in source.read_bytes()]

    assert sources, "no normative HTML sources found"
    assert not noncanonical, f"normative HTML contains non-LF line endings: {noncanonical!r}"


def test_normative_html_sidecars_equal_current_production_extraction() -> None:
    """Committed normative records are exact outputs of the live extractor."""
    html_root = _CORPUS_ROOT / "normatives" / "html"
    sources = sorted(html_root.glob("*.html"))
    failures: list[str] = []

    for source in sources:
        json_paths = sorted(
            path
            for path in html_root.glob(f"{source.name}*{EXTRACTED_JSON_SUFFIX}")
            if _matches_origin_name(path.name, source.name)
        )
        if not json_paths:
            continue
        committed = [PreprocessOutput.model_validate_json(path.read_text(encoding="utf-8")) for path in json_paths]
        expected = build_outputs(source, repo_root=_REPO_ROOT)
        if committed != expected:
            failures.append(source.relative_to(_REPO_ROOT).as_posix())

    assert sources, "no normative HTML sources found"
    assert not failures, f"normative HTML sidecars differ from the production extractor: {failures[:20]!r}"


def test_committed_extraction_sidecars_match_current_sources() -> None:
    """Every committed extraction sidecar still matches its source bytes."""
    failures: list[str] = []
    sidecars = sorted(_CORPUS_ROOT.rglob(f"*{EXTRACTED_JSON_SUFFIX}"))

    for json_path in sidecars:
        rel_json = json_path.relative_to(_REPO_ROOT).as_posix()
        output = PreprocessOutput.model_validate_json(json_path.read_text(encoding="utf-8"))
        origin = (_REPO_ROOT / output.source_relpath).resolve()
        rel_origin = output.source_relpath
        text_path = json_path.with_name(json_path.name.removesuffix(EXTRACTED_JSON_SUFFIX) + EXTRACTED_TEXT_SUFFIX)

        if output.source_relpath != Path(output.source_relpath).as_posix():
            failures.append(f"{rel_json}: source_relpath is not POSIX: {output.source_relpath!r}")
        if not origin.is_file():
            failures.append(f"{rel_json}: declared source is missing: {rel_origin}")
            continue
        if not origin.is_relative_to(_CORPUS_ROOT):
            failures.append(f"{rel_json}: declared source escapes corpus root: {rel_origin}")
        if json_path.parent != origin.parent or not _matches_origin_name(json_path.name, origin.name):
            failures.append(f"{rel_json}: sidecar is not paired with declared sibling source {rel_origin}")
        if output.source_sha256 != _sha256_of(origin):
            failures.append(f"{rel_json}: source_sha256 does not match current source bytes for {rel_origin}")
        if origin.suffix == ".html" and output.preprocessor_id != HTML_EXTRACTOR_ID:
            failures.append(
                f"{rel_json}: normative HTML sidecar declares retired or unknown "
                f"preprocessor_id {output.preprocessor_id!r}",
            )
        if not text_path.is_file():
            failures.append(f"{rel_json}: text sidecar is missing: {text_path.relative_to(_REPO_ROOT).as_posix()}")
        elif text_path.read_text(encoding="utf-8") != output.render_text():
            failures.append(f"{rel_json}: text sidecar does not match rendered schema payload")

    assert sidecars, "no committed extraction sidecars found under src/cadrumo/_data/corpus"
    assert not failures, f"{len(failures)} stale or malformed extraction sidecars: {failures[:20]!r}"


def test_manual_pdf_corpus_text_sidecars_exist_and_match_source_sha256() -> None:
    """Every committed manual-PDF corpus text sidecar matches its source PDF bytes.

    Ensures that dev/packaging/extract_manual_corpus_text.py was re-run after
    any corpus PDF changed, so the shipped sidecars are always in sync with
    the source PDFs that _validate_evidence._read_manual_pdf_sidecar reads.
    """
    sidecars = sorted(_MANUAL_CORPUS_TEXT_ROOT.rglob(f"*{_CORPUS_TEXT_SUFFIX}"))
    failures: list[str] = []

    for sidecar_path in sidecars:
        rel_sidecar = sidecar_path.relative_to(_REPO_ROOT).as_posix()
        try:
            data: dict[str, object] = json.loads(sidecar_path.read_text(encoding="utf-8"))
        except Exception as exc:
            failures.append(f"{rel_sidecar}: cannot parse JSON: {exc}")
            continue

        corpus_path = data.get("corpus_path")
        stored_sha256 = data.get("source_sha256")
        normalised_text = data.get("normalised_text")
        schema_version = data.get("schema_version")

        if not isinstance(corpus_path, str) or not corpus_path.startswith("corpus/"):
            failures.append(f"{rel_sidecar}: missing or malformed corpus_path: {corpus_path!r}")
            continue
        if not isinstance(stored_sha256, str) or len(stored_sha256) != 64:
            failures.append(f"{rel_sidecar}: missing or malformed source_sha256")
            continue
        if not isinstance(normalised_text, str):
            failures.append(f"{rel_sidecar}: missing normalised_text field")
            continue
        if schema_version != 1:
            failures.append(f"{rel_sidecar}: unexpected schema_version {schema_version!r}")
            continue

        # Derive the expected source PDF path from corpus_path.
        relative = corpus_path[len("corpus/") :]
        source_path = _CORPUS_ROOT / Path(relative)
        if not source_path.is_file():
            failures.append(f"{rel_sidecar}: source PDF missing: {corpus_path}")
            continue

        actual_sha256 = hashlib.sha256(source_path.read_bytes()).hexdigest()
        if actual_sha256 != stored_sha256:
            failures.append(
                f"{rel_sidecar}: sha256 mismatch for {corpus_path} "
                f"(stored {stored_sha256[:8]}…, actual {actual_sha256[:8]}…) — "
                "run: uv run --no-sync python -m dev.packaging.extract_manual_corpus_text"
            )

    assert sidecars, f"no manual corpus text sidecars found under {_MANUAL_CORPUS_TEXT_ROOT}"
    assert not failures, f"{len(failures)} stale or malformed manual PDF sidecars:\n" + "\n".join(failures[:20])


def test_manual_pdf_corpus_text_sidecar_mismatch_returns_none() -> None:
    """_read_manual_pdf_sidecar serves sidecar text on match and refuses it on mismatch.

    Real-behavior test with two assertions:
    1. A matching sha256 (real source PDF) returns the sidecar's normalised_text,
       proving that packaged_data resolution and the sha256 verification path both
       work correctly end-to-end.
    2. A mismatched sha256 (wrong bytes) returns None, proving that stale text is
       refused rather than served to the caller.

    Without assertion 1 the test would pass for the wrong reason if packaged_data
    resolution broke (None from a lookup failure satisfies the None assertion).
    """
    from cadrumo.domain.calculations.registry._validate_evidence import (
        _read_manual_pdf_sidecar,
    )

    # Pick the first committed sidecar so the test does not depend on a
    # specific manual file being present.
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

    dev/packaging/extract_manual_corpus_text.py inlines normalise_corpus_text from
    cadrumo.domain.calculations.registry._text to avoid triggering cadrumo package
    initialisation (pydantic Settings) in a plain ``python -m`` invocation.  The
    two implementations must produce identical output: any future edit to either
    side that does not mirror to the other would silently change the normalised
    text in the shipped sidecars vs. what the runtime validator compares against.

    The battery covers every branch in the normaliser:
    - HTML tag stripping: tags removed, non-tag ``<`` (followed by space/digit) kept
    - HTML entity unescaping: ``&amp;`` ``&lt;`` ``&gt;`` ``&nbsp;``
    - Combining-mark stripping via NFKD: U+0300-U+036F combining diacritics
    - NBSP ``\\xa0`` → space
    - Whitespace collapsing
    - Lowercasing
    """
    from dev.packaging.extract_manual_corpus_text import (
        _normalise_corpus_text as inlined,
    )

    from cadrumo.domain.calculations.registry._text import (
        normalise_corpus_text as canonical,
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
        "café",  # e + combining acute (U+0301)
        "ño",  # n + combining tilde (U+0303)
        "àb́ĉ",  # multiple combining marks
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
        canon = canonical(text)
        inline = inlined(text)
        if canon != inline:
            mismatches.append(f"input={text!r}\n  canonical={canon!r}\n  inlined={inline!r}")

    assert not mismatches, (
        f"{len(mismatches)} input(s) produced different output between canonical "
        f"and inlined normalise_corpus_text:\n" + "\n".join(mismatches)
    )
