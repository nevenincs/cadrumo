"""Corpus reads behind legal grounding answer per FILE, not per reference.

Grounding is verified for each legal reference, but three of its inputs are
decided by the cited file alone: the resolved path trio, the sidecar
fingerprint the corpus-text cache keys on, and the document's dated-redaction
count. Asking them per reference made verifying the 1404-entry catalogue
re-resolve, re-hash and re-decode the same 388 files -- 6.48s, of which 1.88s
was decoding documents like the 1.9 MB ``ley-35-2006.html`` 86 times. These
gates hold the per-file answer and the invalidation that keeps it honest.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from cadrumo.core.corpus_text import corpus_redaction_marks
from cadrumo.core.hashing import blake2b_hex

from ..compiler.legal_grounding import (
    _corpus_file_digest,
    _corpus_redaction_mark_count,
    _resolved_corpus_paths,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REDACTION_DOCUMENT = (
    b'<version id_norma="BOE-A-2020-1234" fecha_vigencia="20200101">primera</version>'
    b'<version id_norma="BOE-A-2021-5678" fecha_vigencia="20210101">segunda</version>'
)


def _document(tmp_path: Path, name: str, payload: bytes) -> Path:
    path = tmp_path / "corpus" / "normatives" / "html" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def _touch_forward(path: Path) -> None:
    """Advance the file's mtime so a stat-keyed memo observes a new identity."""
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))


def test_a_file_cited_by_many_references_is_hashed_once(tmp_path: Path) -> None:
    path = _document(tmp_path, "ley.html", b"<p>text</p>")
    _corpus_file_digest.cache_clear()
    stat = path.stat()

    digests = {_corpus_file_digest(str(path), stat.st_size, stat.st_mtime_ns) for _ in range(5)}

    assert digests == {blake2b_hex(path.read_bytes())}, "the memo must not change the fingerprint"
    info = _corpus_file_digest.cache_info()
    assert info.misses == 1, "one file must be hashed exactly once however many references cite it"
    assert info.hits == 4


def test_an_edited_file_is_fingerprinted_afresh(tmp_path: Path) -> None:
    path = _document(tmp_path, "ley.html", b"<p>text</p>")
    _corpus_file_digest.cache_clear()
    original = _corpus_file_digest(*_fingerprint(path))

    path.write_bytes(b"<p>revised text</p>")
    _touch_forward(path)

    assert _corpus_file_digest(*_fingerprint(path)) != original


def _fingerprint(path: Path) -> tuple[str, int, int]:
    stat = path.stat()
    return str(path), stat.st_size, stat.st_mtime_ns


def test_a_documents_redactions_are_counted_once_and_match_the_marks(tmp_path: Path) -> None:
    path = _document(tmp_path, "ley.html", _REDACTION_DOCUMENT)
    _corpus_redaction_mark_count.cache_clear()
    expected = len(corpus_redaction_marks(path.read_text(encoding="utf-8", errors="replace")))

    counts = {_corpus_redaction_mark_count(*_fingerprint(path)) for _ in range(4)}

    assert counts == {expected}, "the memo must not change the count the refusal reports"
    info = _corpus_redaction_mark_count.cache_info()
    assert info.misses == 1, "one document must be decoded exactly once"
    assert info.hits == 3


def test_an_edited_document_is_recounted(tmp_path: Path) -> None:
    path = _document(tmp_path, "ley.html", _REDACTION_DOCUMENT)
    _corpus_redaction_mark_count.cache_clear()
    before = _corpus_redaction_mark_count(*_fingerprint(path))

    path.write_bytes(b"<p>one consolidated text</p>")
    _touch_forward(path)

    after = _corpus_redaction_mark_count(*_fingerprint(path))
    assert before >= 2, "the fixture must start fused, or the invalidation proves nothing"
    assert after < 2


def test_one_corpus_path_resolves_its_sidecars_once(tmp_path: Path) -> None:
    _document(tmp_path, "ley.html", b"<p>text</p>")
    root = tmp_path.resolve()
    _resolved_corpus_paths.cache_clear()

    results = {_resolved_corpus_paths(root, "corpus/normatives/html/ley.html") for _ in range(6)}

    (document, annotation, sidecar) = next(iter(results))
    assert len(results) == 1
    assert document.name == "ley.html"
    assert annotation.name == "ley.html.annotation.json"
    assert sidecar.name == "ley.html.extracted.json"
    info = _resolved_corpus_paths.cache_info()
    assert info.misses == 1, "one path must reach the filesystem resolver exactly once"
    assert info.hits == 5


def test_a_different_root_resolves_separately(tmp_path: Path) -> None:
    """The memo keys on the root too, so two roots cannot share one answer."""
    other = tmp_path / "other"
    other.mkdir()
    _resolved_corpus_paths.cache_clear()

    first = _resolved_corpus_paths(tmp_path.resolve(), "corpus/normatives/html/ley.html")
    second = _resolved_corpus_paths(other.resolve(), "corpus/normatives/html/ley.html")

    assert first != second
    assert _resolved_corpus_paths.cache_info().misses == 2
