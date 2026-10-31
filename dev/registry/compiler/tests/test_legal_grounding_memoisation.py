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

from cadrumo.core.hashing import blake2b_hex
from dev.corpus.text import corpus_redaction_marks

from .. import legal_grounding
from ..corpus_provenance import corpus_content_digest, corpus_digest_pass
from ..legal_grounding import (
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


def _forge_stat_preserving_rewrite(path: Path, payload: bytes) -> None:
    """Rewrite ``path`` at its original size and restore its mtime, as a forged stat identity would."""
    original = path.stat()
    assert len(payload) <= original.st_size
    path.write_bytes(payload.ljust(original.st_size, b" "))
    os.utime(path, ns=(original.st_atime_ns, original.st_mtime_ns))
    rewritten = path.stat()
    assert (rewritten.st_size, rewritten.st_mtime_ns) == (original.st_size, original.st_mtime_ns)


def _count_reads(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    reads: list[Path] = []
    original = Path.read_bytes

    def counting_read_bytes(path: Path) -> bytes:
        reads.append(path)
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", counting_read_bytes)
    return reads


def test_a_file_cited_by_many_references_is_hashed_once_per_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _document(tmp_path, "ley.html", b"<p>text</p>")
    reads = _count_reads(monkeypatch)

    with corpus_digest_pass():
        digests = {corpus_content_digest(path) for _ in range(5)}

    assert digests == {blake2b_hex(b"<p>text</p>")}, "the memo must not change the fingerprint"
    assert reads.count(path) == 1, "one file must be hashed exactly once per pass however many references cite it"


def test_a_new_pass_observes_a_stat_preserving_rewrite(tmp_path: Path) -> None:
    path = _document(tmp_path, "ley.html", b"<p>text</p>")
    with corpus_digest_pass():
        original = corpus_content_digest(path)

    _forge_stat_preserving_rewrite(path, b"<p>txet</p>")

    with corpus_digest_pass():
        assert corpus_content_digest(path) != original
    assert corpus_content_digest(path) != original, "outside a pass the current bytes are hashed"


def test_a_documents_redactions_are_counted_once_and_match_the_marks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _document(tmp_path, "ley.html", _REDACTION_DOCUMENT)
    legal_grounding._REDACTION_MARK_COUNTS.clear()
    expected = len(corpus_redaction_marks(path.read_text(encoding="utf-8", errors="replace")))
    reads = _count_reads(monkeypatch)

    with corpus_digest_pass():
        counts = {_corpus_redaction_mark_count(path) for _ in range(4)}

    assert counts == {expected}, "the memo must not change the count the refusal reports"
    assert reads.count(path) == 2, "one digest read and one decoding read, however many references ask"


def test_a_stat_preserving_rewrite_is_recounted(tmp_path: Path) -> None:
    path = _document(tmp_path, "ley.html", _REDACTION_DOCUMENT)
    legal_grounding._REDACTION_MARK_COUNTS.clear()
    before = _corpus_redaction_mark_count(path)

    _forge_stat_preserving_rewrite(path, b"<p>one consolidated text</p>")

    after = _corpus_redaction_mark_count(path)
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
