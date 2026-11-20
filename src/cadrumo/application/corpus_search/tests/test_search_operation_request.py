"""The corpus search request is strict and bounded before any search runs."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from cadrumo.core.external_constants import OutputLanguage

from ..search_operation import (
    REFERENCE_CORPUS_LIMIT_DEFAULT,
    REFERENCE_CORPUS_LIMIT_MAX,
    REFERENCE_CORPUS_QUERY_MAX_LENGTH,
    ReferenceCorpusSearchRequest,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _request(**fields: object) -> ReferenceCorpusSearchRequest:
    return ReferenceCorpusSearchRequest.model_validate(
        {"profile_id": uuid4(), "query": "recargo", "output_language": OutputLanguage.ES, **fields}
    )


def test_a_query_is_trimmed_and_the_limit_defaults() -> None:
    request = _request(query="  recargo  ")

    assert request.query == "recargo"
    assert request.limit == REFERENCE_CORPUS_LIMIT_DEFAULT


def test_the_bounds_are_inclusive() -> None:
    longest = _request(query="a" * REFERENCE_CORPUS_QUERY_MAX_LENGTH, limit=REFERENCE_CORPUS_LIMIT_MAX)

    assert len(longest.query) == REFERENCE_CORPUS_QUERY_MAX_LENGTH
    assert longest.limit == REFERENCE_CORPUS_LIMIT_MAX


@pytest.mark.parametrize(
    "fields",
    (
        {"query": ""},
        {"query": "   "},
        {"query": "a" * (REFERENCE_CORPUS_QUERY_MAX_LENGTH + 1)},
        {"limit": 0},
        {"limit": REFERENCE_CORPUS_LIMIT_MAX + 1},
        {"limit": "3"},
        {"output_language": "fr"},
        {"locale": "en"},
    ),
)
def test_an_unbounded_or_unknown_field_is_refused(fields: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _request(**fields)


def test_a_refused_request_does_not_echo_the_query() -> None:
    secret_query = "x" * (REFERENCE_CORPUS_QUERY_MAX_LENGTH + 1)

    with pytest.raises(ValidationError) as refused:
        _request(query=secret_query)

    assert secret_query not in str(refused.value)
