"""Read-only locale catalogue support for CLI conformance tests.

The CLI tests need only parse the shipped YAML and flatten its leaves.  That
test-facing question is intentionally kept beside the tests instead of
pulling the repository's write-capable locale maintenance manager into the
shipped package graph.
"""

from __future__ import annotations

from collections.abc import Hashable
from pathlib import Path
from typing import IO, Any

import yaml

from .....core.external_constants import UTF_8_ENCODING

type LocaleNode = str | dict[str, "LocaleNode"] | None


class _StrictUniqueKeyLoader(getattr(yaml, "CSafeLoader", yaml.SafeLoader)):  # type: ignore[misc,valid-type]
    """Reject duplicate YAML keys while retaining the safe-loader boundary."""

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Hashable, Any]:
        mapping: dict[Hashable, Any] = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in mapping:
                raise ValueError(f"Duplicate locale key {key!r} at line {key_node.start_mark.line + 1}")
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


def _parse_locale(source: IO[str]) -> dict[str, LocaleNode]:
    loader = _StrictUniqueKeyLoader(source)
    try:
        data = loader.get_single_data()
    finally:
        loader.dispose()
    return data if data is not None else {}


def _merge(base: dict[str, LocaleNode], overlay: dict[str, LocaleNode]) -> None:
    for key, value in overlay.items():
        if isinstance(base.get(key), dict) and isinstance(value, dict):
            _merge(base[key], value)  # type: ignore[arg-type]
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
