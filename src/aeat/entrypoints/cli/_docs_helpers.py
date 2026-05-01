"""Pure helpers for the Docs CLI sub-app.

The Docs API uses 1-indexed character offsets, with index 1 being the
first usable position inside the body. ``insertText`` requests applied
in document order shift every later index by the inserted length, so
batches that perform multiple insertions are easiest to reason about
when built **in reverse document order** — that way every previous
index stays valid.
"""

from __future__ import annotations

from typing import Any


def extract_plaintext(document: dict[str, Any]) -> str:
    """Extract a plain-text rendering from a Docs ``documents.get`` payload.

    Walks the body content tree and concatenates every ``textRun`` it
    encounters. Tabs and paragraph boundaries are preserved as-is from
    the API; tables and embedded objects are skipped because the Docs
    JSON tree does not give them a stable plaintext representation.

    Args:
        document: The full ``documents.get`` response body.

    Returns:
        Concatenated plain-text contents.
    """
    body = document.get("body") or {}
    content = body.get("content") or []
    pieces: list[str] = []
    for element in content:
        paragraph = element.get("paragraph")
        if not paragraph:
            continue
        for run in paragraph.get("elements", []):
            text_run = run.get("textRun")
            if not text_run:
                continue
            piece = text_run.get("content")
            if isinstance(piece, str):
                pieces.append(piece)
    return "".join(pieces)


def find_end_index(document: dict[str, Any]) -> int:
    """Return the largest valid insertion index for a Docs payload.

    The Docs API exposes ``endIndex`` on the body's last content
    element, but inserting *at* that index is rejected because the
    final newline is reserved. The valid maximum is therefore
    ``endIndex - 1``.

    Args:
        document: ``documents.get`` response body.

    Returns:
        Highest insertable index, or 1 if the body is empty.
    """
    body = document.get("body") or {}
    content = body.get("content") or []
    if not content:
        return 1
    last = content[-1]
    end = last.get("endIndex")
    if isinstance(end, int) and end > 1:
        return end - 1
    return 1


def build_append_request(text: str, end_index: int) -> list[dict[str, Any]]:
    """Build a single-element batchUpdate request that appends ``text``.

    Always returns a one-element list so callers can extend it without
    branching on the empty-text case (an empty insertText is rejected
    by the API, so we filter at the call site).

    Args:
        text: Text to insert. Should not be empty.
        end_index: Insertion offset, typically the result of
            :func:`find_end_index`.

    Returns:
        A list with one ``insertText`` request, ready to feed into
        ``documents.batchUpdate``.
    """
    return [
        {
            "insertText": {
                "location": {"index": end_index},
                "text": text,
            }
        }
    ]


def build_replace_all_request(old: str, new: str) -> list[dict[str, Any]]:
    """Build a Docs ``replaceAllText`` batchUpdate request.

    Args:
        old: Substring to replace.
        new: Replacement text.

    Returns:
        A list with one ``replaceAllText`` request.
    """
    return [
        {
            "replaceAllText": {
                "containsText": {"text": old, "matchCase": True},
                "replaceText": new,
            }
        }
    ]
