"""Public bundled-corpus queries under one published authority pin."""

from __future__ import annotations

from typing import Any

from cadrumo.application.corpus_search.reference_search import search_reference_corpus
from cadrumo.application.reference_catalogue import read_pinned_reference

from .bounded_pages import REPLY_BYTES, CursorRefusedError, encoded_size, page_text
from .protocol_contract import public_value

_CORPUS_LIMIT = 8
_TEXT_DETAIL = "verbatim_text is cut in windows: join the windows in order"


def corpus_query(args: dict[str, Any]) -> dict[str, Any]:
    """Ground one query in the bundled corpus and approved terminology.

    Exact citations resolve their verbatim evidence under the reported
    publication pin, and a text too long for one reply is served in windows.
    Lexical hits and terminology concepts come from the shipped corpus and
    handbook, which carry no profile data.
    """
    query = args["query"]
    limit = args.get("limit", _CORPUS_LIMIT)
    answer = read_pinned_reference(lambda operation: search_reference_corpus(query, limit=limit, operation=operation))
    terminology = [public_value(hit) for hit in answer.report.terminology]
    envelope = {
        "outcome": "found",
        "logical_generation": answer.generation.logical_generation,
        "reader_incarnation": answer.generation.reader_incarnation,
    }
    found = public_value(answer.report.retrieval)
    whole = {**envelope, "retrieval": found, "terminology": terminology}
    citation = found["citation"]
    if citation is None or encoded_size(whole) <= REPLY_BYTES:
        if args.get("cursor"):
            return _refused("cursor applies only to an exact citation whose text is too long for one reply")
        return whole

    def compose(window: str, paging: dict[str, Any]) -> dict[str, Any]:
        windowed = {**citation, "verbatim_text": window}
        return {**envelope, "retrieval": {**found, "citation": windowed}, "terminology": terminology, "paging": paging}

    try:
        return page_text("corpus_search", args, citation["verbatim_text"], compose, detail=_TEXT_DETAIL)
    except CursorRefusedError as error:
        return _refused(str(error))


def _refused(message: str) -> dict[str, Any]:
    return {"outcome": "refused", "code": "invalid_request", "message": message}
