"""Immutable provenance for the project-authoritative Rung-2 inputs.

This contract records the raw committed relevance source and the canonical
vocabulary identities derived from it.  It is intentionally provenance only:
the source digest does not establish that a relevance corpus is complete,
correct, or semantically ratified, and the vocabulary fingerprints do not
establish runtime token coverage or an aggregate miss-rate result.

The constructor accepts bytes and already-authoritative input iterables rather
than reading the filesystem or contacting RAG.  That keeps it deterministic
and lets the project-input assembler decide which source bytes and canonical
inputs are authoritative.
"""

from __future__ import annotations

from collections.abc import Iterable
from hashlib import sha256
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

from ._static_matrix import (
    canonical_query_tokens,
    canonical_vocabulary,
    query_token_fingerprint,
    vocabulary_fingerprint,
)

__all__ = [
    "Rung2InputProvenance",
    "build_rung2_input_provenance",
]

_Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
_RepositoryRelativePath = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=512)]


class Rung2InputProvenance(BaseModel):
    """Frozen identity evidence for one source-backed Rung-2 input set.

    ``source_sha256`` is the digest of the raw source bytes supplied to the
    constructor.  The two vocabulary digests identify the canonical sequences
    supplied to the same constructor.  None of these fields is a semantic
    acceptance claim: corpus completeness, relevance quality, and query-token
    coverage remain separate gates.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    source_relpath: _RepositoryRelativePath
    source_sha256: _Sha256
    vocabulary_sha256: _Sha256
    query_token_sha256: _Sha256

    @field_validator("source_relpath")
    @classmethod
    def _require_repository_relative_path(cls, value: str) -> str:
        """Canonicalise and require a non-escaping repository-relative path."""
        normalised = value.replace("\\", "/")
        if normalised.startswith("/") or (len(normalised) >= 2 and normalised[0].isalpha() and normalised[1] == ":"):
            raise ValueError("source_relpath must be repository-relative")
        parts = normalised.split("/")
        if any(part in {"", ".", ".."} for part in parts):
            raise ValueError("source_relpath must not contain empty, '.' or '..' path segments")
        return normalised


def build_rung2_input_provenance(
    *,
    source_relpath: str,
    source_bytes: bytes,
    vocabulary: Iterable[str],
    query_tokens: Iterable[str],
) -> Rung2InputProvenance:
    """Build deterministic provenance from raw bytes and canonical input material.

    This function is pure with respect to the repository: it performs no file
    access, provider selection, model loading, RAG request, threshold check, or
    runtime token-coverage measurement.  Canonicalisation and fingerprinting
    reuse the matrix contract's existing helpers.
    """
    canonical_terms = canonical_vocabulary(vocabulary)
    canonical_tokens = canonical_query_tokens(query_tokens)
    return Rung2InputProvenance(
        source_relpath=source_relpath,
        source_sha256=sha256(source_bytes).hexdigest(),
        vocabulary_sha256=vocabulary_fingerprint(canonical_terms),
        query_token_sha256=query_token_fingerprint(canonical_tokens),
    )
