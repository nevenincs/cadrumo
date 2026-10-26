"""Public bundled-corpus queries under one published authority pin."""

from __future__ import annotations

from typing import Any

from cadrumo.application.corpus_search.runtime import search_corpus
from cadrumo.application.corpus_search.terminology import search_terminology
from cadrumo.application.reference_catalogue import read_pinned_reference

from .protocol_contract import public_value

_CORPUS_LIMIT = 8


def corpus_query(args: dict[str, Any]) -> dict[str, Any]:
    """Ground one query in the bundled corpus and approved terminology.

    Exact citations resolve their verbatim evidence under the reported
    publication pin. Lexical hits and terminology concepts come from the
    shipped corpus and handbook, which carry no profile data.
    """
    query = args["query"]
    limit = args.get("limit", _CORPUS_LIMIT)
    retrieval = read_pinned_reference(lambda operation: search_corpus(query, operation=operation, limit=limit))
    terminology = search_terminology(query, limit=limit)
    return {
        "outcome": "found",
        "logical_generation": retrieval.generation.logical_generation,
        "reader_incarnation": retrieval.generation.reader_incarnation,
        "retrieval": public_value(retrieval.report),
        "terminology": [public_value(hit) for hit in terminology],
    }
