"""On-host corpus-search grounding surface.

The console's fully offline retrieval stack has two cooperating paths:

* the FTS5 lexical index
  (:mod:`~application.corpus_search.lexical_index`) — concept recall over
  top-level ``normatives/html/*.html.extracted.json`` payloads, including
  content-aware extractions of XML responses;
* the structured citation lookup
  (:mod:`~application.corpus_search.citation_lookup`) — exact ``legal_refs``
  resolution through the signed registry authority.

The lexical index is intentionally narrower than the development RAG index,
which also enrolls corpus PDFs, workbooks, and terminology sources. Neither
runtime path needs a model, vectors, or the network.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
