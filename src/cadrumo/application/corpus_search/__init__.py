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

__all__: tuple[str, ...] = ()
