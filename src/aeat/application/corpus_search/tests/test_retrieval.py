"""Real-behavior tests for hybrid retrieval and RRF fusion.

The retrieval logic (FTS5 lexical + numpy cosine + RRF fusion + citation
short-circuit + lexical-only degrade) is exercised over a small real
bundled-corpus index. The semantic side needs a live query vector; rather
than trigger the optional potion model download, two thin QueryEmbedder
subclasses supply a fixed real vector or a deterministic dependency
refusal — a permitted unit-test isolation of the external model that keeps
the fusion, cosine, and assembly logic under real numpy arrays.
"""

from __future__ import annotations

from pathlib import Path
from typing import override

import numpy as np
import pytest

from .._errors import CorpusSearchDependencyError, CorpusSearchInputError
from .._lexical_index import build_lexical_index, iter_corpus_chunks
from .._models import RetrievalMode
from .._query_embed import QueryEmbedder
from .._retrieval import hybrid_search
from ._corpus_fixture import build_sample_corpus

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DIMS = 6


class _FixedVectorEmbedder(QueryEmbedder):
    """Return one fixed real vector, isolating retrieval from the model download."""

    def __init__(self, vector: np.ndarray) -> None:
        super().__init__(cache_dir=Path("unused"))
        self._vector = np.asarray(vector, dtype=np.float32)

    @override
    def embed_query(self, text: str) -> np.ndarray:
        if not text.strip():
            raise CorpusSearchInputError("empty", context={"query": text})
        return self._vector


class _UnavailableEmbedder(QueryEmbedder):
    """Refuse as if the search extra were absent, to prove clean degrade."""

    @override
    def embed_query(self, text: str) -> np.ndarray:
        raise CorpusSearchDependencyError("model2vec absent", suggestion="pip install aeat-cli[search]")


def _index_and_chunks(tmp_path: Path) -> tuple[Path, list[str]]:
    corpus = build_sample_corpus(tmp_path / "corpus")
    chunks = list(iter_corpus_chunks(corpus))
    database_path = tmp_path / "index.sqlite"
    build_lexical_index(database_path, chunks)
    return database_path, [chunk.chunk_id for chunk in chunks]


def _deterministic_matrix(chunk_ids: list[str]) -> np.ndarray:
    rng = np.random.default_rng(1234)
    return rng.standard_normal((len(chunk_ids), _DIMS)).astype(np.float32)


def test_lexical_only_when_no_embeddings(tmp_path: Path) -> None:
    database_path, _ids = _index_and_chunks(tmp_path)
    response = hybrid_search("recargo declaración extemporánea", database_path=database_path, limit=5)
    assert response.mode is RetrievalMode.LEXICAL_ONLY
    assert response.hits
    assert response.hits[0].corpus_ref.endswith("ley-58-2003-art-27.html")
    assert response.hits[0].semantic_rank is None
    assert response.hits[0].lexical_rank == 0


def test_degrades_to_lexical_only_when_embedder_unavailable(tmp_path: Path) -> None:
    database_path, ids = _index_and_chunks(tmp_path)
    matrix = _deterministic_matrix(ids)
    response = hybrid_search(
        "recargo",
        database_path=database_path,
        embeddings=(matrix, ids),
        query_embedder=_UnavailableEmbedder(),
        limit=5,
    )
    assert response.mode is RetrievalMode.LEXICAL_ONLY
    assert response.hits


def test_hybrid_mode_fuses_semantic_side(tmp_path: Path) -> None:
    database_path, ids = _index_and_chunks(tmp_path)
    matrix = _deterministic_matrix(ids)
    # Query vector identical to a specific chunk's row -> that chunk is the
    # semantic nearest and must surface with a semantic_rank.
    target_index = len(ids) // 2
    embedder = _FixedVectorEmbedder(matrix[target_index])
    response = hybrid_search(
        "recargo",
        database_path=database_path,
        embeddings=(matrix, ids),
        query_embedder=embedder,
        limit=10,
    )
    assert response.mode is RetrievalMode.HYBRID
    by_id = {hit.chunk_id: hit for hit in response.hits}
    assert ids[target_index] in by_id
    assert by_id[ids[target_index]].semantic_rank == 0
    assert any(hit.semantic_rank is not None for hit in response.hits)


def test_rrf_ranks_dual_side_hit_above_single_side(tmp_path: Path) -> None:
    database_path, ids = _index_and_chunks(tmp_path)
    matrix = _deterministic_matrix(ids)
    # Point the query vector at the chunk the lexical query also ranks first,
    # so it scores on both sides and must lead the fused order.
    lexical_first = hybrid_search("recargo extemporánea", database_path=database_path, limit=1).hits[0].chunk_id
    lexical_index = ids.index(lexical_first)
    embedder = _FixedVectorEmbedder(matrix[lexical_index])
    response = hybrid_search(
        "recargo extemporánea",
        database_path=database_path,
        embeddings=(matrix, ids),
        query_embedder=embedder,
        limit=10,
    )
    assert response.mode is RetrievalMode.HYBRID
    assert response.hits[0].chunk_id == lexical_first
    assert response.hits[0].lexical_rank is not None
    assert response.hits[0].semantic_rank is not None
    scores = [hit.score for hit in response.hits]
    assert scores == sorted(scores, reverse=True)


def test_citation_short_circuit(tmp_path: Path) -> None:
    from .._citation_lookup import bundled_citation_lookup

    database_path, _ids = _index_and_chunks(tmp_path)
    response = hybrid_search(
        "ley-58-2003:art-27.2",
        database_path=database_path,
        citation_lookup=bundled_citation_lookup(),
        limit=5,
    )
    assert response.mode is RetrievalMode.CITATION
    assert response.citation is not None
    assert response.citation.document_id == "BOE-A-2003-23186"
    assert "extempor" in response.citation.verbatim_text.lower()
    assert response.hits == ()


def test_empty_query_refused(tmp_path: Path) -> None:
    database_path, _ids = _index_and_chunks(tmp_path)
    with pytest.raises(CorpusSearchInputError):
        hybrid_search("   ", database_path=database_path)


def test_nonpositive_limit_refused(tmp_path: Path) -> None:
    database_path, _ids = _index_and_chunks(tmp_path)
    with pytest.raises(CorpusSearchInputError):
        hybrid_search("recargo", database_path=database_path, limit=0)
