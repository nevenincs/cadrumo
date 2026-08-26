"""Corpus retrieval: exact citation short-circuit over an FTS5 lexical ranking.

The grounding search runs two cooperating retrievers, neither of which needs a
model:

* an exact-citation short-circuit — when the query IS a citation id
  (``ley-58-2003:art-27.2``), it resolves directly through the structured
  lookup, no ranking needed;
* the FTS5 lexical index
  (:mod:`~application.corpus_search._lexical_index`) for exact and stemmed
  in-prose recall, ranked by BM25 over the diacritic-folded and Spanish-stemmed
  columns.

The shipped product carries no semantic runtime: nothing here loads an
embedding model, computes or consumes vectors, or reaches the network. Semantic
recall re-enters the product, if ever, only as laundered precompiled data
produced by the dev-side oracle.
"""

from __future__ import annotations

from pathlib import Path

from ._citation_lookup import CitationLookup
from ._lexical_index import search_lexical
from ._models import RetrievalHit, RetrievalMode, RetrievalResponse
from .errors import CorpusSearchInputError


def run_retrieval(
    query: str,
    *,
    database_path: Path,
    citation_lookup: CitationLookup | None = None,
    limit: int = 10,
) -> RetrievalResponse:
    """Run grounding retrieval for ``query`` and return a typed response.

    Args:
        query: The free-text query, or an exact citation id.
        database_path: A lexical index built by ``build_lexical_index``.
        citation_lookup: Optional catalogue lookup enabling the exact-citation
            short-circuit.
        limit: Maximum number of ranked hits to return.

    Returns:
        A :class:`RetrievalResponse` — a citation resolution, or the ranked
        lexical hits.

    Raises:
        CorpusSearchInputError: If ``query`` is blank or ``limit`` is not
            positive.
    """
    cleaned = query.strip()
    if not cleaned:
        raise CorpusSearchInputError(reason="query_empty", context={"query": query})
    if limit <= 0:
        raise CorpusSearchInputError(reason="limit_not_positive", context={"limit": limit})

    if citation_lookup is not None and cleaned in set(citation_lookup.citation_ids):
        return RetrievalResponse(
            query=cleaned,
            mode=RetrievalMode.CITATION,
            citation=citation_lookup.resolve(cleaned),
        )

    hits = tuple(
        RetrievalHit(
            chunk_id=hit.chunk_id,
            corpus_ref=hit.corpus_ref,
            doc_title=hit.doc_title,
            text=hit.text,
            score=hit.score,
            rank=rank,
            lexical_rank=rank,
        )
        for rank, hit in enumerate(search_lexical(database_path, cleaned, limit=limit))
    )
    return RetrievalResponse(query=cleaned, mode=RetrievalMode.LEXICAL_ONLY, hits=hits)


__all__ = [
    "run_retrieval",
]
