"""Runtime corpus-search service: provision the index and run hybrid search.

The MCP console tools and resources consume grounding through one service
entry, :func:`search_corpus`, so the protocol layer never re-derives the
retrieval wiring. On first use the lexical index is built once from the
bundled corpus into an app-controlled cache under the Settings storage root
and reused thereafter (the corpus is static, so a present index is current).

Precomputed corpus vectors are loaded when they have been shipped/materialised
into the same cache directory; absent them (or the ``search`` extra) the
service runs in lexical-only + citation mode, the shippable degraded default.

See Also:
    :func:`~application.corpus_search.hybrid_search`
        Retrieval primitive this runtime service provisions and calls.
    :func:`~application.corpus_search.ensure_corpus_embeddings`
        Build-once semantic-vector cache behind the ``aeat-cli[search]`` extra.
    :class:`~application.corpus_search.QueryEmbedder`
        Live-query embedder used only when semantic vectors are available.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

from ...core.config import Settings, load_settings
from ._citation_lookup import bundled_citation_lookup
from ._embed_build import embed_corpus, load_embeddings
from ._lexical_index import build_lexical_index, iter_corpus_chunks
from ._models import CorpusChunk, RetrievalResponse
from ._query_embed import QueryEmbedder, search_extra_available, search_model_cache_dir
from ._retrieval import hybrid_search

if TYPE_CHECKING:
    import numpy as np

_INDEX_SUBDIR = "corpus-search"
_INDEX_FILENAME = "corpus.sqlite"
_VECTORS_FILENAME = "corpus-vectors.npy"
_VECTOR_IDS_FILENAME = "corpus-chunk-ids.json"

_DEFAULT_LIMIT = 8


def corpus_search_dir(settings: Settings | None = None) -> Path:
    """Return the app-controlled corpus-search cache directory."""
    resolved = settings or load_settings()
    return resolved.aeat_local_storage_root / _INDEX_SUBDIR


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


def load_corpus_embeddings(settings: Settings | None = None) -> tuple[np.ndarray, tuple[str, ...]] | None:
    """Load precomputed corpus vectors from the cache, or ``None`` if not present."""
    directory = corpus_search_dir(settings)
    matrix_path = directory / _VECTORS_FILENAME
    ids_path = directory / _VECTOR_IDS_FILENAME
    if not matrix_path.exists() or not ids_path.exists():
        return None
    return load_embeddings(matrix_path, ids_path)


def ensure_corpus_embeddings(
    settings: Settings | None = None,
    *,
    semantic_available: bool | None = None,
    corpus_chunks: Iterable[CorpusChunk] | None = None,
) -> tuple[np.ndarray, tuple[str, ...]] | None:
    """Return the corpus vectors, building them once behind the ``search`` extra.

    This is the runtime build step for the semantic half (the decision recorded
    for the S79/S87 question): corpus vectors are BUILT behind the ``aeat-cli[search]``
    extra on first use, never shipped in the wheel (``shipped-search-licence-clean``
    keeps the wheel free of the ~0.5 GB model weights and the derived matrix). It
    mirrors :func:`ensure_corpus_index`: the first call is the one slow build (it
    downloads/loads the potion model and encodes every bundled chunk into an
    app-controlled cache); every later call finds the cached matrix and returns
    immediately, and a present matrix is current because the bundled corpus is
    static.

    Returns ``None`` — the shippable lexical-only default — whenever the extra is
    absent, so a bare-core install never triggers a model download.
    """
    if semantic_available is None:
        semantic_available = search_extra_available()
    if not semantic_available:
        return None
    directory = corpus_search_dir(settings)
    matrix_path = directory / _VECTORS_FILENAME
    ids_path = directory / _VECTOR_IDS_FILENAME
    if not matrix_path.exists() or not ids_path.exists():
        directory.mkdir(parents=True, exist_ok=True)
        embed_corpus(
            corpus_chunks if corpus_chunks is not None else iter_corpus_chunks(),
            matrix_path=matrix_path,
            chunk_ids_path=ids_path,
            cache_dir=search_model_cache_dir(settings),
        )
    return load_embeddings(matrix_path, ids_path)


def search_corpus(query: str, *, limit: int = _DEFAULT_LIMIT, settings: Settings | None = None) -> RetrievalResponse:
    """Run grounding retrieval for ``query`` over the bundled corpus.

    Provisions the lexical index (build-once cache), loads precomputed vectors
    when present, and fuses lexical, semantic, and exact-citation retrieval —
    degrading to lexical-only when the semantic stack is unavailable.

    Args:
        query: The free-text query or an exact citation id.
        limit: Maximum number of hits.
        settings: Optional settings override (test isolation).

    Returns:
        A :class:`RetrievalResponse`.
    """
    database_path = ensure_corpus_index(settings)
    embeddings = ensure_corpus_embeddings(settings)
    embedder = QueryEmbedder(settings=settings) if embeddings is not None and search_extra_available() else None
    return hybrid_search(
        query,
        database_path=database_path,
        embeddings=embeddings,
        query_embedder=embedder,
        citation_lookup=bundled_citation_lookup(),
        limit=limit,
    )


__all__ = [
    "corpus_index_path",
    "corpus_search_dir",
    "ensure_corpus_embeddings",
    "ensure_corpus_index",
    "load_corpus_embeddings",
    "search_corpus",
]
