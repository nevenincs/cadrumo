"""Real-behaviour schema coverage for static matrix quantized rows."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from dev.docs.terminology._static_matrix import QuantizedEmbeddingRow, QuantizedQueryTokenRow


def test_quantized_embedding_row_accepts_non_zero_values() -> None:
    """A valid candidate-result row is accepted by the schema."""
    row = QuantizedEmbeddingRow(term="prorrata", scale=1.0, values=(0, 1, -127))

    assert row.term == "prorrata"
    assert row.scale == 1.0
    assert row.values == (0, 1, -127)


def test_quantized_embedding_row_rejects_all_zero_values() -> None:
    """A candidate-result row with no semantic signal is rejected."""
    with pytest.raises(ValidationError, match="quantized embedding rows must contain a non-zero value"):
        QuantizedEmbeddingRow(term="prorrata", scale=1.0, values=(0, 0, 0))


def test_quantized_query_token_row_accepts_non_zero_values() -> None:
    """A valid browser-addressable query-token row is accepted by the schema."""
    row = QuantizedQueryTokenRow(token="prorrata", token_id=17, scale=1.0, values=(0, 1, -127))

    assert row.token == "prorrata"
    assert row.token_id == 17
    assert row.scale == 1.0
    assert row.values == (0, 1, -127)


def test_quantized_query_token_row_rejects_all_zero_values() -> None:
    """A query-token row with no semantic signal is rejected."""
    with pytest.raises(ValidationError, match="quantized query-token rows must contain a non-zero value"):
        QuantizedQueryTokenRow(token="prorrata", token_id=17, scale=1.0, values=(0, 0, 0))
