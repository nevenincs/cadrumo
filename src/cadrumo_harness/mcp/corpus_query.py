"""Public bundled-corpus queries under one published authority pin."""

from __future__ import annotations

from typing import Any

from cadrumo.application.corpus_search.runtime import search_corpus
from cadrumo.application.corpus_search.terminology import search_terminology
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

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
    with bundled_indexed_authority().operation() as operation:
        retrieval = search_corpus(query, operation=operation, limit=limit)
        pin = operation.generation
    terminology = search_terminology(query, limit=limit)
    return {
        "outcome": "found",
        "logical_generation": pin.logical_generation,
        "reader_incarnation": pin.reader_incarnation,
        "retrieval": public_value(retrieval),
        "terminology": [public_value(hit) for hit in terminology],
    }
