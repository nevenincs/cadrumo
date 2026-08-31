"""Fingerprint-keyed flat-map cache for one shared locale catalogue.

Persists the flattened ``{dotted.key: value}`` map a packaged locale YAML
file resolves to, so a warm process skips the YAML parse (measured: the
packaged catalogues carry a large ``modelo.schema.*`` block -- casilla labels
and help text, derived and compiled by the registry loader
(:mod:`domain.calculations.registry._modelo_localization`) -- that makes even
the C-accelerated loader cost ~800 ms per process, because PyYAML's C
acceleration covers only scanning/parsing; the higher-level "construct Python
objects from the parsed node tree" step is always pure Python and scales with
node count. A JSON reload of the pre-flattened map costs single-digit tens of
milliseconds).

Mirrors two precedents together, one per risk it addresses:

* :mod:`domain.calculations.registry._verdict_cache`'s KEYING shape: JSON,
  not pickle (the payload is a plain ``dict[str, str | None]``, so there is no
  reason to accept pickle's arbitrary-code-on-load surface for a runtime
  artefact a wheel ships); a source-digest key embedded in the payload. This
  alone catches "the YAML changed" -- any mismatch is a cache MISS, not a
  cache HIT with a wrong answer. Stale and absent collapse to one code path
  by construction: the digest is part of the lookup key, so a cache written
  for an older source can never be mistaken for a match against the current
  one.
* :mod:`domain.calculations.registry._compiled_cache`'s INTEGRITY shape: an
  embedded digest of the payload itself, re-verified on read. The source-key
  match alone cannot catch a payload that is corrupt or truncated UNDER a
  valid key -- a crash, a killed process, or two processes racing to warm the
  same cache could in principle leave a structurally-valid-but-incomplete
  ``flat`` dict that still parses and still carries a matching source digest.
  ``payload_digest`` (a content hash of ``flat`` itself, recomputed on every
  read) closes that gap: a truncated or tampered payload fails this check
  even when the source digest happens to match, and is treated identically
  to a source-digest mismatch -- delete, return ``None``, re-derive.

``atomic_write_best_effort_text`` (used by both precedents and this module)
already writes via a same-directory tempfile followed by :func:`os.replace`,
which is atomic on both POSIX and Windows: a reader always observes either
the complete old file or the complete new one, never a partial write from
THIS process's own write. The payload-digest check is the second, independent
line of defence against a corrupt file arriving by some other path (a
different, non-atomic writer; bit rot; manual tampering).

The source digest is computed over the source file's RAW BYTES, never the
parsed content: cheap (no YAML parse needed to compute it), and immune to a
semantically-equivalent reformat producing a different hash for identical
data.
"""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic import BaseModel

from ...core.models import STRICT_FROZEN_CONFIG
from ..atomic_write import atomic_write_best_effort_text
from ..external_constants import UTF_8_ENCODING
from ..hashing import content_hash_hex
from ..storage_taxonomy import StorageCategory
from ..storage_taxonomy_locations import storage_path

_CACHE_FILENAME_PREFIX = "cadrumo_locale_catalogue_"
_CACHE_SCHEMA_VERSION = "flat-catalogue-v1"

_LOGGER = logging.getLogger(__name__)


class _FlatCatalogueCache(BaseModel):
    """A persisted flattened locale map, keyed by its source file's digest.

    ``source_digest`` binds this payload to the exact source bytes it was
    derived from; the read path recomputes the current source digest and
    only trusts the cache when the two match. ``payload_digest`` binds this
    payload to ITS OWN content, independently of the source: a truncated or
    corrupted ``flat`` dict fails this check even when ``source_digest``
    still matches (see the module docstring's integrity-shape paragraph).
    """

    model_config = STRICT_FROZEN_CONFIG

    schema_version: str
    locale: str
    source_digest: str
    payload_digest: str
    flat: dict[str, str | None]


def _compute_payload_digest(flat: dict[str, str | None]) -> str:
    """Return the content-hash of ``flat`` itself, independent of its source.

    Detects a structurally-valid-but-incomplete or tampered payload that a
    source-digest match alone cannot: the digest changes with any addition,
    removal, or alteration of a key or value.
    """
    return content_hash_hex(flat)


