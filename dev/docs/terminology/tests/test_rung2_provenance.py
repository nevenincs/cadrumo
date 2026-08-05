"""Real-behaviour coverage for source-backed Rung-2 provenance."""

from __future__ import annotations

from hashlib import sha256

import pytest
from pydantic import ValidationError

from dev.docs.terminology._rung2_provenance import (
    Rung2InputProvenance,
    build_rung2_input_provenance,
)
from dev.docs.terminology._static_matrix import (
    canonical_query_tokens,
    canonical_vocabulary,
    query_token_fingerprint,
    vocabulary_fingerprint,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


def test_builder_records_raw_source_and_canonical_input_identities() -> None:
    """The provenance fields identify the supplied bytes and canonical inputs."""
    source_bytes = b'{"query":"Modelo 130 casilla 15"}\x00\xff'
    vocabulary = ("  MODELO 130  ", "café", "CAFÉ")
    query_tokens = ("Casilla-15", "GASTO", "CASILLA 15")

    provenance = build_rung2_input_provenance(
        source_relpath="src/cadrumo/_data/terminology/relevance.json",
        source_bytes=source_bytes,
        vocabulary=vocabulary,
        query_tokens=query_tokens,
    )

    canonical_terms = canonical_vocabulary(vocabulary)
    canonical_tokens = canonical_query_tokens(query_tokens)
    assert provenance.source_sha256 == sha256(source_bytes).hexdigest()
    assert provenance.vocabulary_sha256 == vocabulary_fingerprint(canonical_terms)
    assert provenance.query_token_sha256 == query_token_fingerprint(canonical_tokens)


@pytest.mark.parametrize(
    "source_relpath",
    (
        "/absolute/relevance.json",
        r"C:\repo\relevance.json",
        r"\\server\share\relevance.json",
        "../relevance.json",
        r"nested\..\relevance.json",
        "nested/../../relevance.json",
    ),
)
def test_builder_rejects_absolute_or_escaping_source_paths(source_relpath: str) -> None:
    """Source identity must remain inside the repository-relative namespace."""
    with pytest.raises(ValidationError):
        build_rung2_input_provenance(
            source_relpath=source_relpath,
            source_bytes=b"relevance",
            vocabulary=("modelo 130",),
            query_tokens=("modelo 130",),
        )


def test_provenance_rejects_extra_fields() -> None:
    """The immutable record has a closed schema."""
    provenance = build_rung2_input_provenance(
        source_relpath="src/relevance.json",
        source_bytes=b"relevance",
        vocabulary=("modelo 130",),
        query_tokens=("modelo 130",),
    )
    payload = provenance.model_dump()
    payload["unexpected"] = "not part of the provenance contract"

    with pytest.raises(ValidationError):
        Rung2InputProvenance.model_validate(payload)


def test_provenance_rejects_mutation() -> None:
    """The record cannot be changed after its source identity is captured."""
    provenance = build_rung2_input_provenance(
        source_relpath="src/relevance.json",
        source_bytes=b"relevance",
        vocabulary=("modelo 130",),
        query_tokens=("modelo 130",),
    )

    with pytest.raises(ValidationError):
        provenance.source_sha256 = "0" * 64  # type: ignore[misc]
