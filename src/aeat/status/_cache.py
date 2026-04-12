"""Short-lived file cache for AEAT status records.

The cache is advisory: every consumer can bypass it, and every read
revalidates the stored JSON through the target pydantic model, so a
stale-schema payload degrades to a miss rather than a silent
corruption.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from aeat.logging import get_logger

from ._models import AeatStatusKind

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


def _atomic_write_text(path: Path, text: str) -> bool:
    """Write ``text`` to ``path`` atomically via a sibling temp file.

    Uses :class:`tempfile.NamedTemporaryFile` in the same directory
    so ``os.replace`` stays cross-filesystem-safe (it isn't: the
    source and destination have to live on the same mount). On
    Windows, ``os.replace`` can raise ``PermissionError`` if a
    reader holds the destination open at the exact instant of the
    rename; we catch that case, log it, clean up the temp file, and
    return ``False`` so the caller knows the write did not land.

    Returns:
        ``True`` if the write succeeded, ``False`` on a graceful
        Windows ``PermissionError`` race.
    """
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=path.name + ".",
        suffix=".tmp",
        delete=False,
    ) as fh:
        fh.write(text)
        tmp_path = Path(fh.name)
    try:
        os.replace(tmp_path, path)
    except PermissionError:
        logger.warning(
            "atomic cache write lost the race on %s; falling back to fetched-but-not-cached",
            path,
        )
        with contextlib.suppress(OSError):  # pragma: no cover - defensive
            tmp_path.unlink(missing_ok=True)
        return False
    return True


class _CacheMeta(BaseModel):
    """Sidecar metadata stored next to every cached payload."""

    cached_at: float
    ttl_s: int


class StatusCache:
    """File-backed cache for status records, keyed by ``(surface, key)``.

    Payloads are stored as JSON under
    ``<cache_dir>/<surface>/<key>.json`` with a sibling
    ``<key>.meta.json`` carrying ``cached_at`` / ``ttl_s``. A miss
    is returned for any of:

    - missing payload file,
    - missing metadata file,
    - expired metadata (``now - cached_at > ttl_s``),
    - payload that no longer revalidates through the target model.
    """

    def __init__(self, cache_dir: Path, ttl_s: int) -> None:
        """Initialise the cache.

        Args:
            cache_dir: Root directory for cached payloads. Created
                lazily on first write.
            ttl_s: Time-to-live in seconds for every entry.
        """
        self._cache_dir = cache_dir
        self._ttl_s = ttl_s

    @property
    def ttl_s(self) -> int:
        """Configured TTL in seconds."""
        return self._ttl_s

    def _paths(self, surface: AeatStatusKind, key: str) -> tuple[Path, Path]:
        surface_dir = self._cache_dir / surface.value
        return surface_dir / f"{key}.json", surface_dir / f"{key}.meta.json"

    def get_tuple(
        self,
        *,
        surface: AeatStatusKind,
        key: str,
        model: type[T],
    ) -> tuple[T, ...] | None:
        """Fetch and revalidate a cached ``tuple[T, ...]`` payload.

        Args:
            surface: The status surface (namespaces the key).
            key: The :func:`make_cache_key` hex key.
            model: The pydantic model class every tuple element must
                revalidate against.

        Returns:
            A tuple of validated records, or ``None`` on miss.
        """
        payload_path, meta_path = self._paths(surface, key)
        if not payload_path.is_file() or not meta_path.is_file():
            return None
        try:
            meta = _CacheMeta.model_validate_json(meta_path.read_text(encoding="utf-8"))
        except ValidationError:
            logger.debug("cache meta invalid for %s/%s - miss", surface.value, key)
            return None
        if time.time() - meta.cached_at >= meta.ttl_s:
            logger.debug("cache expired for %s/%s - miss", surface.value, key)
            return None
        try:
            raw = json.loads(payload_path.read_text(encoding="utf-8"))
            if not isinstance(raw, list):
                logger.debug("cache payload not a list for %s/%s - miss", surface.value, key)
                return None
            # Read back through the JSON validator: ``strict=True``
            # rejects string-coerced datetimes via ``model_validate``,
            # but ``model_validate_json`` honours the JSON coercion
            # rules and round-trips ``model_dump(mode="json")``
            # cleanly.
            return tuple(model.model_validate_json(json.dumps(item)) for item in raw)
        except (ValidationError, json.JSONDecodeError):
            logger.debug("cache payload schema-mismatch for %s/%s - miss", surface.value, key)
            return None

    def put_tuple(
        self,
        *,
        surface: AeatStatusKind,
        key: str,
        records: tuple[BaseModel, ...],
    ) -> None:
        """Store a tuple of records under ``(surface, key)``.

        Args:
            surface: The status surface.
            key: The :func:`make_cache_key` hex key.
            records: The records to serialise.
        """
        payload_path, meta_path = self._paths(surface, key)
        payload_path.parent.mkdir(parents=True, exist_ok=True)
        payload_json = json.dumps([record.model_dump(mode="json") for record in records])
        meta = _CacheMeta(cached_at=time.time(), ttl_s=self._ttl_s)
        # Atomic write: stage to a sibling temp file and os.replace
        # into position so a crash or concurrent writer can never
        # leave a half-written payload visible to readers. Failures
        # are non-fatal: the caller gets the freshly-fetched records
        # regardless, we just don't cache them.
        if not _atomic_write_text(payload_path, payload_json):
            return
        _atomic_write_text(meta_path, meta.model_dump_json())