def compute_directory_source_digest(shards: list[tuple[str, bytes]]) -> str:
    """Return the hex SHA-256 digest of a multi-file locale catalogue directory.

    Combines each shard's relative path and raw bytes in sorted order.
    """
    import hashlib

    hasher = hashlib.sha256()
    for rel_path, raw_bytes in sorted(shards, key=lambda x: x[0]):
        hasher.update(rel_path.encode(UTF_8_ENCODING))
        hasher.update(b"\x00")
        hasher.update(raw_bytes)
        hasher.update(b"\x00")
    return hasher.hexdigest()


def catalogue_cache_path(locale: str) -> Path:
    """Return the on-disk flat-map cache file for ``locale``.

    Resolved through :func:`~core.storage_path` for
    ``StorageCategory.LOCALE_CATALOGUE_CACHE`` (``<storage-root>/cache/locale-catalogue``),
    never a shared OS temp dir. One file per locale; the digest embedded
    inside decides whether the file's content is still current.
    """
    return storage_path(StorageCategory.LOCALE_CATALOGUE_CACHE) / f"{_CACHE_FILENAME_PREFIX}{locale}.json"


def read_catalogue_cache(locale: str, *, source_digest: str) -> dict[str, str | None] | None:
    """Return the cached flat map for ``locale`` if it matches ``source_digest``.

    Any absence, read failure, foreign/corrupt shape, schema-version
    mismatch, source-digest mismatch, OR payload-digest mismatch is treated
    identically: the stale or unreadable file is best-effort deleted and
    ``None`` is returned so the caller falls back to parsing the source YAML
    directly. There is no "serve it anyway" branch -- a cache that cannot be
    trusted is exactly as useful as no cache. The payload-digest check runs
    even when the source digest matches, because a matching source digest
    only proves "this cache was derived from the current source at some
    point" -- it says nothing about whether ``flat`` itself survived intact.
    """
    path = catalogue_cache_path(locale)
    if not path.is_file():
        return None
    try:
        raw = path.read_text(encoding=UTF_8_ENCODING)
        cached = _FlatCatalogueCache.model_validate_json(raw)
    except Exception:
        _LOGGER.debug("Ignoring unreadable or foreign locale catalogue cache at %s", path, exc_info=True)
        _delete_catalogue_cache(path)
        return None
    if (
        cached.schema_version != _CACHE_SCHEMA_VERSION
        or cached.locale != locale
        or cached.source_digest != source_digest
    ):
        _LOGGER.debug(
            "Locale catalogue cache at %s is stale (source changed); deleting and re-parsing",
            path,
        )
        _delete_catalogue_cache(path)
        return None
    if cached.payload_digest != _compute_payload_digest(cached.flat):
        _LOGGER.debug(
            "Locale catalogue cache at %s failed its payload-integrity check "
            "(truncated or corrupted despite a matching source digest); deleting and re-parsing",
            path,
        )
        _delete_catalogue_cache(path)
        return None
    return cached.flat


def write_catalogue_cache(locale: str, *, source_digest: str, flat: dict[str, str | None]) -> None:
    """Persist ``flat`` for ``locale`` under ``source_digest``, best-effort."""
    path = catalogue_cache_path(locale)
    payload = _FlatCatalogueCache(
        schema_version=_CACHE_SCHEMA_VERSION,
        locale=locale,
        source_digest=source_digest,
        payload_digest=_compute_payload_digest(flat),
        flat=flat,
    )
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_best_effort_text(path, payload.model_dump_json(), encoding=UTF_8_ENCODING)
    except Exception:
        _LOGGER.warning("Could not write locale catalogue cache at %s", path, exc_info=True)


def _delete_catalogue_cache(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        _LOGGER.debug("Could not delete locale catalogue cache at %s", path, exc_info=True)


__all__ = [
    "catalogue_cache_path",
    "compute_directory_source_digest",
    "read_catalogue_cache",
    "write_catalogue_cache",
]
