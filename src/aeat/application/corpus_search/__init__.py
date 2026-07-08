"""On-host hybrid corpus-search grounding surface.

The console's R3 grounding surface: a licence-clean, on-host retrieval
stack over the bundled BOE/AEAT corpus, built from the already-shipped
``*.extracted`` triples. Three cooperating pieces live here:

* the FTS5 lexical index
  (:mod:`~application.corpus_search._lexical_index`) — standard-library
  SQLite plus a Spanish Snowball stemmed column, always importable;
* the structured citation lookup
  (:mod:`~application.corpus_search._citation_lookup`) — an exact
  ``legal_refs`` id resolver over the registry legal catalogue that
  returns verbatim authoritative text;
* the build-time embedding precompute
  (:mod:`~application.corpus_search._embed_build`) — the semantic half,
  gated behind the ``aeat-cli[search]`` extra, that ships its corpus vectors
  as plain data.

The lexical index and the citation lookup carry the degraded, no-download
mode: they refuse nothing for want of a model. Only the embedding
precompute and the runtime query embedder need the ``search`` extra, and
they refuse with an install hint when it is absent.
"""

from __future__ import annotations

from ._citation_lookup import CitationLookup, bundled_citation_lookup
from ._embed_build import (
    POTION_MODEL_ID,
    POTION_MODEL_REVISION,
    embed_corpus,
    load_embeddings,
    more_like_this,
)
from ._errors import (
    CorpusSearchDependencyError,
    CorpusSearchError,
    CorpusSearchInputError,
)
from ._lexical_index import (
    build_lexical_index,
    bundled_corpus_html_root,
    iter_corpus_chunks,
    search_lexical,
)
from ._models import (
    CitationResolution,
    CorpusChunk,
    CorpusDocument,
    CorpusEmbeddingBuildResult,
    CorpusIndexBuildResult,
    LexicalSearchHit,
    RetrievalHit,
    RetrievalMode,
    RetrievalResponse,
    SimilarChunk,
)
from ._query_embed import QueryEmbedder, search_extra_available, search_model_cache_dir
from ._retrieval import PER_SIDE_CAP, RRF_K, hybrid_search
from ._runtime import (
    corpus_index_path,
    corpus_search_dir,
    ensure_corpus_embeddings,
    ensure_corpus_index,
    load_corpus_embeddings,
    search_corpus,
)
from ._terminology import (
    TerminologyConcept,
    TerminologyHit,
    load_terminology_concepts,
    lookup_terminology,
    search_terminology,
)

__all__ = [
    "PER_SIDE_CAP",
    "POTION_MODEL_ID",
    "POTION_MODEL_REVISION",
    "RRF_K",
    "CitationLookup",
    "CitationResolution",
    "CorpusChunk",
    "CorpusDocument",
    "CorpusEmbeddingBuildResult",
    "CorpusIndexBuildResult",
    "CorpusSearchDependencyError",
    "CorpusSearchError",
    "CorpusSearchInputError",
    "LexicalSearchHit",
    "QueryEmbedder",
    "RetrievalHit",
    "RetrievalMode",
    "RetrievalResponse",
    "SimilarChunk",
    "TerminologyConcept",
    "TerminologyHit",
    "build_lexical_index",
    "bundled_citation_lookup",
    "bundled_corpus_html_root",
    "corpus_index_path",
    "corpus_search_dir",
    "embed_corpus",
    "ensure_corpus_embeddings",
    "ensure_corpus_index",
    "hybrid_search",
    "iter_corpus_chunks",
    "load_corpus_embeddings",
    "load_embeddings",
    "load_terminology_concepts",
    "lookup_terminology",
    "more_like_this",
    "search_corpus",
    "search_extra_available",
    "search_lexical",
    "search_model_cache_dir",
    "search_terminology",
]
