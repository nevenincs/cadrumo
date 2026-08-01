"""Hybrid corpus retrieval: FTS5 lexical + semantic cosine, RRF-fused (R3).

The R3 grounding search runs three cooperating retrievers and fuses them:

* an exact-citation short-circuit — when the query IS a citation id
  (``ley-58-2003:art-27.2``), it resolves directly through the structured
  lookup, no ranking needed;
* the FTS5 lexical index
  (:mod:`~application.corpus_search._lexical_index`) for exact and stemmed
  in-prose recall;
* a brute-force numpy cosine over the build-time-precomputed corpus matrix,
  with the live query embedded by :class:`~application.corpus_search.QueryEmbedder`.

The lexical and semantic rankings are fused with Reciprocal Rank Fusion
(RRF, ``k=60``), each side capped at its top ~50, in plain Python — no ANN
index earns its keep at this corpus scale. When the semantic side is
unavailable (the ``search`` extra absent, or no precomputed vectors supplied)
the retriever degrades cleanly to lexical-only, so a bare-core install still
grounds an operator against the corpus.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from ._citation_lookup import CitationLookup
from ._errors import CorpusSearchDependencyError, CorpusSearchInputError
from ._lexical_index import search_lexical
from ._models import LexicalSearchHit, RetrievalHit, RetrievalMode, RetrievalResponse
from ._query_embed import QueryEmbedder
from ._ranking import RRF_K, l2_normalise, reciprocal_rank_fusion

if TYPE_CHECKING:
    import numpy as np

#: Per-side result cap before fusion; a generous top-N keeps fusion cheap.
PER_SIDE_CAP = 50


def hybrid_search(
    query: str,
    *,
    database_path: Path,
    embeddings: tuple[np.ndarray, Sequence[str]] | None = None,
    query_embedder: QueryEmbedder | None = None,
    citation_lookup: CitationLookup | None = None,
    limit: int = 10,
    rrf_k: int = RRF_K,
    per_side_cap: int = PER_SIDE_CAP,
) -> RetrievalResponse:
    """Run hybrid retrieval for ``query`` and return a typed response.

    Args:
        query: The free-text query, or an exact citation id.
        database_path: A lexical index built by ``build_lexical_index``.
        embeddings: Optional ``(matrix, chunk_ids)`` precomputed corpus
            vectors; when omitted the semantic side is off (lexical-only).
        query_embedder: Optional embedder for the live query; when omitted or
            unavailable, the semantic side is off.
        citation_lookup: Optional catalogue lookup enabling the exact-citation
            short-circuit.
        limit: Maximum number of fused hits to return.
        rrf_k: The RRF damping constant.
        per_side_cap: Per-side result cap before fusion.

    Returns:
        A :class:`RetrievalResponse` — a citation resolution, or ranked hits
        with the mode (hybrid or lexical-only) that produced them.

    Raises:
        CorpusSearchInputError: If ``query`` is blank or ``limit`` is not
            positive.
    """
    cleaned = query.strip()
    if not cleaned:
        raise CorpusSearchInputError("retrieval query must be non-empty", context={"query": query})
    if limit <= 0:
        raise CorpusSearchInputError("retrieval limit must be positive", context={"limit": limit})

    if citation_lookup is not None and cleaned in set(citation_lookup.citation_ids):
        return RetrievalResponse(
            query=cleaned,
            mode=RetrievalMode.CITATION,
            citation=citation_lookup.resolve(cleaned),
        )

    lexical_hits = search_lexical(database_path, cleaned, limit=per_side_cap)
    lexical_rank_by_id = {hit.chunk_id: index for index, hit in enumerate(lexical_hits)}

    semantic_rank_by_id, mode = _semantic_ranks(
        query=cleaned,
        embeddings=embeddings,
        query_embedder=query_embedder,
        per_side_cap=per_side_cap,
    )

    fused = reciprocal_rank_fusion(lexical_rank_by_id, semantic_rank_by_id, rrf_k=rrf_k)[:limit]
    hits = _assemble_hits(
        fused=fused,
        lexical_hits=lexical_hits,
        lexical_rank_by_id=lexical_rank_by_id,
        semantic_rank_by_id=semantic_rank_by_id,
        database_path=database_path,
    )
    return RetrievalResponse(query=cleaned, mode=mode, hits=hits)


def _semantic_ranks(
    *,
    query: str,
    embeddings: tuple[np.ndarray, Sequence[str]] | None,
    query_embedder: QueryEmbedder | None,
    per_side_cap: int,
) -> tuple[dict[str, int], RetrievalMode]:
    """Return the semantic per-chunk ranks and the mode, degrading cleanly.

    Yields an empty ranking plus ``LEXICAL_ONLY`` whenever the semantic side
    cannot run — no vectors, no embedder, or the ``search`` extra absent.
    """
    if embeddings is None or query_embedder is None:
        return {}, RetrievalMode.LEXICAL_ONLY
    matrix, chunk_ids = embeddings
    try:
        query_vector = query_embedder.embed_query(query)
    except CorpusSearchDependencyError:
        return {}, RetrievalMode.LEXICAL_ONLY
    ranked_ids = _cosine_ranked_ids(matrix, chunk_ids, query_vector, top_k=per_side_cap)
    return {chunk_id: index for index, chunk_id in enumerate(ranked_ids)}, RetrievalMode.HYBRID


def _cosine_ranked_ids(
    matrix: np.ndarray,
    chunk_ids: Sequence[str],
    query_vector: np.ndarray,
    *,
    top_k: int,
) -> list[str]:
    import numpy as np

    if matrix.shape[0] != len(chunk_ids):
        raise CorpusSearchInputError(
            "embedding matrix and chunk-id list length disagree",
            context={"matrix_rows": int(matrix.shape[0]), "chunk_ids": len(chunk_ids)},
        )
    if matrix.size == 0:
        return []
    normalised = l2_normalise(np.asarray(matrix, dtype=np.float32))
    query_unit = l2_normalise(np.asarray(query_vector, dtype=np.float32).reshape(1, -1))[0]
    similarities = normalised @ query_unit
    order = np.argsort(-similarities)[:top_k]
    return [chunk_ids[int(index)] for index in order]


def _assemble_hits(
    *,
    fused: list[tuple[str, float]],
    lexical_hits: Sequence[LexicalSearchHit],
    lexical_rank_by_id: dict[str, int],
    semantic_rank_by_id: dict[str, int],
    database_path: Path,
) -> tuple[RetrievalHit, ...]:
    lexical_by_id = {hit.chunk_id: hit for hit in lexical_hits}
    needs_lookup = [chunk_id for chunk_id, _score in fused if chunk_id not in lexical_by_id]
    meta = _fetch_chunk_meta(database_path, needs_lookup)
    hits: list[RetrievalHit] = []
    for rank, (chunk_id, score) in enumerate(fused):
        lexical_hit = lexical_by_id.get(chunk_id)
        if lexical_hit is not None:
            corpus_ref, doc_title, text = lexical_hit.corpus_ref, lexical_hit.doc_title, lexical_hit.text
        elif chunk_id in meta:
            corpus_ref, doc_title, text = meta[chunk_id]
        else:
            continue
        hits.append(
            RetrievalHit(
                chunk_id=chunk_id,
                corpus_ref=corpus_ref,
                doc_title=doc_title,
                text=text,
                score=score,
                rank=rank,
                lexical_rank=lexical_rank_by_id.get(chunk_id),
                semantic_rank=semantic_rank_by_id.get(chunk_id),
            )
        )
    return tuple(hits)


def _fetch_chunk_meta(database_path: Path, chunk_ids: Sequence[str]) -> dict[str, tuple[str, str, str]]:
    if not chunk_ids:
        return {}
    connection = sqlite3.connect(database_path)
    try:
        meta: dict[str, tuple[str, str, str]] = {}
        for chunk_id in chunk_ids:
            row = connection.execute(
                "SELECT corpus_ref, doc_title, text FROM chunks WHERE chunk_id = ?",
                (chunk_id,),
            ).fetchone()
            if row is not None:
                meta[chunk_id] = (row[0], row[1], row[2])
        return meta
    finally:
        connection.close()


__all__ = [
    "PER_SIDE_CAP",
    "hybrid_search",
]
