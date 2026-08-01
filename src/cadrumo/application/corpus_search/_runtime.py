"""Runtime corpus-search service: provision the index and run grounding search.

The MCP console tools and resources consume grounding through one service
entry, :func:`search_corpus`, so the protocol layer never re-derives the
retrieval wiring. On first use the lexical index is built once from the
bundled corpus into an app-controlled cache under the Settings storage root
and reused thereafter (the corpus is static, so a present index is current).

Retrieval is fully offline: the FTS5 lexical ranking and the exact-citation
lookup need no model, no vectors, and no network. The service has no degraded
mode because it has no optional half to degrade from.

See Also:
    :func:`~application.corpus_search.run_retrieval`
        Retrieval primitive this runtime service provisions and calls.
"""

from __future__ import annotations

from pathlib import Path

from ...core.config import Settings, load_settings
from ._citation_lookup import bundled_citation_lookup
from ._lexical_index import build_lexical_index, iter_corpus_chunks
from ._models import RetrievalResponse
from ._retrieval import run_retrieval

_INDEX_SUBDIR = "corpus-search"
_INDEX_FILENAME = "corpus.sqlite"

_DEFAULT_LIMIT = 8


def corpus_search_dir(settings: Settings | None = None) -> Path:
    """Return the app-controlled corpus-search cache directory."""
    resolved = settings or load_settings()
    return resolved.cadrumo_local_storage_root / _INDEX_SUBDIR


def corpus_index_path(settings: Settings | None = None) -> Path:
    """Return the lexical index path (whether or not it has been built)."""
    return corpus_search_dir(settings) / _INDEX_FILENAME


def ensure_corpus_index(settings: Settings | None = None) -> Path:
    """Return the lexical index path, building it from the bundled corpus if absent.

    The first build stems the whole bundled corpus and is the one slow call
    (seconds to tens of seconds); every later call finds the cached index and
    returns immediately. A present index is current because the bundled corpus
    is static.
    """
    database_path = corpus_index_path(settings)
    if not database_path.exists():
        database_path.parent.mkdir(parents=True, exist_ok=True)
        build_lexical_index(database_path, iter_corpus_chunks())
    return database_path


def search_corpus(
    query: str,
    *,
    limit: int = _DEFAULT_LIMIT,
    settings: Settings | None = None,
) -> RetrievalResponse:
    """Run grounding retrieval for ``query`` over the bundled corpus.

    Provisions the lexical index (build-once cache) and runs the exact-citation
    short-circuit over the ranked FTS5 lexical search.

    Args:
        query: The free-text query or an exact citation id.
        limit: Maximum number of hits.
        settings: Optional settings override (test isolation).

    Returns:
        A :class:`RetrievalResponse`.
    """
    return run_retrieval(
        query,
        database_path=ensure_corpus_index(settings),
        citation_lookup=bundled_citation_lookup(),
        limit=limit,
    )


__all__ = [
    "corpus_index_path",
    "corpus_search_dir",
    "ensure_corpus_index",
    "search_corpus",
]
