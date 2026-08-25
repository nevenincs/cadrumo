"""Sidecar-mechanism tests for the manual-PDF corpus text pathway.

Covers two behavioural contracts:

1. ``_read_manual_pdf_sidecar`` serves the shipped normalised text when the
   source PDF's sha256 matches the sidecar, and refuses (returns ``None``) when
   it does not — proving the sha256 guard is live end-to-end and that
   :func:`packaged_data` resolution actually finds the sidecar.

2. ``_validated_sidecar_text`` — the whole runtime admission decision — enforces
   the shared sidecar contract, so a payload the build-time extractor could not
   have written is refused instead of served as extracted text.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from .....core.directory_scan import scan_directory
from .._validate_evidence import _read_manual_pdf_sidecar, _validated_sidecar_text

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
    sidecars = scan_directory(_MANUAL_CORPUS_TEXT_ROOT, pattern=f"*{_CORPUS_TEXT_SUFFIX}", recursive=True)
    assert sidecars, "no manual corpus text sidecars found — the corpus text extraction must run first"

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


def _first_shipped_sidecar() -> tuple[str, dict[str, object]]:
    """Return the corpus path and decoded payload of one shipped sidecar."""
    sidecars = scan_directory(_MANUAL_CORPUS_TEXT_ROOT, pattern=f"*{_CORPUS_TEXT_SUFFIX}", recursive=True)
    assert sidecars, "no manual corpus text sidecars found"
    payload: dict[str, object] = json.loads(sidecars[0].read_text(encoding="utf-8"))
    corpus_path = payload["corpus_path"]
    assert isinstance(corpus_path, str)
    return corpus_path, payload


def test_runtime_admission_accepts_the_shipped_sidecar() -> None:
    """The positive control: a real shipped sidecar is admitted unchanged.

    Without this, every refusal assertion below would also be satisfied by a
    validator that refuses everything.
    """
    corpus_path, payload = _first_shipped_sidecar()
    expected_text = payload["normalised_text"]
    stored_sha256 = payload["source_sha256"]
    assert isinstance(expected_text, str)
    assert isinstance(stored_sha256, str)

    admitted = _validated_sidecar_text(json.dumps(payload), corpus_path, stored_sha256)

    assert admitted == expected_text


@pytest.mark.parametrize(
    ("mutation", "replacement"),
    [
        ("schema_version", None),
        ("schema_version", 1),
        ("corpus_path", None),
        ("extraction_platform", None),
        ("extraction_platform", ""),
        ("normalised_text", ""),
        ("source_sha256", "not-a-digest"),
    ],
)
def test_runtime_admission_refuses_out_of_contract_sidecars(mutation: str, replacement: object) -> None:
    """A sidecar the extractor could not have written is refused, not served.

    The pre-fix reader validated only ``source_sha256`` equality and that
    ``normalised_text`` was a string, so a payload with a dropped schema
    version, a stripped extraction-platform stamp, a missing corpus path, or an
    empty extraction was served verbatim as if it were extracted text. Every
    refusal here degrades to on-demand extraction from the real PDF bytes, so
    refusing costs a slow path and never a wrong ``required_text`` verdict.
    """
    corpus_path, payload = _first_shipped_sidecar()
    stored_sha256 = payload["source_sha256"]
    assert isinstance(stored_sha256, str)
    if replacement is None:
        del payload[mutation]
    else:
        payload[mutation] = replacement

    assert _validated_sidecar_text(json.dumps(payload), corpus_path, stored_sha256) is None


def test_runtime_admission_refuses_a_sidecar_claiming_another_corpus_path() -> None:
    """A sidecar filed under one path but claiming another is refused.

    The content key alone cannot catch this: a sidecar swapped between two
    sources keeps a self-consistent digest while serving the wrong document's
    text for the addressed citation.
    """
    corpus_path, payload = _first_shipped_sidecar()
    stored_sha256 = payload["source_sha256"]
    assert isinstance(stored_sha256, str)
    payload["corpus_path"] = "corpus/manuals/some/other/source.pdf"

    assert _validated_sidecar_text(json.dumps(payload), corpus_path, stored_sha256) is None
