"""On-host lexical corpus-search grounding surface.

The console's grounding surface: a licence-clean, fully offline retrieval
stack over the bundled BOE/AEAT corpus, built from the already-shipped
``*.extracted`` triples. Two cooperating pieces live here:

* the FTS5 lexical index
  (:mod:`~application.corpus_search._lexical_index`) — standard-library
  SQLite plus a Spanish Snowball stemmed column;
* the structured citation lookup
  (:mod:`~application.corpus_search._citation_lookup`) — an exact
  ``legal_refs`` id resolver over the registry legal catalogue that
  returns verbatim authoritative text.

Neither needs a model, vectors, or the network, so the surface has one shape
on every install: it refuses nothing for want of a download. Semantic search
is a dev-side precompile step whose laundered output ships with the
documentation, never a runtime the product carries.
"""

from __future__ import annotations

from ._citation_lookup import CitationLookup, bundled_citation_lookup
from .errors import (
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
    CorpusIndexBuildResult,
    LexicalSearchHit,
    RetrievalHit,
    RetrievalMode,
    RetrievalResponse,
)
from ._retrieval import run_retrieval
from ._runtime import (
    corpus_index_path,
    corpus_search_dir,
    ensure_corpus_index,
    search_corpus,
)
from ._terminology import (
    CONCEPT_ID_MAX_LENGTH,
    CONCEPT_ID_MIN_LENGTH,
    CONCEPT_ID_PATTERN,
    TerminologyConcept,
    TerminologyHit,
    load_terminology_concepts,
    lookup_terminology,
    search_terminology,
)

__all__ = [
    "CONCEPT_ID_MAX_LENGTH",
    "CONCEPT_ID_MIN_LENGTH",
    "CONCEPT_ID_PATTERN",
    "CitationLookup",
    "CitationResolution",
    "CorpusChunk",
    "CorpusDocument",
    "CorpusIndexBuildResult",
    "CorpusSearchError",
    "CorpusSearchInputError",
    "LexicalSearchHit",
    "RetrievalHit",
    "RetrievalMode",
    "RetrievalResponse",
    "TerminologyConcept",
    "TerminologyHit",
    "build_lexical_index",
    "bundled_citation_lookup",
    "bundled_corpus_html_root",
    "corpus_index_path",
    "corpus_search_dir",
    "ensure_corpus_index",
    "iter_corpus_chunks",
    "load_terminology_concepts",
    "lookup_terminology",
    "run_retrieval",
    "search_corpus",
    "search_lexical",
    "search_terminology",
]
