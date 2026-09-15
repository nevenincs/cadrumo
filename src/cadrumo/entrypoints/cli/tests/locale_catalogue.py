"""Read-only locale catalogue support for CLI conformance tests.

The CLI tests need only parse the shipped YAML and flatten its leaves.  That
test-facing question is intentionally kept beside the tests instead of
pulling the repository's write-capable locale maintenance manager into the
shipped package graph.
"""

from __future__ import annotations

from pathlib import Path
from typing import IO

import yaml

from ....core.external_constants import UTF_8_ENCODING

type LocaleNode = str | dict[str, "LocaleNode"] | None


def _coerce_locale_mapping(value: object) -> dict[str, LocaleNode]:
    if not isinstance(value, dict):
        raise TypeError(f"Locale root must be a mapping; got {type(value).__name__}")

    mapping: dict[str, LocaleNode] = {}
    for key, child in value.items():
        if not isinstance(key, str):
            raise TypeError(f"Locale mapping keys must be text; got {type(key).__name__}")
        mapping[key] = _coerce_locale_node(child)
    return mapping


def _coerce_locale_node(value: object) -> LocaleNode:
    if isinstance(value, str) or value is None:
        return value
    if isinstance(value, dict):
        return _coerce_locale_mapping(value)
    raise TypeError(f"Locale values must be text, mappings, or null; got {type(value).__name__}")


def _locale_key(value: object) -> str:
    if not isinstance(value, (str, int, float, bool)):
        raise TypeError(f"Locale mapping keys must be scalar; got {type(value).__name__}")
    return str(value)


class _StrictUniqueKeyLoader(yaml.SafeLoader):
    """Reject duplicate YAML keys while retaining the safe-loader boundary."""

    pass


def _construct_locale_mapping(loader: _StrictUniqueKeyLoader, node: yaml.MappingNode) -> dict[str, LocaleNode]:
    mapping: dict[str, LocaleNode] = {}
    for key_node, value_node in node.value:
        key = _locale_key(loader.construct_object(key_node, deep=True))
        if key in mapping:
            raise ValueError(f"Duplicate locale key {key!r} at line {key_node.start_mark.line + 1}")
        mapping[key] = _coerce_locale_node(loader.construct_object(value_node, deep=True))
    return mapping


_StrictUniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_locale_mapping,
)


def _parse_locale(source: IO[str]) -> dict[str, LocaleNode]:
    loader = _StrictUniqueKeyLoader(source)
    try:
        data = loader.get_single_data()
    finally:
        loader.dispose()
    return {} if data is None else _coerce_locale_mapping(data)


def _merge(base: dict[str, LocaleNode], overlay: dict[str, LocaleNode]) -> None:
    for key, value in overlay.items():
        current = base.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            _merge(current, value)
        else:
            base[key] = value


def load_locale(path: Path) -> dict[str, LocaleNode]:
    """Load one locale shard directory or flat YAML catalogue."""
    if path.is_dir():
        merged: dict[str, LocaleNode] = {}
        for shard in sorted(path.rglob("*.yml")):
            with shard.open(encoding=UTF_8_ENCODING) as source:
                _merge(merged, _parse_locale(source))
        return merged
    with path.open(encoding=UTF_8_ENCODING) as source:
        return _parse_locale(source)


def get_yaml_keys(data: dict[str, LocaleNode], prefix: str = "") -> set[str]:
    """Return all leaf paths in a parsed locale mapping."""
    keys: set[str] = set()
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            keys.update(get_yaml_keys(value, path))
        else:
            keys.add(path)
    return keys


__all__ = ["LocaleNode", "get_yaml_keys", "load_locale"]
