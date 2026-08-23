"""Runtime corpus-search service: provision the index and run grounding search.

External tools and resources consume grounding through one service
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

from ...core import StorageCategory, storage_location
from ...core.config import Settings, load_settings
from ._citation_lookup import bundled_citation_lookup
from ._lexical_index import build_lexical_index, iter_corpus_chunks
from ._models import RetrievalResponse
from ._retrieval import run_retrieval

# Bare filename, read off the taxonomy rather than an untethered string
# literal. Still joined onto ``cadrumo_corpus_search_cache_dir`` exactly as
# before -- the member carries no ``settings_field`` and is not safe to
# resolve directly, because ``CORPUS_SEARCH_CACHE`` is operator-overridable
# (see the member's declaration in ``core._storage_taxonomy``).
_INDEX_FILENAME = Path(storage_location(StorageCategory.CORPUS_SEARCH_INDEX).subpath).name

_DEFAULT_LIMIT = 8


def corpus_search_dir(settings: Settings | None = None) -> Path:
    """Return the app-controlled corpus-search cache directory.

    Read from the settings field rather than joined onto the storage root
    here. A module-local subdirectory literal is invisible to the taxonomy:
    no environment override could reach it, the tree materialiser could not
    pre-create it, and a root override in a test would not redirect it -- so
    this module carried its own ``mkdir`` to compensate for a directory
    nothing else knew about.
    """
    resolved = settings or load_settings()
    return resolved.cadrumo_corpus_search_cache_dir


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
