"""Split a machine-secret field that carries a JSON array into the JSON text of each item."""

from __future__ import annotations

import json


def json_array_items(text: str) -> tuple[str, ...]:
    """Return each element of a JSON array as its own JSON text; blank text is no elements.

    Raises ``ValueError`` when the text is not one JSON array. The message names the
    shape and never the content, since the content is private.
    """
    if not text.strip():
        return ()
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError:
        raise ValueError("the field must hold one JSON array") from None
    if not isinstance(decoded, list):
        raise ValueError("the field must hold one JSON array")
    return tuple(json.dumps(item) for item in decoded)


__all__ = ["json_array_items"]
