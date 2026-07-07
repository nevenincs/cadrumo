"""End-to-end proof that the REAL potion model fuses semantic recall into search.

The sibling `test_retrieval.py` proves the fusion MECHANICS (RRF, per-side ranks,
clean degradation) with injected fixed vectors, so it never downloads the model.
This test closes the remaining gap the refoundation close deferred (item 2 / H1):
that the REAL `potion-multilingual-128M` embeddings actually recall a
semantically-related chunk a lexical query misses — the whole point of shipping
the semantic half.

It is gated on `search_extra_available()` rather than skipped: with the
`aeat-cli[search]` extra present it runs the real proof (building a real embedding
matrix via `embed_corpus` and querying with the real `QueryEmbedder`); without
it, it asserts the degraded lexical-only contract. Both branches assert real
behaviour — there is no `skip`/`xfail`.

The shippability/licence gate stays green: this builds its matrix in a tmp dir
and ships nothing (per `shipped-search-licence-clean` / the "no matrix ships"
decision — vectors are built behind the extra, never bundled).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ....core.config import override_settings
from .. import (
    CorpusChunk,
    QueryEmbedder,
    RetrievalMode,
    build_lexical_index,
    corpus_search_dir,
    embed_corpus,
    ensure_corpus_embeddings,
    hybrid_search,
    load_embeddings,
    search_extra_available,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

# A cross-lingual vocabulary mismatch: the target chunk is Spanish; the query is
# English. A Spanish stemmer cannot lexically bridge the two, but the multilingual
# potion embedder places them close — exactly the recall the semantic half exists
# to add. The distractors share the domain (AEAT tax prose) but not the concept.
_TARGET = "recargo-chunk"
_QUERY = "special VAT surcharge scheme for retail shopkeepers"

_CHUNKS = (
    CorpusChunk(
        chunk_id=_TARGET,
        corpus_ref="liva:art-154",
        source_path="corpus/normatives/html/liva.html",
        doc_title="Ley del IVA",
        ordinal=0,
        text="El recargo de equivalencia es un régimen especial del IVA para comerciantes minoristas.",
    ),
    CorpusChunk(
        chunk_id="irpf-chunk",
        corpus_ref="lirpf:art-1",
        source_path="corpus/normatives/html/lirpf.html",
        doc_title="Ley del IRPF",
        ordinal=1,
        text="El modelo 100 declara el IRPF anual de las personas físicas y sus rentas.",
    ),
    CorpusChunk(
        chunk_id="deadline-chunk",
        corpus_ref="orden:plazo",
        source_path="corpus/normatives/html/orden.html",
        doc_title="Orden de plazos",
        ordinal=2,
        text="El plazo de presentación del modelo 303 finaliza el 20 de abril.",
    ),
)


def _lexical_index(tmp_path: Path) -> Path:
    database_path = tmp_path / "index.sqlite"
    build_lexical_index(database_path, _CHUNKS)
    return database_path


def test_lexical_only_misses_the_cross_lingual_target(tmp_path: Path) -> None:
    # Baseline: the English query cannot lexically reach the Spanish target, so
    # lexical-only retrieval does NOT surface it (the gap the semantic half fills).
    database_path = _lexical_index(tmp_path)
    response = hybrid_search(_QUERY, database_path=database_path, limit=5)
    assert response.mode is RetrievalMode.LEXICAL_ONLY
    assert _TARGET not in {hit.chunk_id for hit in response.hits}


def test_real_potion_embeddings_recall_the_target_via_hybrid(tmp_path: Path) -> None:
    if not search_extra_available():
        # Without the extra the semantic side cannot run; hybrid_search must
        # degrade to lexical-only rather than raise. (The real recall proof runs
        # in the search-extra lane where the model is present.)
        database_path = _lexical_index(tmp_path)
        response = hybrid_search(
            _QUERY,
            database_path=database_path,
            query_embedder=QueryEmbedder(),
            limit=5,
        )
        assert response.mode is RetrievalMode.LEXICAL_ONLY
        return

    database_path = _lexical_index(tmp_path)
    matrix_path = tmp_path / "matrix.npy"
    chunk_ids_path = tmp_path / "chunk_ids.json"
    build_result = embed_corpus(_CHUNKS, matrix_path=matrix_path, chunk_ids_path=chunk_ids_path)
    assert build_result.chunk_count == len(_CHUNKS)
    assert build_result.dimensions > 0

    matrix, chunk_ids = load_embeddings(matrix_path, chunk_ids_path)
    response = hybrid_search(
        _QUERY,
        database_path=database_path,
        embeddings=(matrix, chunk_ids),
        query_embedder=QueryEmbedder(),
        limit=5,
    )

    # The real semantic side fused a hit the lexical side could not reach.
    assert response.mode is RetrievalMode.HYBRID
    recalled = {hit.chunk_id for hit in response.hits}
    assert _TARGET in recalled, f"real potion embeddings failed to recall the cross-lingual target: {recalled}"
    # And it is the top fused hit — semantic recall is decisive here, not noise.
    assert response.hits[0].chunk_id == _TARGET


def test_ensure_corpus_embeddings_is_none_without_the_extra(tmp_path: Path) -> None:
    # Bare-core default: no extra -> no build, no download, lexical-only. The
    # explicit runtime input keeps this assertion stable even in an env where
    # the extra happens to be installed.
    with override_settings(aeat_local_storage_root=tmp_path):
        assert ensure_corpus_embeddings(semantic_available=False) is None
        assert not (corpus_search_dir() / "corpus-vectors.npy").exists()


def test_ensure_corpus_embeddings_builds_once_behind_the_extra(tmp_path: Path) -> None:
    # The runtime build step: behind the extra, the corpus matrix is built once
    # into the app cache and reused. A small chunk set stands in for the whole
    # bundled corpus so the test does not embed thousands of chunks.
    if not search_extra_available():
        with override_settings(aeat_local_storage_root=tmp_path):
            assert ensure_corpus_embeddings(corpus_chunks=_CHUNKS) is None
        return

    with override_settings(aeat_local_storage_root=tmp_path):
        first = ensure_corpus_embeddings(corpus_chunks=_CHUNKS)
        assert first is not None
        matrix, chunk_ids = first
        assert matrix.shape[0] == len(_CHUNKS)
        assert set(chunk_ids) == {chunk.chunk_id for chunk in _CHUNKS}
        vector_file = corpus_search_dir() / "corpus-vectors.npy"
        assert vector_file.exists()
        first_mtime = vector_file.stat().st_mtime_ns

        # Second call reuses the cached matrix (no rebuild).
        second = ensure_corpus_embeddings(corpus_chunks=_CHUNKS)
        assert second is not None
        assert vector_file.stat().st_mtime_ns == first_mtime
