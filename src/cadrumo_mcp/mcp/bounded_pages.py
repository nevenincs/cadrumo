"""Byte-bounded pages for the reference tools.

A reference answer stays in the model's context and is read again on every
later model call of the turn, so one catalogue returned whole costs far more
than the question did. A list-shaped answer is therefore served one page at a
time: the largest run of rows, starting at a cursor, whose whole reply still
fits :data:`REPLY_BYTES`. A text too long for one reply is served the same way
in windows of characters. Both are deterministic for one publication, so a
reader that follows ``next_cursor`` visits every row or character exactly once.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, Final

from cadrumo.core.hashing import canonical_json_bytes

REPLY_BYTES: Final = 12_000
"""The most bytes a paged reply holds, counted as the compact JSON the wire carries."""

ROWS_MAX: Final = 100
"""The most rows a page holds, however small they are and whatever ``limit`` asks."""


class CursorRefusedError(ValueError):
    """A cursor that names no row or character of the answer it was passed with."""


def encoded_size(value: object) -> int:
    """Return how many bytes ``value`` takes as the compact JSON the wire carries."""
    return len(canonical_json_bytes(value))


def _largest_fit(count: int, fits: Callable[[int], bool]) -> int:
    """Return the largest ``n`` in ``1..count`` for which ``fits(n)`` holds, or 1 where none does.

    One row or character always goes out, so a reader that follows the cursors
    always advances.
    """
    low, high = 1, count
    while low < high:
        middle = (low + high + 1) // 2
        if fits(middle):
            low = middle
        else:
            high = middle - 1
    return low


def _next_call(tool: str, arguments: dict[str, Any], cursor: int) -> dict[str, Any]:
    return {"tool": tool, "arguments": {**arguments, "cursor": cursor}}


def _paging(
    tool: str, arguments: dict[str, Any], *, total: int, offset: int, returned: int, **facts: str
) -> dict[str, Any]:
    end = offset + returned
    paging: dict[str, Any] = {"total": total, "offset": offset, "returned": returned, **facts}
    if end < total:
        paging["next_cursor"] = end
        paging["next_call"] = _next_call(tool, arguments, end)
    else:
        paging["next_cursor"] = None
    return paging


def _served_from(cursor: int, total: int) -> int:
    """Admit a cursor that names a row or character, or the start of an answer that has none."""
    if cursor and cursor >= total:
        raise CursorRefusedError(f"cursor {cursor} is past the end: the answer holds {total}")
    return cursor


def page_rows(
    tool: str,
    arguments: dict[str, Any],
    rows: Sequence[Any],
    compose: Callable[[list[Any], dict[str, Any]], dict[str, Any]],
    **facts: str,
) -> dict[str, Any]:
    """Serve the page of ``rows`` that ``arguments`` name, composed into one whole reply.

    ``compose`` receives a page and its ``paging`` and returns the reply that
    carries them, so the bound counts everything the reader receives. ``facts``
    are text members of ``paging`` that say how to get the detail a row omits.
    """
    total = len(rows)
    offset = _served_from(arguments.get("cursor", 0), total)
    cap = min(arguments.get("limit", ROWS_MAX), ROWS_MAX, total - offset)

    def reply_of(count: int) -> dict[str, Any]:
        paging = _paging(tool, arguments, total=total, offset=offset, returned=count, **facts)
        return compose(list(rows[offset : offset + count]), paging)

    if cap == 0:
        return reply_of(0)
    return reply_of(_largest_fit(cap, lambda count: encoded_size(reply_of(count)) <= REPLY_BYTES))


def page_text(
    tool: str,
    arguments: dict[str, Any],
    text: str,
    compose: Callable[[str, dict[str, Any]], dict[str, Any]],
    **facts: str,
) -> dict[str, Any]:
    """Serve the window of ``text`` that ``arguments`` name, composed into one whole reply.

    Windows count characters of ``text`` and are cut so that the whole reply,
    with each character escaped as the wire escapes it, fits the bound.
    """
    total = len(text)
    offset = _served_from(arguments.get("cursor", 0), total)

    def reply_of(count: int) -> dict[str, Any]:
        paging = _paging(tool, arguments, total=total, offset=offset, returned=count, **facts)
        return compose(text[offset : offset + count], paging)

    cap = min(total - offset, REPLY_BYTES)
    if cap == 0:
        return reply_of(0)
    return reply_of(_largest_fit(cap, lambda count: encoded_size(reply_of(count)) <= REPLY_BYTES))
