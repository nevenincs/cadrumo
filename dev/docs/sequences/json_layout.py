"""Lossless JSON layout for recorded command output and its documentation view."""

from __future__ import annotations

import json

# Large record arrays dominate recordings. Keep a record on one reviewable line,
# but expand unusually large records instead of hiding whole subtrees on a line.
_RECORD_ARRAY_MIN_ITEMS = 16
_INLINE_RECORD_MAX_CHARS = 1024


def format_sequence_json(document: object) -> str:
    """Return sorted, indented JSON with bounded inline rows in large arrays.

    Only whitespace changes. Array order, every key and value, and JSON types
    are preserved; ordinary documents retain the standard two-space layout.
    """

    def render(value: object, depth: int) -> str:
        prefix = "  " * depth
        child_prefix = prefix + "  "
        if isinstance(value, dict) and value:
            entries = [
                f"{child_prefix}{json.dumps(key, ensure_ascii=False)}: {render(value[key], depth + 1)}"
                for key in sorted(value)
            ]
            return "{\n" + ",\n".join(entries) + "\n" + prefix + "}"
        if isinstance(value, list) and value:
            rows: list[str] = []
            for item in value:
                inline = None
                if len(value) >= _RECORD_ARRAY_MIN_ITEMS and isinstance(item, dict):
                    candidate = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                    if len(child_prefix) + len(candidate) <= _INLINE_RECORD_MAX_CHARS:
                        inline = candidate
                rows.append(child_prefix + (inline if inline is not None else render(item, depth + 1)))
            return "[\n" + ",\n".join(rows) + "\n" + prefix + "]"
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    return render(document, 0)
