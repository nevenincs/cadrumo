"""Deterministic, network-free half of the hybrid real-model recall proof.

The REAL `potion-multilingual-128M` recall proof — and the runtime build-once
cache reuse proof — genuinely need the real model and a real network fetch (or
a warm local cache), so they live in the opt-in sibling
`test_hybrid_real_model_recall_live.py` instead (gated on
`CADRUMO_LIVE_TESTS_ENABLED=1`, per `src/cadrumo/tests/README.md`). This module
covers everything that can be asserted deterministically and without ever
constructing a live model: that lexical-only retrieval genuinely misses a
cross-lingual target (the gap the semantic half exists to fill), that
`hybrid_search` degrades to lexical-only whenever no precomputed corpus vectors
are supplied — even with a real (but unloaded) `QueryEmbedder` instance passed
in, since `_semantic_ranks` short-circuits on `embeddings is None` before ever
calling `embed_query` — and that `ensure_corpus_embeddings` reports the bare-core
degraded default when the semantic side is explicitly unavailable.

Previously this module branched on `search_extra_available()` to run its real
proof only when the `cadrumo[search]` extra happened to be importable, which
made a plain integration run silently reach huggingface.co whenever a host
had the extra installed with a cold model cache. No test here reaches the
network any more; the real proof moved to the live-gated sibling module.
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
    ensure_corpus_embeddings,
    hybrid_search,
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


def test_hybrid_search_degrades_to_lexical_only_without_precomputed_embeddings(tmp_path: Path) -> None:
    # Even with a real (but unloaded) QueryEmbedder passed in, hybrid_search
    # degrades to lexical-only whenever no precomputed corpus vectors are
    # supplied: `_semantic_ranks` short-circuits on `embeddings is None` before
    # ever calling `embed_query`, so constructing `QueryEmbedder()` here never
    # loads the model (mirrors
    # test_query_embed.py::test_construction_is_lazy_and_does_not_load_the_model)
    # and this assertion holds unconditionally, with no branch on
    # `search_extra_available()`. The real recall proof (extra present, real
    # embeddings supplied) lives in the opt-in
    # test_hybrid_real_model_recall_live.py.
    database_path = _lexical_index(tmp_path)
    response = hybrid_search(
        _QUERY,
        database_path=database_path,
        query_embedder=QueryEmbedder(),
        limit=5,
    )
    assert response.mode is RetrievalMode.LEXICAL_ONLY


def test_ensure_corpus_embeddings_is_none_without_the_extra(tmp_path: Path) -> None:
    # Bare-core default: no extra -> no build, no download, lexical-only. The
    # explicit runtime input keeps this assertion stable even in an env where
    # the extra happens to be installed.
    with override_settings(cadrumo_local_storage_root=tmp_path):
        assert ensure_corpus_embeddings(semantic_available=False) is None
        assert not (corpus_search_dir() / "corpus-vectors.npy").exists()
