"""On-demand lazy-loading locale catalogue with smart dot-notation shard resolution.

Provides :class:`LazyLocaleCatalogue`, an immutable :class:`~collections.abc.Mapping`
that loads only the requested YAML shard files on demand, memoizing parsed values in
memory.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import IO, override

import yaml

from ..external_constants import UTF_8_ENCODING
from ..type_guards import is_object_mapping
from .routing import route_key_to_shard

_LOGGER = logging.getLogger(__name__)

if not yaml.__with_libyaml__:
    # The pure-Python scanner is roughly ten times slower on these catalogues;
    # falling back to it silently would turn every rendered message into a
    # multi-second stall with no signal pointing at the cause.
    raise ImportError(
        "PyYAML is installed without libyaml support; Cadrumo requires a PyYAML build "
        "that provides yaml.CSafeLoader. Reinstall PyYAML from a platform wheel."
    )


def _load_yaml_handle(handle: IO[str]) -> object:
    """Load YAML content with libyaml's safe loader."""
    return yaml.load(handle, Loader=yaml.CSafeLoader) or {}


def _child_path(prefix: str, key: object) -> str:
    return f"{prefix}.{key}" if prefix else str(key)


def _flat_value(value: object) -> str | None:
    return None if value is None else str(value)


def _flatten_dict(value: object, prefix: str = "") -> dict[str, str | None]:
    """Recursively flatten nested mappings to dot-separated keys."""
    if is_object_mapping(value):
        flattened: dict[str, str | None] = {}
        for key, child in value.items():
            flattened.update(_flatten_dict(child, _child_path(prefix, key)))
        return flattened
    return {prefix: _flat_value(value)}


class _UnscannableShardError(Exception):
    """The event scan met a construct only a full load interprets faithfully."""


_SCAN_RESOLVER = yaml.resolver.Resolver()


def _scalar_value(event: yaml.ScalarEvent) -> object:
    """Construct one scalar exactly as the safe loader's composer and constructor do."""
    tag = event.tag
    if tag is None or tag == "!":
        tag = _SCAN_RESOLVER.resolve(yaml.ScalarNode, event.value, event.implicit)
    if tag == "tag:yaml.org,2002:merge":
        raise _UnscannableShardError
    node = yaml.ScalarNode(tag, event.value, style=event.style)
    # A fresh constructor per scalar: ``construct_document`` resets its memo, and
    # nothing is shared between threads resolving keys at once.
    return yaml.constructor.SafeConstructor().construct_document(node)


@dataclass(slots=True)
class _MappingFrame:
    path: str
    pending_path: str | None = None


def _scan_shard_for_key(handle: IO[str], key: str) -> str | None:
    """Return one flattened scalar value by streaming the shard up to its key.

    A listing asks one key of a large shard, and a full load constructs every
    entry to answer it. Catalogue authoring refuses duplicate keys, so the first
    match is the value a full load keeps. Anything a full load would read
    differently -- an anchor or alias, a merge key, a complex key, a collection
    at the key itself, a second document -- raises :class:`_UnscannableShardError`, as
    does a key the shard lacks.
    """
    mappings: list[_MappingFrame] = []
    # A sequence flattens to one stringified value, so nothing under it is a key.
    opaque_depth = 0
    documents = 0
    for event in yaml.parse(handle, Loader=yaml.CSafeLoader):
        if isinstance(event, yaml.AliasEvent) or getattr(event, "anchor", None) is not None:
            raise _UnscannableShardError
        if isinstance(event, yaml.DocumentStartEvent):
            documents += 1
            if documents > 1:
                raise _UnscannableShardError
            continue
        if opaque_depth:
            if isinstance(event, yaml.CollectionStartEvent):
                opaque_depth += 1
            elif isinstance(event, yaml.CollectionEndEvent):
                opaque_depth -= 1
                if not opaque_depth:
                    _close_value(mappings)
            continue
        frame = mappings[-1] if mappings else None
        if frame is not None and frame.pending_path is None:
            if not isinstance(event, yaml.ScalarEvent | yaml.MappingEndEvent):
                raise _UnscannableShardError
            if isinstance(event, yaml.ScalarEvent):
                frame.pending_path = _child_path(frame.path, _scalar_value(event))
                continue
        if isinstance(event, yaml.MappingEndEvent):
            mappings.pop()
            _close_value(mappings)
        elif isinstance(event, yaml.ScalarEvent):
            if frame is not None and frame.pending_path == key:
                return _flat_value(_scalar_value(event))
            _close_value(mappings)
        elif isinstance(event, yaml.CollectionStartEvent):
            if frame is not None and frame.pending_path == key:
                raise _UnscannableShardError
            if isinstance(event, yaml.SequenceStartEvent):
                opaque_depth = 1
            else:
                mappings.append(_MappingFrame(path="" if frame is None else (frame.pending_path or "")))
    raise _UnscannableShardError


def _close_value(mappings: list[_MappingFrame]) -> None:
    if mappings:
        mappings[-1].pending_path = None


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
        self._scanned_shards: set[Path] = set()
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

    def _scan_shard_file(self, rel_shard: Path, key: str) -> bool:
        # Streaming pays off for a shard asked one key; a shard asked a second
        # uncached key is being read broadly, and one full load serves the rest.
        if rel_shard in self._scanned_shards or rel_shard in self._loaded_shards:
            return False
        self._scanned_shards.add(rel_shard)
        if self.shard_dir is None:
            return False
        shard_file = self.shard_dir / rel_shard
        if not shard_file.is_file():
            return False
        try:
            with shard_file.open("r", encoding=UTF_8_ENCODING) as handle:
                self._key_cache[key] = _scan_shard_for_key(handle, key)
        except (_UnscannableShardError, yaml.YAMLError):
            return False
        return True

    def _resolve_key(self, key: str) -> None:
        if key in self._key_cache:
            return
        rel_shard = route_key_to_shard(key)
        if not self._scan_shard_file(rel_shard, key):
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
