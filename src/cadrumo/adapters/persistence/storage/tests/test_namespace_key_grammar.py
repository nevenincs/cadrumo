"""Prove each corrected namespace grammar describes the live object-key shape.

The :data:`~adapters.persistence.storage.TRANSACTION_CATALOGUE_NAMESPACE` and
:data:`~adapters.persistence.storage.CALCULATION_OBSERVATIONS_NAMESPACE`
``object_key_grammar`` fields are the sole metadata authority for the secure-object
keys their repositories write. These tests derive the real object keys from the
production key-derivation helpers and assert the declared grammar matches them, so a
future drift between the grammar and the live key shape fails loudly rather than
sitting as stale documentation.
"""

from __future__ import annotations

import re

import pytest

from .....application.calculations import member_observation_key, observation_key
from .....core import Period
from .....domain.transactions import transaction_index_object_key, transaction_object_key
from .. import CALCULATION_OBSERVATIONS_NAMESPACE, TRANSACTION_CATALOGUE_NAMESPACE

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def _shape_to_regex(shape: str) -> re.Pattern[str]:
    """Compile one declared key-grammar shape into an anchored matcher.

    ``{placeholder}`` matches one non-``:`` segment; a ``[...]`` group is an
    optional segment; every other character is a literal separator.
    """
    parts: list[str] = ["^"]
    index = 0
    while index < len(shape):
        char = shape[index]
        if char == "{":
            close = shape.index("}", index)
            parts.append("[^:]+")
            index = close + 1
        elif char == "[":
            parts.append("(?:")
            index += 1
        elif char == "]":
            parts.append(")?")
            index += 1
        else:
            parts.append(re.escape(char))
            index += 1
    parts.append("$")
    return re.compile("".join(parts))


def _declared_shapes(grammar: str) -> list[re.Pattern[str]]:
    return [_shape_to_regex(shape.strip()) for shape in grammar.split(";")]


def _matches_any(key: str, shapes: list[re.Pattern[str]]) -> bool:
    return any(shape.match(key) for shape in shapes)


def test_transaction_catalogue_grammar_describes_live_secure_object_keys() -> None:
    shapes = _declared_shapes(TRANSACTION_CATALOGUE_NAMESPACE.object_key_grammar)

    row_key = transaction_object_key("bucket-7", "tx-42")
    index_key = transaction_index_object_key("bucket-7")

    assert row_key == "transaction:bucket-7:tx-42"
    assert index_key == "transaction-index:bucket-7"

    # Every live key the repository writes conforms to a declared shape.
    assert _matches_any(row_key, shapes)
    assert _matches_any(index_key, shapes)

    # Every declared shape is realized by a live key: no dead grammar entry.
    for shape in shapes:
        assert shape.match(row_key) or shape.match(index_key)

    # Anti-tautology: the BucketEvent audit object_id is a different concept and
    # must not be accepted as a secure-object key by this namespace's grammar.
    assert not _matches_any("transaction-catalogue:bucket-7", shapes)


def test_transaction_catalogue_pre_correction_grammar_rejected_the_live_keys() -> None:
    """The retired ``transaction-catalogue:{bucket_id}`` grammar matched neither key."""
    drifted = _declared_shapes("transaction-catalogue:{bucket_id}")

    assert not _matches_any(transaction_object_key("b", "t"), drifted)
    assert not _matches_any(transaction_index_object_key("b"), drifted)


def test_calculation_observation_grammar_describes_single_and_member_keys() -> None:
    shapes = _declared_shapes(CALCULATION_OBSERVATIONS_NAMESPACE.object_key_grammar)
    period = Period.from_year_and_code(2024, "1T")

    single_key = observation_key("353", period)
    member_key = member_observation_key("353", period, "B12345678")

    # The member key extends the single-filer key with a trailing NIF segment.
    assert member_key == f"{single_key}:B12345678"

    assert _matches_any(single_key, shapes)
    assert _matches_any(member_key, shapes)

    # Anti-tautology: a truncated two-segment key is not a valid observation key.
    assert not _matches_any("100:2024", shapes)


def test_calculation_observation_pre_correction_grammar_rejected_the_member_key() -> None:
    """The retired ``{modelo}:{filing_year}:{period}`` grammar dropped the member row."""
    drifted = _declared_shapes("{modelo}:{filing_year}:{period}")
    period = Period.from_year_and_code(2024, "1T")

    assert not _matches_any(member_observation_key("353", period, "B12345678"), drifted)
    # The single-filer key was always covered; only the member variant drifted.
    assert _matches_any(observation_key("100", period), drifted)
