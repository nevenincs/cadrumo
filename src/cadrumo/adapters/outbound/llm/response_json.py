"""Locating a JSON object inside a model reply.

A small model routinely wraps its answer in a code fence or a sentence, so the
object has to be located rather than assumed to be the whole reply. Two response
parsers each carried an identical copy of that search; this is the one they now
share.
"""

from __future__ import annotations

import json

__all__ = ["first_json_object"]


def first_json_object(text: str) -> str | None:
    """Return the first complete JSON object in ``text`` as its source substring, or ``None``.

    The SUBSTRING rather than the decoded object, so validation runs in
    pydantic's JSON mode. Strict validation of an already-decoded object would
    refuse a JSON array where the schema declares a tuple -- which every real
    reply carries, because JSON has no tuple.

    Decoding is delegated to the stdlib decoder, which knows where an object
    ends.
    """
    decoder = json.JSONDecoder()
    index = text.find("{")
    while index >= 0:
        try:
            _, end = decoder.raw_decode(text, index)
        except ValueError:
            index = text.find("{", index + 1)
            continue
        return text[index:end]
    return None
