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

Mirrors :mod:`domain.calculations.registry._validate_verdict`'s shape: JSON,
not pickle (the payload is a plain ``dict[str, str | None]``, so there is no
reason to accept pickle's arbitrary-code-on-load surface for a runtime
artefact a wheel ships); a source-digest key embedded in the payload; any
mismatch, corruption, or foreign shape is a cache MISS, not a cache HIT with a
wrong answer -- ``read_catalogue_cache`` deletes the stale file and returns
``None`` so the caller re-parses YAML and rewarms. Stale and absent are the
same code path by construction: the digest is part of the lookup key, so a
cache written for an older source can never be mistaken for a match against
the current one.

The digest is computed over the source file's RAW BYTES, never the parsed
content: cheap (no YAML parse needed to compute it), and immune to a
semantically-equivalent reformat producing a different hash for identical
data.
"""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from ..atomic_write import atomic_write_best_effort_text
from ..external_constants import UTF_8_ENCODING
from ..hashing import sha256_hex
from .._storage_taxonomy import StorageCategory
from .._storage_taxonomy_locations import storage_path

_CACHE_FILENAME_PREFIX = "cadrumo_locale_catalogue_"
_CACHE_SCHEMA_VERSION = "flat-catalogue-v1"

_LOGGER = logging.getLogger(__name__)


class _FlatCatalogueCache(BaseModel):
    """A persisted flattened locale map, keyed by its source file's digest.

    ``source_digest`` binds this payload to the exact source bytes it was
    derived from; the read path recomputes the current source digest and
    only trusts the cache when the two match.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str
    locale: str
    source_digest: str
    flat: dict[str, str | None]


def compute_source_digest(raw_source: bytes) -> str:
    """Return the hex SHA-256 digest of a locale catalogue's raw source bytes.

    Hashing the raw bytes (not the parsed YAML) is cheap -- no parse is
    needed to compute it -- and cannot be fooled by a semantically-equivalent
    reformat of the same data producing a different hash.
    """
    return sha256_hex(raw_source)


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
    mismatch, or digest mismatch is treated identically: the stale or
    unreadable file is best-effort deleted and ``None`` is returned so the
    caller falls back to parsing the source YAML directly. There is no
    "serve it anyway" branch -- a cache that cannot be trusted is exactly as
    useful as no cache.
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
    return cached.flat


def write_catalogue_cache(locale: str, *, source_digest: str, flat: dict[str, str | None]) -> None:
    """Persist ``flat`` for ``locale`` under ``source_digest``, best-effort."""
    path = catalogue_cache_path(locale)
    payload = _FlatCatalogueCache(
        schema_version=_CACHE_SCHEMA_VERSION,
        locale=locale,
        source_digest=source_digest,
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
    "compute_source_digest",
    "read_catalogue_cache",
    "write_catalogue_cache",
]
