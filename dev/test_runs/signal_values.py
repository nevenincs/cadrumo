"""Decode command-signal JSON scalars and persist bounded transcript detail records."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Final, TypeGuard

from dev._paths import UTF_8

_UTF_8: Final[str] = UTF_8


_HOTSPOT_LIMIT: Final[int] = 10


def _is_json_object(value: object) -> TypeGuard[dict[str, object]]:
    """Narrow a decoded JSON value to an object with string keys."""
    return isinstance(value, dict) and all(isinstance(key, str) for key in value)


def _json_int(value: object, *, field: str) -> int:
    """Decode one JSON scalar accepted by the command transcript contract."""
    if isinstance(value, (int, float, str)):
        return int(value)
    raise TypeError(f"JSON field {field!r} must be an integer-compatible scalar")


def _json_string_list(value: object, *, field: str) -> tuple[str, ...]:
    """Decode one JSON array whose values are rendered as transcript strings."""
    if not isinstance(value, list):
        raise TypeError(f"JSON field {field!r} must be an array")
    return tuple(str(item) for item in value)


def _top(
    counter: Counter[str],
    *,
    limit: int = _HOTSPOT_LIMIT,
    minimum_count: int = 1,
) -> list[dict[str, object]]:
    """Return a deterministic bounded frequency table."""
    rows: list[dict[str, object]] = []
    for value, count in sorted(counter.items(), key=lambda item: (-item[1], item[0])):
        if count >= minimum_count:
            rows.append({"count": count, "value": value})
    return rows[:limit]


def _write_json_lines(path: Path, rows: object) -> None:
    """Persist a stable JSON-lines collection, refusing non-list payloads."""
    if not isinstance(rows, list):
        rows = []
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding=_UTF_8,
        newline="\n",
    )
