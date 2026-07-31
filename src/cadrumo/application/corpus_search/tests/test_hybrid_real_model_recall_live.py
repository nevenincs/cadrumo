"""Opt-in live proof that the REAL potion model fuses semantic recall into search.

The sibling `test_hybrid_real_model_recall.py` proves everything about the
hybrid retriever that can be asserted deterministically and without a live
model; `test_retrieval.py` proves the fusion MECHANICS (RRF, per-side ranks,
clean degradation) with injected fixed vectors. Neither downloads the model.
THIS module closes the remaining gap the refoundation close deferred
(item 2 / H1): that the REAL `potion-multilingual-128M` embeddings actually
recall a semantically-related chunk a lexical query misses — the whole point
of shipping the semantic half — and that the runtime build-once cache
(`ensure_corpus_embeddings`) actually reuses a real precomputed matrix rather
than rebuilding it.

Both proofs genuinely need the real model and a real network fetch (first use,
or a warm local cache thereafter), so unlike the deterministic sibling they
cannot be forced into a network-free branch without becoming vacuous. They are
gated behind the same opt-in the project uses for every other live-network
test — `CADRUMO_LIVE_TESTS_ENABLED=1` via `requires_live_enabled()`
(`src/cadrumo/tests/live_gate.py`) — which FAILS rather than silently skips
when the opt-in is unset, per `src/cadrumo/tests/README.md`. Run deliberately
with `uv run pytest -m aeat_live`, never incidentally on a plain `pytest`
invocation (these previously lived in the `integration` lane, gated only on
`search_extra_available()`, so a host with the `cadrumo[search]` extra
installed and a cold model cache reached huggingface.co on a plain
`-m integration` run with no opt-in).

The shippability/licence gate stays green: this builds its matrix in a tmp dir
and ships nothing (per `shipped-search-licence-clean` / the "no matrix ships"
decision — vectors are built behind the extra, never bundled).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ....core.config import override_settings
from ....tests.live_gate import requires_live_enabled
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
)

pytestmark = [pytest.mark.aeat_live, pytest.mark.hex_application]

# Mirrors test_hybrid_real_model_recall.py's fixture: a cross-lingual
# vocabulary mismatch the multilingual potion embedder bridges and a
# Spanish stemmer cannot. The distractors share the domain (AEAT tax prose)
# but not the concept.
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


def test_real_potion_embeddings_recall_the_target_via_hybrid(tmp_path: Path) -> None:
    requires_live_enabled()

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


def test_ensure_corpus_embeddings_builds_once_behind_the_extra(tmp_path: Path) -> None:
    requires_live_enabled()

    # The runtime build step: behind the extra, the corpus matrix is built once
    # into the app cache and reused. A small chunk set stands in for the whole
    # bundled corpus so the test does not embed thousands of chunks.
    with override_settings(cadrumo_local_storage_root=tmp_path):
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
