"""Public bundled-corpus queries under one published authority pin."""

from __future__ import annotations

from typing import Any

from cadrumo.application.corpus_search.reference_search import search_reference_corpus
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
    answer = read_pinned_reference(lambda operation: search_reference_corpus(query, limit=limit, operation=operation))
    return {
        "outcome": "found",
        "logical_generation": answer.generation.logical_generation,
        "reader_incarnation": answer.generation.reader_incarnation,
        "retrieval": public_value(answer.report.retrieval),
        "terminology": [public_value(hit) for hit in answer.report.terminology],
    }
