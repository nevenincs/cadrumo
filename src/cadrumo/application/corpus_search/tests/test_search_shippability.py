"""Licence/footprint shippability gate for the corpus-search surface.

Confirms the wheel ships the light, licence-clean data (the extracted
corpus triples the index builds from) and NOT the heavy model footprint:
no model weights, no onnxruntime, no caches, no precompiled index. Also
confirms the degraded, no-download mode is importable without the search
extra and that the FTS index build is deterministic. Real-behavior only:
no skips, tmp_path SQLite, assertions on the packaged-data tree that
SHIPS rather than on any optional runtime download.
"""

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path

import pytest

from ....core.resources import bundled_path
from .._embed_build import embed_corpus
from .._errors import CorpusSearchDependencyError
from .._lexical_index import build_lexical_index, iter_corpus_chunks
from .._models import CorpusChunk
from .._query_embed import search_extra_available
from ._corpus_fixture import build_sample_corpus

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
_MODEL2VEC_PRESENT = importlib.util.find_spec("model2vec") is not None

# Model-weight / runtime / cache artifacts that must never ship in the wheel.
_FORBIDDEN_SUFFIXES = frozenset(
    {
        ".onnx",
        ".safetensors",
        ".bin",
        ".pt",
        ".pth",
        ".ckpt",
        ".gguf",
        ".h5",
        ".msgpack",
        ".tflite",
        ".npy",
        ".npz",
        ".sqlite",
        ".db",
    }
)
_FORBIDDEN_DIR_NAMES = frozenset({"onnxruntime", "model2vec", ".cache", "__pycache__"})


def _iter_files(root: Path):
    for path in root.rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts:
            yield path


def test_lexical_and_citation_modules_import_without_search_extra() -> None:
    # The degraded lexical-only mode must import with no semantic stack; a
    # real import-machinery check, not a mock.
    for module in (
        "cadrumo.application.corpus_search._lexical_index",
        "cadrumo.application.corpus_search._citation_lookup",
        "cadrumo.application.corpus_search",
    ):
        assert importlib.import_module(module) is not None


def test_embed_surface_carries_degraded_mode(tmp_path: Path) -> None:
    # When the search extra is absent (the shipped default) the embed path
    # refuses with the install hint; that refusal path stays live — the
    # degraded no-download contract this gate protects. When the extra is
    # present, the actual embed is a network-download path this unit gate
    # does not drive (mirrors
    # test_query_embed.py::test_embed_query_matches_environment_capability);
    # the real build is proven in the opt-in
    # test_hybrid_real_model_recall_live.py instead.
    chunks = [
        CorpusChunk(
            chunk_id="a:000:00",
            corpus_ref="corpus/normatives/html/x.html#a1",
            source_path="corpus/normatives/html/x.html",
            doc_title="X",
            ordinal=0,
            text="texto",
        )
    ]
    if _MODEL2VEC_PRESENT:
        assert search_extra_available() is True
        return
    with pytest.raises(CorpusSearchDependencyError) as exc_info:
        embed_corpus(chunks, matrix_path=tmp_path / "m.npy", chunk_ids_path=tmp_path / "ids.json")
    assert exc_info.value.suggestion == "pip install cadrumo[search]"


def test_corpus_search_package_ships_no_model_artifacts() -> None:
    offenders = [
        path.relative_to(_PACKAGE_ROOT).as_posix()
        for path in _iter_files(_PACKAGE_ROOT)
        if path.suffix.lower() in _FORBIDDEN_SUFFIXES
    ]
    assert not offenders, f"corpus_search package must ship no weights/index artifacts, found: {offenders}"


def test_corpus_search_package_has_no_model_or_cache_dirs() -> None:
    offenders = [
        path.relative_to(_PACKAGE_ROOT).as_posix()
        for path in _PACKAGE_ROOT.rglob("*")
        if path.is_dir() and path.name in (_FORBIDDEN_DIR_NAMES - {"__pycache__"})
    ]
    assert not offenders, f"corpus_search package must ship no model/cache dirs, found: {offenders}"


def test_bundled_data_ships_no_model_weights() -> None:
    # The whole bundled _data tree must be free of model weights and
    # runtimes: only the light, licence-clean corpus text data ships.
    weight_suffixes = _FORBIDDEN_SUFFIXES - {".sqlite", ".db", ".npy", ".npz"}
    data_root = bundled_path()
    offenders = [
        path.relative_to(data_root).as_posix()
        for path in _iter_files(data_root)
        if path.suffix.lower() in weight_suffixes
    ]
    assert not offenders, f"bundled _data must ship no model weights, found: {offenders[:10]}"


def test_bundled_corpus_ships_extracted_triples() -> None:
    # The shippable LIGHT data the index builds from must be present.
    from .._lexical_index import bundled_corpus_html_root

    extracted = list(bundled_corpus_html_root().glob("*.html.extracted.json"))
    assert len(extracted) > 100, f"expected the shipped extracted corpus triples, found {len(extracted)}"


def test_fts_chunk_ids_deterministic_across_builds(tmp_path: Path) -> None:
    corpus = build_sample_corpus(tmp_path / "corpus")
    chunk_ids = [chunk.chunk_id for chunk in iter_corpus_chunks(corpus)]

    first_db = tmp_path / "first.sqlite"
    second_db = tmp_path / "second.sqlite"
    build_lexical_index(first_db, iter_corpus_chunks(corpus))
    build_lexical_index(second_db, iter_corpus_chunks(corpus))

    assert _index_chunk_ids(first_db) == chunk_ids
    assert _index_chunk_ids(second_db) == chunk_ids


def _index_chunk_ids(database_path: Path) -> list[str]:
    import sqlite3

    connection = sqlite3.connect(database_path)
    try:
        rows = connection.execute("SELECT chunk_id FROM chunks ORDER BY rowid").fetchall()
    finally:
        connection.close()
    return [row[0] for row in rows]
