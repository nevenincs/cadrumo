"""Runtime corpus-search service: provision the index and run grounding search.

External tools and resources consume grounding through one service
entry, :func:`search_corpus`, so the protocol layer never re-derives the
retrieval wiring. The lexical index covers top-level
``normatives/html/*.html.extracted.json`` payloads. It is provisioned in an
app-controlled cache and rebuilt atomically whenever the indexed bytes or
schema identity changes.

Retrieval is fully offline: the FTS5 lexical ranking and the exact-citation
lookup need no model, no vectors, and no network. The service has no degraded
mode because it has no optional half to degrade from.

See Also:
    :func:`~application.corpus_search.run_retrieval`
        Retrieval primitive this runtime service provisions and calls.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import tempfile
from pathlib import Path

from ...core.config import Settings, load_settings
from ...core.directory_scan import scan_directory
from ...core.locks import exclusive_file_lock
from ...core.storage_taxonomy import StorageCategory
from ...core.storage_taxonomy_locations import storage_location
from ._retrieval import run_retrieval
from .citation_lookup import bundled_citation_lookup
from .lexical_index import build_lexical_index, bundled_corpus_html_root, iter_corpus_chunks
from .models import RetrievalResponse

# Bare filename, read off the taxonomy rather than an untethered string
# literal. Still joined onto ``cadrumo_corpus_search_cache_dir`` exactly as
# before -- the member carries no ``settings_field`` and is not safe to
# resolve directly, because ``CORPUS_SEARCH_CACHE`` is operator-overridable
# (see the member's declaration in ``core.storage_taxonomy``).
_INDEX_FILENAME = Path(storage_location(StorageCategory.CORPUS_SEARCH_INDEX).subpath).name

_DEFAULT_LIMIT = 8

# These tokens deliberately participate in the cache identity. Bump the index
# token when the SQLite/search representation changes and the extractor token
# when identical extracted bytes acquire different parsing semantics.
_INDEX_SCHEMA_VERSION = "corpus-fts5-v1"
_EXTRACTOR_SCHEMA_VERSION = "extracted-json-v1"
_EXTRACTED_JSON_PATTERN = "*.html.extracted.json"
_METADATA_KEY = "corpus_identity"


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
    """Return the current lexical index, rebuilding stale caches atomically.

    Currency is determined from the sorted relative paths and exact bytes of
    every indexed source plus explicit index and extractor schema versions.
    Builds are staged beside the destination and published with one atomic
    replace, so an interrupted build is never mistaken for a current index.
    """
    database_path = corpus_index_path(settings)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    corpus_root = bundled_corpus_html_root()
    with exclusive_file_lock(database_path):
        source_identity = _corpus_identity(corpus_root)
        if _stored_identity(database_path) == source_identity:
            return database_path
        staging_path = _staging_database_path(database_path)
        try:
            build_lexical_index(staging_path, iter_corpus_chunks(corpus_root))
            if _corpus_identity(corpus_root) != source_identity:
                raise RuntimeError("corpus sources changed while the lexical index was being built")
            _store_identity(staging_path, source_identity)
            os.replace(staging_path, database_path)
        finally:
            staging_path.unlink(missing_ok=True)
    return database_path


def _corpus_identity(corpus_root: Path) -> str:
    digest = hashlib.sha256()
    for token in (_INDEX_SCHEMA_VERSION, _EXTRACTOR_SCHEMA_VERSION):
        encoded = token.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    for source_path in scan_directory(corpus_root, pattern=_EXTRACTED_JSON_PATTERN):
        relative = source_path.relative_to(corpus_root).as_posix().encode("utf-8")
        payload = source_path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def _stored_identity(database_path: Path) -> str | None:
    if not database_path.is_file():
        return None
    try:
        connection = sqlite3.connect(f"file:{database_path.as_posix()}?mode=ro", uri=True)
        try:
            row = connection.execute(
                "SELECT value FROM corpus_index_metadata WHERE key = ?",
                (_METADATA_KEY,),
            ).fetchone()
        finally:
            connection.close()
    except sqlite3.Error:
        return None
    return str(row[0]) if row is not None else None


def _store_identity(database_path: Path, identity: str) -> None:
    connection = sqlite3.connect(database_path)
    try:
        connection.execute("CREATE TABLE corpus_index_metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute(
            "INSERT INTO corpus_index_metadata(key, value) VALUES(?, ?)",
            (_METADATA_KEY, identity),
        )
        connection.commit()
    finally:
        connection.close()


def _staging_database_path(database_path: Path) -> Path:
    descriptor, raw_path = tempfile.mkstemp(
        prefix=f".{database_path.name}.",
        suffix=".tmp",
        dir=database_path.parent,
    )
    os.close(descriptor)
    return Path(raw_path)


def search_corpus(
    query: str,
    *,
    limit: int = _DEFAULT_LIMIT,
    settings: Settings | None = None,
) -> RetrievalResponse:
    """Run grounding retrieval for ``query``.

    Provisions the content-keyed normative-HTML lexical index and runs the
    separate signed-authority citation lookup before ranked FTS5 search.

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
