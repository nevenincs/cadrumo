"""Shape extraction for untyped JSON documents from external services.

Discovery-style clients (Google Drive, Google Sheets) return decoded JSON with
no static shape. Reading a nested array or object out of one is the same three
steps every time: confirm the container is a string-keyed object, read the key,
and confirm the value has the shape the caller is about to rely on. These
helpers own that sequence so callers narrow once, at the boundary, instead of
re-deriving it per call site.

A value that fails a check is absent, not empty: the helpers return an empty
result so the caller sees "no rows" rather than a partially typed value. They
never coerce a malformed value into a plausible one.
"""

from __future__ import annotations

from .type_guards import is_object_list, is_str_keyed_dict

__all__ = ["str_keyed_mapping", "str_keyed_rows"]


def str_keyed_mapping(value: object) -> dict[str, object]:
    """Return ``value`` when it is a string-keyed object, else an empty mapping.

    A JSON object whose keys are not strings cannot carry the named fields a
    caller reads, so it is reported as absent rather than partially honoured.
    """
    return value if is_str_keyed_dict(value) else {}


def str_keyed_rows(container: object, key: str) -> list[dict[str, object]]:
    """Return ``container[key]`` as the string-keyed objects it contains.

    Returns an empty list when the container is not a string-keyed object, when
    the key is absent, or when its value is not an array. Array entries that are
    not themselves string-keyed objects are dropped: they cannot carry the
    fields the caller reads.
    """
    if not is_str_keyed_dict(container):
        return []
    raw_rows = container.get(key)
    if not is_object_list(raw_rows):
        return []
    return [row for row in raw_rows if is_str_keyed_dict(row)]
