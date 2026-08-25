"""On-demand lazy-loading locale catalogue with smart dot-notation shard resolution.

Provides :class:`LazyLocaleCatalogue`, an immutable :class:`~collections.abc.Mapping`
that loads only the requested YAML shard files on demand, memoizing parsed values in
memory.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import IO, override

import yaml

from ..external_constants import UTF_8_ENCODING
from ._routing import route_key_to_shard

_LOGGER = logging.getLogger(__name__)


def _load_yaml_handle(handle: IO[str]) -> object:
    """Load YAML content using CSafeLoader if available, falling back to safe_load."""
    if hasattr(yaml, "CSafeLoader"):
        return yaml.load(handle, Loader=yaml.CSafeLoader) or {}
    return yaml.safe_load(handle) or {}


def _flatten_dict(value: object, prefix: str = "") -> dict[str, str | None]:
    """Recursively flatten nested mappings to dot-separated keys."""
    if isinstance(value, Mapping):
        flattened: dict[str, str | None] = {}
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            flattened.update(_flatten_dict(child, child_prefix))
        return flattened
    return {prefix: None if value is None else str(value)}


class LazyLocaleCatalogue(Mapping[str, str | None]):
    """An on-demand, lazy-loading locale catalogue mapping.

    Resolves translation keys on demand by mapping dot-notation keys to specific
    domain/Modelo YAML shards. When a key is requested, only the owning shard file
    is read and parsed into the in-memory cache.
    """

    def __init__(
        self,
        locale: str,
        *,
        shard_dir: Path | None = None,
    ) -> None:
        self.locale = locale
        self.shard_dir = shard_dir
        self._key_cache: dict[str, str | None] = {}
        self._loaded_shards: set[Path] = set()
        self._all_shards_loaded: bool = False

        if self.shard_dir is None or not self.shard_dir.is_dir():
            raise FileNotFoundError(f"Locale catalogue shard directory not found for {locale}: {shard_dir}")

    def _load_shard_file(self, rel_shard: Path) -> None:
        if rel_shard in self._loaded_shards:
            return
        self._loaded_shards.add(rel_shard)
        if self.shard_dir is None:
            return
        shard_file = self.shard_dir / rel_shard
        if not shard_file.is_file():
            return
        try:
            with shard_file.open("r", encoding=UTF_8_ENCODING) as handle:
                parsed = _load_yaml_handle(handle)
            flattened = _flatten_dict(parsed)
            self._key_cache.update(flattened)
        except Exception:
            _LOGGER.warning(
                "Failed to parse locale shard %s for %s",
                shard_file,
                self.locale,
                exc_info=True,
            )

    def _load_all(self) -> None:
        if self._all_shards_loaded:
            return
        self._all_shards_loaded = True
        if self.shard_dir is not None and self.shard_dir.is_dir():
            for yml_file in self.shard_dir.rglob("*.yml"):
                rel_shard = yml_file.relative_to(self.shard_dir)
                self._load_shard_file(rel_shard)

    def _resolve_key(self, key: str) -> None:
        if key in self._key_cache:
            return
        rel_shard = route_key_to_shard(key)
        self._load_shard_file(rel_shard)

    @override
    def __getitem__(self, key: str) -> str | None:
        self._resolve_key(key)
        if key in self._key_cache:
            return self._key_cache[key]
        raise KeyError(key)

    @override
    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):
            return False
        self._resolve_key(key)
        return key in self._key_cache

    @override
    def __iter__(self) -> Iterator[str]:
        self._load_all()
        return iter(self._key_cache)

    @override
    def __len__(self) -> int:
        self._load_all()
        return len(self._key_cache)

    def to_dict(self) -> dict[str, str | None]:
        """Return a complete flattened dictionary of all translation keys."""
        self._load_all()
        return dict(self._key_cache)


__all__ = [
    "LazyLocaleCatalogue",
]
