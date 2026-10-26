"""Runtime cache identity and atomic-publication behavior."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path

import pytest

from .. import runtime
from ..lexical_index import build_lexical_index, iter_corpus_chunks, search_lexical
from ..models import CorpusChunk, CorpusIndexBuildResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _source(root: Path, *, text: str = "recargo inicial") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / "sample.html.extracted.json"
    path.write_text(
        json.dumps({"units": [{"title": "Sample", "anchor": "a", "text": text}]}),
        encoding="utf-8",
    )
    return path


def _arrange(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[Path, Path]:
    corpus_root = tmp_path / "corpus"
    database_path = tmp_path / "cache" / "corpus.sqlite3"
    monkeypatch.setattr(runtime, "bundled_corpus_html_root", lambda: corpus_root)
    monkeypatch.setattr(runtime, "corpus_index_path", lambda settings=None: database_path)
    return corpus_root, database_path


def test_unchanged_sources_reuse_the_published_index(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    corpus_root, database_path = _arrange(monkeypatch, tmp_path)
    _source(corpus_root)
    runtime.ensure_corpus_index()
    first_bytes = database_path.read_bytes()

    def unexpected_build(database_path: Path, chunks: object) -> object:
        raise AssertionError("an unchanged corpus must reuse its index")

    monkeypatch.setattr(runtime, "build_lexical_index", unexpected_build)
    assert runtime.ensure_corpus_index() == database_path
    assert database_path.read_bytes() == first_bytes


def test_same_size_source_edit_invalidates_the_index(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    corpus_root, database_path = _arrange(monkeypatch, tmp_path)
    source = _source(corpus_root, text="recargo inicial")
    runtime.ensure_corpus_index()
    original_size = source.stat().st_size

    _source(corpus_root, text="recargo cambiox")
    assert source.stat().st_size == original_size
    runtime.ensure_corpus_index()

    assert not search_lexical(database_path, "inicial")
    assert search_lexical(database_path, "cambiox")


def test_removed_source_invalidates_without_retaining_old_rows(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    corpus_root, database_path = _arrange(monkeypatch, tmp_path)
    source = _source(corpus_root)
    runtime.ensure_corpus_index()
    assert search_lexical(database_path, "recargo")

    source.unlink()
    runtime.ensure_corpus_index()

    assert not search_lexical(database_path, "recargo")


def test_index_without_identity_metadata_is_rebuilt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    corpus_root, database_path = _arrange(monkeypatch, tmp_path)
    _source(corpus_root, text="contenido actual")
    database_path.parent.mkdir(parents=True)
    build_lexical_index(database_path, iter_corpus_chunks(corpus_root))
    calls = 0
    real_builder = runtime.build_lexical_index

    def counted_build(path: Path, chunks: Iterable[CorpusChunk]) -> CorpusIndexBuildResult:
        nonlocal calls
        calls += 1
        return real_builder(path, chunks)

    monkeypatch.setattr(runtime, "build_lexical_index", counted_build)
    runtime.ensure_corpus_index()
    assert calls == 1
    assert runtime._stored_identity(database_path) == runtime._corpus_identity(corpus_root)


def test_interrupted_rebuild_never_partially_publishes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    corpus_root, database_path = _arrange(monkeypatch, tmp_path)
    _source(corpus_root, text="contenido inicial")
    runtime.ensure_corpus_index()
    published_digest = hashlib.sha256(database_path.read_bytes()).digest()
    _source(corpus_root, text="contenido cambiado")

    def interrupted_build(path: Path, chunks: object) -> object:
        path.write_bytes(b"partial")
        raise RuntimeError("simulated interruption")

    monkeypatch.setattr(runtime, "build_lexical_index", interrupted_build)
    with pytest.raises(RuntimeError, match="simulated interruption"):
        runtime.ensure_corpus_index()

    assert hashlib.sha256(database_path.read_bytes()).digest() == published_digest
    assert not tuple(database_path.parent.glob(f".{database_path.name}.*.tmp"))
