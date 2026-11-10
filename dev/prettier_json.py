"""Lay JSON out as Prettier prints it, so a generated fixture is already in its committed byte form.

The window's fixtures are checked by Prettier. A producer that writes through
:func:`write_json` writes the bytes Prettier leaves unchanged, with LF line
endings, so seeding is byte-stable and a format check of the generated file
changes nothing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_WIDTH = 80
_INDENT = "  "


def _inline_list(value: list[Any]) -> str | None:
    """A list on one line, or ``None`` where Prettier breaks it: a matrix of several rows, or an item that breaks."""
    if not value:
        return "[]"
    if len(value) > 1 and all(isinstance(item, list) and len(item) > 1 for item in value):
        return None
    parts: list[str] = []
    for item in value:
        part = _inline(item)
        if part is None:
            return None
        parts.append(part)
    return "[" + ", ".join(parts) + "]"


def _inline(value: Any) -> str | None:
    """``value`` on one line as Prettier prints a JSON value that fits, or ``None`` where it breaks."""
    if isinstance(value, dict):
        return None if value else "{}"
    if isinstance(value, list):
        return _inline_list(value)
    return json.dumps(value, ensure_ascii=False)


def _render(value: Any, depth: int, room: int) -> str:
    """``value`` laid out as Prettier lays out JSON, ``room`` columns being left on its first line."""
    pad = _INDENT * depth
    inner = _INDENT * (depth + 1)
    flat = _inline(value)
    if flat is not None and len(flat) <= room:
        return flat
    if isinstance(value, dict):
        last = len(value) - 1
        lines = []
        for place, (key, item) in enumerate(value.items()):
            head = f"{json.dumps(key, ensure_ascii=False)}: "
            left = _WIDTH - len(inner) - len(head) - (0 if place == last else 1)
            lines.append(inner + head + _render(item, depth + 1, left))
        return "{\n" + ",\n".join(lines) + "\n" + pad + "}"
    if isinstance(value, list):
        last = len(value) - 1
        rows = [
            inner + _render(item, depth + 1, _WIDTH - len(inner) - (0 if place == last else 1))
            for place, item in enumerate(value)
        ]
        return "[\n" + ",\n".join(rows) + "\n" + pad + "]"
    return json.dumps(value, ensure_ascii=False)


def dump_json(value: Any) -> str:
    """``value`` as the JSON text Prettier leaves unchanged, so formatting the file changes nothing."""
    return _render(value, 0, _WIDTH) + "\n"


def write_json(path: Path, value: Any) -> None:
    """Write ``value`` to ``path`` in its committed byte form: Prettier's layout, UTF-8, LF line endings."""
    path.write_text(dump_json(value), encoding="utf-8", newline="\n")
