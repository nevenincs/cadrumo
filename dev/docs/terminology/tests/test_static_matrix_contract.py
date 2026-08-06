"""Real-behaviour schema coverage for static matrix quantized rows."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from dev.docs.terminology._static_matrix import (
    EmbeddingObservation,
    ModelMetadata,
    NormalizationContract,
    ProviderProvenance,
    QuantizedEmbeddingRow,
    QuantizedQueryTokenRow,
    QueryTokenObservation,
    TokenizerProvenance,
    compile_static_embedding_matrix,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


class DeterministicMatrixProvider:
    """Provide typed, finite observations for the compiler contract test."""

    metadata = ModelMetadata(
        repository="test/model",
        revision="0" * 40,
        spdx_license="MIT",
        dimension=3,
        model_snapshot_sha256="0" * 64,
        provider=ProviderProvenance(
            package="test-provider",
            version="1.0.0",
            source_sha256="0" * 64,
        ),
        tokenizer=TokenizerProvenance(
            package="test-tokenizer",
            version="1.0.0",
            repository="test/tokenizer",
            revision="0" * 40,
            vocabulary_sha256="0" * 64,
            config_sha256="0" * 64,
            normalization=NormalizationContract(
                algorithm="unicode-word-runs-nfkc-lower-v1",
                unicode_form="NFKC",
                case_mapping="lower",
                accent_policy="preserve",
                token_boundaries="unicode-letter-number-runs-v1",
                separator_policy="collapse-to-boundary-v1",
            ),
        ),
    )

    def embed(self, terms: tuple[str, ...]) -> tuple[EmbeddingObservation, ...]:
        return tuple(
            EmbeddingObservation(
                term=term,
                token_ids=(17,),
                token_count=1,
                vector=(1.0, 0.5, 0.25),
            )
            for term in terms
        )

    def embed_query_tokens(self, tokens: tuple[str, ...]) -> tuple[QueryTokenObservation, ...]:
        return tuple(
            QueryTokenObservation(
                token=token,
                model_token_ids=(17,),
                token_count=1,
                vector=(1.0, 0.5, 0.25),
            )
            for token in tokens
        )


def test_matrix_compiler_preserves_strict_tuple_collections() -> None:
    """Compiler payload collections remain tuples for strict model validation."""
    matrix = compile_static_embedding_matrix(
        ("prorrata",),
        DeterministicMatrixProvider(),
        query_tokens=("prorrata",),
    )

    assert isinstance(matrix.token_inventory, tuple)
    assert isinstance(matrix.rows, tuple)
    assert isinstance(matrix.query_token_rows, tuple)
    assert isinstance(matrix.token_inventory[0].token_ids, tuple)
    assert isinstance(matrix.rows[0].values, tuple)
    assert isinstance(matrix.query_token_rows[0].values, tuple)


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
    row = QuantizedQueryTokenRow(
        token="prorrata",
        model_token_ids=(17, 23),
        token_count=2,
        scale=1.0,
        values=(0, 1, -127),
    )

    assert row.token == "prorrata"
    assert row.model_token_ids == (17, 23)
    assert row.token_count == 2
    assert row.scale == 1.0
    assert row.values == (0, 1, -127)


def test_quantized_query_token_row_rejects_all_zero_values() -> None:
    """A query-token row with no semantic signal is rejected."""
    with pytest.raises(ValidationError, match="quantized query-token rows must contain a non-zero value"):
        QuantizedQueryTokenRow(
            token="prorrata",
            model_token_ids=(17, 23),
            token_count=2,
            scale=1.0,
            values=(0, 0, 0),
        )
