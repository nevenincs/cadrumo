"""Compile a bounded, provenance-stamped static term-embedding matrix.

The resident vaultspec-rag service and its model weights remain dev-only.  This
module owns the deterministic seam between that build-time oracle and the
plain-data matrix that a later browser-side cosine tier may consume:

* the vocabulary is normalised, deduplicated, byte-sorted, and fingerprinted;
* a provider must return exactly one tokenised, finite vector for every term;
* a provider must separately return exact browser-recognizable query-token
  vectors with complete model-token provenance; and
* vectors are normalised and quantised with a specified per-row int8 scheme;
* the output carries model, provider, tokenizer, licence, vocabulary, row-order,
  and artifact provenance; and
* the serialized artifact is hard-capped before it can be written.

No model package, model download, vaultspec-rag import, or browser dependency
belongs here.  A concrete pinned provider is supplied by the dev-box step
after model selection and measurement have been ratified.
"""

from __future__ import annotations

import math
import re
import struct
import unicodedata
from collections.abc import Iterable
from hashlib import sha256
from pathlib import Path
from typing import Annotated, Final, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from ._jcs import canonical_json_bytes

__all__ = [
    "DEFAULT_MAX_SERIALIZED_BYTES",
    "EMBEDDING_MATRIX_SCHEMA_VERSION",
    "INT8_QUANTIZATION_ALGORITHM",
    "NORMALIZATION_CONTRACT_VERSION",
    "ROW_ORDER",
    "EmbeddingObservation",
    "MatrixCompilationError",
    "ModelMetadata",
    "NormalizationContract",
    "ProviderProvenance",
    "QuantizedEmbeddingRow",
    "QuantizedQueryTokenRow",
    "QueryTokenObservation",
    "StaticEmbeddingMatrix",
    "StaticEmbeddingProvider",
    "TokenInventoryEntry",
    "TokenizerProvenance",
    "canonical_query_tokens",
    "canonical_vocabulary",
    "canonical_vocabulary_bytes",
    "compile_static_embedding_matrix",
    "load_static_embedding_matrix",
    "normalise_query_tokens",
    "query_token_fingerprint",
    "vocabulary_fingerprint",
    "write_static_embedding_matrix",
]

_UTF_8: Final[str] = "utf-8"
DEFAULT_MAX_SERIALIZED_BYTES: Final[int] = 3_000_000
EMBEDDING_MATRIX_SCHEMA_VERSION: Final[int] = 4
INT8_QUANTIZATION_ALGORITHM: Final[str] = "symmetric-per-row-int8-f32-v1"
NORMALIZATION_CONTRACT_VERSION: Final[str] = "unicode-word-runs-nfkc-lower-v1"
ROW_ORDER: Final[str] = "canonical-utf8-byte-order-v1"
_IMMUTABLE_REVISION = re.compile(r"^[0-9a-f]{40}$")
_ALLOWED_SPDX_LICENSES = frozenset({"MIT", "Apache-2.0"})

_Term = Annotated[str, StringConstraints(min_length=1, max_length=160)]
_QueryToken = Annotated[str, StringConstraints(min_length=1, max_length=160)]
_TokenId = Annotated[int, Field(ge=0)]
_Int8Value = Annotated[int, Field(ge=-127, le=127)]
_Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class MatrixCompilationError(ValueError):
    """Raised when provider output cannot satisfy the matrix contract."""


class ProviderProvenance(BaseModel):
    """Pinned package identity for the build-time embedding provider."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    package: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=256)]
    version: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
    source_sha256: _Sha256


class NormalizationContract(BaseModel):
    """Versioned normalization shared by the compiler and browser reader.

    The fields are deliberately explicit rather than a prose note.  A future
    browser implementation can reject a matrix whose algorithm identifier is
    not one it implements, instead of silently applying a different Unicode or
    token-boundary policy.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    algorithm: Literal["unicode-word-runs-nfkc-lower-v1"]
    unicode_form: Literal["NFKC"]
    case_mapping: Literal["lower"]
    accent_policy: Literal["preserve"]
    token_boundaries: Literal["unicode-letter-number-runs-v1"]
    separator_policy: Literal["collapse-to-boundary-v1"]


class TokenizerProvenance(BaseModel):
    """Pinned tokenizer identity and content hashes used for query rows."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    package: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=256)]
    version: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
    repository: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=256)]
    revision: Annotated[str, StringConstraints(min_length=40, max_length=40)]
    vocabulary_sha256: _Sha256
    config_sha256: _Sha256
    normalization: NormalizationContract

    @field_validator("revision")
    @classmethod
    def _require_immutable_revision(cls, value: str) -> str:
        """Require a full immutable tokenizer revision, never a branch name."""
        revision = value.casefold()
        if not _IMMUTABLE_REVISION.fullmatch(revision):
            raise ValueError("tokenizer revision must be a 40-character immutable hexadecimal commit")
        return revision


class ModelMetadata(BaseModel):
    """Immutable model and implementation provenance for matrix rows.

    ``model_snapshot_sha256`` is the root of the reviewed raw-byte manifest for
    the complete local model snapshot.  It is separate from tokenizer role
    hashes because tokenizer bytes do not attest the embedding weights.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    repository: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=256)]
    revision: Annotated[str, StringConstraints(min_length=40, max_length=40)]
    spdx_license: Literal["MIT", "Apache-2.0"]
    dimension: int = Field(gt=0, le=8192)
    model_snapshot_sha256: _Sha256
    provider: ProviderProvenance
    tokenizer: TokenizerProvenance

    @field_validator("revision")
    @classmethod
    def _require_immutable_revision(cls, value: str) -> str:
        """Require and canonicalise a full immutable revision hash."""
        revision = value.casefold()
        if not _IMMUTABLE_REVISION.fullmatch(revision):
            raise ValueError("model revision must be a 40-character immutable hexadecimal commit")
        return revision

    @field_validator("spdx_license")
    @classmethod
    def _require_allowed_license(cls, value: Literal["MIT", "Apache-2.0"]) -> Literal["MIT", "Apache-2.0"]:
        """Keep the shipped matrix inside the accepted licence set."""
        if value not in _ALLOWED_SPDX_LICENSES:
            raise ValueError("matrix model licence must be MIT or Apache-2.0")
        return value


class EmbeddingObservation(BaseModel):
    """One provider response for one canonical vocabulary term.

    Token ids are retained in the matrix's audit inventory.  Pinning the model
    revision makes those ids meaningful without shipping the model vocabulary.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    term: _Term
    token_ids: tuple[_TokenId, ...] = Field(min_length=1)
    token_count: int = Field(ge=1)
    vector: tuple[float, ...] = Field(min_length=1)

    @field_validator("vector")
    @classmethod
    def _require_finite_vector(cls, value: tuple[float, ...]) -> tuple[float, ...]:
        """Reject non-finite provider output before any arithmetic occurs."""
        if any(not math.isfinite(component) for component in value):
            raise ValueError("embedding vectors must contain only finite values")
        return value

    @model_validator(mode="after")
    def _token_count_matches_inventory(self) -> EmbeddingObservation:
        """Refuse silent tokenizer drops or fabricated token counts."""
        if self.token_count != len(self.token_ids):
            raise ValueError("token_count must equal the token_ids inventory length")
        return self


class QueryTokenObservation(BaseModel):
    """One provider response for one browser-recognizable query token.

    A term row is a candidate result representation.  A query-token row is a
    separate contract: its normalized browser token, complete ordered model
    token-id tuple, and count are retained so the browser can recognise covered
    query material without shipping the model tokenizer or weights. The
    provider owns subword pooling and must echo the requested token identity
    exactly; the tuple remains audit provenance for that pooled row.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    token: _QueryToken
    model_token_ids: tuple[_TokenId, ...] = Field(min_length=1)
    token_count: int = Field(ge=1)
    vector: tuple[float, ...] = Field(min_length=1)

    @field_validator("token")
    @classmethod
    def _require_canonical_token(cls, value: str) -> str:
        """Require the exact normalized browser lookup key."""
        if normalise_query_tokens(value) != (value,):
            raise ValueError("query-token text must be one canonical normalized word")
        return value

    @field_validator("vector")
    @classmethod
    def _require_finite_vector(cls, value: tuple[float, ...]) -> tuple[float, ...]:
        """Reject non-finite provider output before any arithmetic occurs."""
        if any(not math.isfinite(component) for component in value):
            raise ValueError("query-token vectors must contain only finite values")
        return value

    @model_validator(mode="after")
    def _token_count_matches_inventory(self) -> QueryTokenObservation:
        """Refuse silent subword drops or fabricated token counts."""
        if self.token_count != len(self.model_token_ids):
            raise ValueError("token_count must equal the model_token_ids inventory length")
        return self


class TokenInventoryEntry(BaseModel):
    """The model-token inventory for one shipped vocabulary row."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    term: _Term
    token_ids: tuple[_TokenId, ...] = Field(min_length=1)
    token_count: int = Field(ge=1)

    @model_validator(mode="after")
    def _token_count_matches_inventory(self) -> TokenInventoryEntry:
        """Keep the persisted count tied to the persisted token ids."""
        if self.token_count != len(self.token_ids):
            raise ValueError("token_count must equal the token_ids inventory length")
        return self


class QuantizedEmbeddingRow(BaseModel):
    """One normalized vector encoded with a symmetric per-row int8 scale."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    term: _Term
    scale: float = Field(gt=0)
    values: tuple[_Int8Value, ...] = Field(min_length=1)

    @field_validator("values")
    @classmethod
    def _require_non_zero_row(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        """Reject a quantized row that cannot represent a semantic vector."""
        if not any(value):
            raise ValueError("quantized embedding rows must contain a non-zero value")
        return value

    @field_validator("scale")
    @classmethod
    def _require_finite_scale(cls, value: float) -> float:
        """Reject a scale that is not the declared float32 representation."""
        if not math.isfinite(value) or value <= 0.0:
            raise ValueError("quantization scale must be finite and positive")
        try:
            round_tripped = struct.unpack("<f", struct.pack("<f", value))[0]
        except (OverflowError, struct.error) as exc:
            raise ValueError("quantization scale cannot be represented as float32") from exc
        if round_tripped != value:
            raise ValueError("quantization scale must be exactly representable as float32")
        return value


class QuantizedQueryTokenRow(BaseModel):
    """One browser token encoded as a symmetric int8 row.

    ``model_token_ids`` records every ordered subword id pooled by the pinned
    provider to produce this row.  It is provenance, not a second browser
    tokenizer: the reader looks up the normalized ``token`` key.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    token: _QueryToken
    model_token_ids: tuple[_TokenId, ...] = Field(min_length=1)
    token_count: int = Field(ge=1)
    scale: float = Field(gt=0)
    values: tuple[_Int8Value, ...] = Field(min_length=1)

    @field_validator("values")
    @classmethod
    def _require_non_zero_row(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        """Reject a query-token row that cannot represent a semantic vector."""
        if not any(value):
            raise ValueError("quantized query-token rows must contain a non-zero value")
        return value

    @field_validator("token")
    @classmethod
    def _require_canonical_token(cls, value: str) -> str:
        """Keep the shipped lookup key on the shared normalization contract."""
        if normalise_query_tokens(value) != (value,):
            raise ValueError("query-token text must be one canonical normalized word")
        return value

    @field_validator("scale")
    @classmethod
    def _require_finite_scale(cls, value: float) -> float:
        """Reject a scale that is not the declared float32 representation."""
        if not math.isfinite(value) or value <= 0.0:
            raise ValueError("query-token quantization scale must be finite and positive")
        try:
            round_tripped = struct.unpack("<f", struct.pack("<f", value))[0]
        except (OverflowError, struct.error) as exc:
            raise ValueError("query-token quantization scale cannot be represented as float32") from exc
        if round_tripped != value:
            raise ValueError("query-token quantization scale must be exactly representable as float32")
        return value

    @model_validator(mode="after")
    def _token_count_matches_inventory(self) -> QuantizedQueryTokenRow:
        """Keep the shipped count tied to the complete ordered id tuple."""
        if self.token_count != len(self.model_token_ids):
            raise ValueError("token_count must equal the model_token_ids inventory length")
        return self


class StaticEmbeddingMatrix(BaseModel):
    """Self-attesting, bounded matrix with separate term/query-token rows.

    ``rows`` describe the closed candidate-result vocabulary.  ``query_token_rows``
    are intentionally a different typed surface: they are the only rows a
    future browser reader may average to represent query material.  Keeping
    the two collections distinct prevents a term-only artifact from being
    mistaken for a usable client-side tokenizer contract.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    schema_version: Literal[4]
    model: ModelMetadata
    vocabulary_sha256: _Sha256
    vocabulary_count: int = Field(ge=1)
    query_token_sha256: _Sha256
    query_token_count: int = Field(ge=1)
    dimension: int = Field(gt=0, le=8192)
    quantization_algorithm: Literal["symmetric-per-row-int8-f32-v1"]
    row_order: Literal["canonical-utf8-byte-order-v1"]
    token_inventory: tuple[TokenInventoryEntry, ...] = Field(min_length=1)
    rows: tuple[QuantizedEmbeddingRow, ...] = Field(min_length=1)
    query_token_rows: tuple[QuantizedQueryTokenRow, ...] = Field(min_length=1)
    serialized_bytes: int = Field(gt=0, le=DEFAULT_MAX_SERIALIZED_BYTES)
    artifact_sha256: _Sha256

    @model_validator(mode="after")
    def _enforce_artifact_invariants(self) -> StaticEmbeddingMatrix:
        """Validate the vocabulary, row order, hashes, and size stamp."""
        if self.dimension != self.model.dimension:
            raise ValueError("matrix dimension must match model metadata dimension")
        if self.vocabulary_count != len(self.rows) or self.vocabulary_count != len(self.token_inventory):
            raise ValueError("vocabulary_count must match rows and token_inventory")
        if self.query_token_count != len(self.query_token_rows):
            raise ValueError("query_token_count must match query_token_rows")

        row_terms = tuple(row.term for row in self.rows)
        inventory_terms = tuple(entry.term for entry in self.token_inventory)
        query_tokens = tuple(row.token for row in self.query_token_rows)
        expected_query_order = tuple(sorted(query_tokens, key=lambda token: token.encode(_UTF_8)))
        expected_order = tuple(sorted(row_terms, key=lambda term: term.encode(_UTF_8)))
        if any(term != _canonical_term(term) for term in row_terms):
            raise ValueError("matrix rows must contain canonical vocabulary terms")
        if row_terms != expected_order or len(row_terms) != len(set(row_terms)):
            raise ValueError("matrix rows must be unique and sorted by canonical UTF-8 byte order")
        if any(not token.strip() for token in query_tokens):
            raise ValueError("matrix query-token rows must not contain blank token identities")
        if query_tokens != expected_query_order or len(query_tokens) != len(set(query_tokens)):
            raise ValueError("query-token rows must be unique and sorted by canonical UTF-8 byte order")
        if inventory_terms != row_terms:
            raise ValueError("token inventory must have the same row order and terms as the matrix")
        if any(len(row.values) != self.dimension for row in self.rows) or any(
            len(row.values) != self.dimension for row in self.query_token_rows
        ):
            raise ValueError("every matrix row must match the declared dimension")
        if self.vocabulary_sha256 != vocabulary_fingerprint(row_terms):
            raise ValueError("vocabulary_sha256 does not match the canonical row vocabulary")
        if self.query_token_sha256 != query_token_fingerprint(query_tokens):
            raise ValueError("query_token_sha256 does not match the query-token vocabulary")

        unsigned_payload = self.model_dump(mode="json", exclude={"serialized_bytes", "artifact_sha256"})
        expected_artifact = sha256(canonical_json_bytes(unsigned_payload)).hexdigest()
        if self.artifact_sha256 != expected_artifact:
            raise ValueError("artifact_sha256 does not match the unsigned matrix payload")
        if self.serialized_bytes != len(self.to_json_bytes()):
            raise ValueError("serialized_bytes does not match canonical artifact bytes")
        return self

    def to_json_bytes(self) -> bytes:
        """Return the canonical newline-terminated JSON representation."""
        return canonical_json_bytes(self.model_dump(mode="json"))


class StaticEmbeddingProvider(Protocol):
    """Build-time provider contract for a pinned embedding model."""

    @property
    def metadata(self) -> ModelMetadata:
        """Return the immutable model metadata for this provider."""
        ...

    def embed(self, terms: tuple[str, ...]) -> tuple[EmbeddingObservation, ...]:
        """Return exactly one tokenized vector observation per requested term."""
        ...

    def embed_query_tokens(self, tokens: tuple[str, ...]) -> tuple[QueryTokenObservation, ...]:
        """Return one exact normalized-word vector plus subword provenance per token."""
        ...


def canonical_vocabulary(terms: Iterable[str]) -> tuple[str, ...]:
    """Return the closed vocabulary in deterministic UTF-8 byte order."""
    canonical: set[str] = set()
    for term in terms:
        canonical.add(_canonical_term(term))
    if not canonical:
        raise MatrixCompilationError("the static matrix vocabulary cannot be empty")
    return tuple(sorted(canonical, key=lambda term: term.encode(_UTF_8)))


def canonical_vocabulary_bytes(terms: Iterable[str]) -> bytes:
    """Serialize canonical terms exactly as used by the vocabulary hash."""
    canonical = canonical_vocabulary(terms)
    return "\n".join(canonical).encode(_UTF_8)


def vocabulary_fingerprint(terms: Iterable[str]) -> str:
    """Return the SHA-256 fingerprint of the canonical vocabulary bytes."""
    return sha256(canonical_vocabulary_bytes(terms)).hexdigest()


def canonical_query_tokens(tokens: Iterable[object]) -> tuple[str, ...]:
    """Return browser-recognizable query words in deterministic UTF-8 order.

    The same versioned normalization contract is applied to compiler input and
    to the future browser query.  Provider rows must echo one of these exact
    normalized words; model subword identities live in ``model_token_ids``.
    """
    canonical: set[str] = set()
    for token in tokens:
        if not isinstance(token, str):
            raise MatrixCompilationError("query-token identities must be non-blank strings")
        normalized = normalise_query_tokens(token)
        if not normalized:
            raise MatrixCompilationError("query-token identities must be non-blank strings")
        canonical.update(normalized)
    if not canonical:
        raise MatrixCompilationError("the static matrix query-token vocabulary cannot be empty")
    return tuple(sorted(canonical, key=lambda token: token.encode(_UTF_8)))


def query_token_fingerprint(tokens: Iterable[str]) -> str:
    """Return the SHA-256 fingerprint of the exact query-token identities."""
    canonical = canonical_query_tokens(tokens)
    return sha256("\n".join(canonical).encode(_UTF_8)).hexdigest()


def compile_static_embedding_matrix(
    vocabulary: Iterable[str],
    provider: StaticEmbeddingProvider,
    *,
    query_tokens: Iterable[str],
    max_serialized_bytes: int = DEFAULT_MAX_SERIALIZED_BYTES,
) -> StaticEmbeddingMatrix:
    """Compile and validate a bounded matrix from a pinned provider.

    The provider receives canonical result terms and exact query-token
    identities and must return one observation for each item in both sets.
    Missing, duplicate, or foreign observations are hard failures; no row is
    silently dropped or replaced by a fallback vector.
    """
    if max_serialized_bytes <= 0 or max_serialized_bytes > DEFAULT_MAX_SERIALIZED_BYTES:
        raise MatrixCompilationError(f"max_serialized_bytes must be between 1 and {DEFAULT_MAX_SERIALIZED_BYTES}")
    terms = canonical_vocabulary(vocabulary)
    tokens = canonical_query_tokens(query_tokens)
    metadata = ModelMetadata.model_validate(provider.metadata)
    observations = tuple(EmbeddingObservation.model_validate(row) for row in provider.embed(terms))
    query_observations = tuple(QueryTokenObservation.model_validate(row) for row in provider.embed_query_tokens(tokens))
    expected = set(terms)
    by_term: dict[str, EmbeddingObservation] = {}
    for observation in observations:
        term = observation.term
        if term != _canonical_term(term):
            raise MatrixCompilationError(
                f"provider observation {term!r} does not exactly echo its canonical input term"
            )
        if term not in expected:
            raise MatrixCompilationError(f"provider returned an observation for unknown term {term!r}")
        if term in by_term:
            raise MatrixCompilationError(f"provider returned duplicate observations for {term!r}")
        by_term[term] = observation
    missing = tuple(term for term in terms if term not in by_term)
    if missing:
        raise MatrixCompilationError(f"provider returned no observation for {missing[0]!r}")

    expected_tokens = set(tokens)
    query_by_token: dict[str, QueryTokenObservation] = {}
    for observation in query_observations:
        token = observation.token
        if token not in expected_tokens:
            raise MatrixCompilationError(f"provider returned an observation for unknown query token {token!r}")
        if token in query_by_token:
            raise MatrixCompilationError(f"provider returned duplicate observations for query token {token!r}")
        query_by_token[token] = observation
    missing_tokens = tuple(token for token in tokens if token not in query_by_token)
    if missing_tokens:
        raise MatrixCompilationError(f"provider returned no observation for query token {missing_tokens[0]!r}")

    rows: list[QuantizedEmbeddingRow] = []
    inventory: list[TokenInventoryEntry] = []
    query_rows: list[QuantizedQueryTokenRow] = []
    for term in terms:
        observation = by_term[term]
        scale, values = _quantize_vector(observation.vector, dimension=metadata.dimension, term=term)
        rows.append(QuantizedEmbeddingRow(term=term, scale=scale, values=values))
        inventory.append(
            TokenInventoryEntry(
                term=term,
                token_ids=observation.token_ids,
                token_count=observation.token_count,
            )
        )
    for token in tokens:
        observation = query_by_token[token]
        scale, values = _quantize_vector(observation.vector, dimension=metadata.dimension, term=token)
        query_rows.append(
            QuantizedQueryTokenRow(
                token=token,
                model_token_ids=observation.model_token_ids,
                token_count=observation.token_count,
                scale=scale,
                values=values,
            )
        )

    core: dict[str, object] = {
        "schema_version": EMBEDDING_MATRIX_SCHEMA_VERSION,
        "model": metadata.model_dump(mode="json"),
        "vocabulary_sha256": vocabulary_fingerprint(terms),
        "vocabulary_count": len(terms),
        "query_token_sha256": query_token_fingerprint(tokens),
        "query_token_count": len(tokens),
        "dimension": metadata.dimension,
        "quantization_algorithm": INT8_QUANTIZATION_ALGORITHM,
        "row_order": ROW_ORDER,
        "token_inventory": tuple(entry.model_dump() for entry in inventory),
        "rows": tuple(row.model_dump() for row in rows),
        "query_token_rows": tuple(row.model_dump() for row in query_rows),
    }
    artifact_sha256 = sha256(canonical_json_bytes(core)).hexdigest()
    payload: dict[str, object] = {**core, "serialized_bytes": 0, "artifact_sha256": artifact_sha256}
    serialized_bytes = _fixed_point_serialized_size(payload)
    if serialized_bytes > max_serialized_bytes:
        raise MatrixCompilationError(
            f"serialized matrix is {serialized_bytes} bytes; maximum is {max_serialized_bytes}"
        )
    payload["serialized_bytes"] = serialized_bytes
    return StaticEmbeddingMatrix.model_validate(payload)


def load_static_embedding_matrix(path: Path) -> StaticEmbeddingMatrix:
    """Read and validate one committed matrix artifact."""
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise MatrixCompilationError(f"cannot read matrix artifact {path}: {exc}") from exc
    try:
        matrix = StaticEmbeddingMatrix.model_validate_json(payload)
    except ValueError as exc:
        raise MatrixCompilationError(f"invalid matrix artifact {path}: {exc}") from exc
    canonical = matrix.to_json_bytes()
    if payload != canonical:
        raise MatrixCompilationError(f"matrix artifact {path} is not in canonical JSON form")
    if len(payload) != matrix.serialized_bytes:
        raise MatrixCompilationError(f"matrix artifact {path} has an incorrect serialized byte count")
    return matrix


def write_static_embedding_matrix(matrix: StaticEmbeddingMatrix, destination: Path) -> None:
    """Write an already validated matrix without changing its bytes."""
    destination.write_bytes(matrix.to_json_bytes())


def _canonical_term(value: object) -> str:
    """Normalize a result term with the shared cross-runtime word contract."""
    if not isinstance(value, str):
        raise MatrixCompilationError("vocabulary terms must be strings")
    tokens = normalise_query_tokens(value)
    if not tokens:
        raise MatrixCompilationError("vocabulary terms cannot be blank")
    normalized = " ".join(tokens)
    if len(normalized) > 160:
        raise MatrixCompilationError("vocabulary terms cannot exceed 160 characters")
    return normalized


def normalise_query_tokens(value: object) -> tuple[str, ...]:
    """Apply the versioned compiler/browser normalization algorithm.

    NFKC, Unicode lowercase, and accent preservation are followed by Unicode
    letter/number-run extraction. Every other character is a separator, so
    repeated separators collapse into one token boundary. The implementation
    intentionally does not use Python ``casefold``: the contract names the
    lowercasing operation shared with JavaScript ``toLowerCase``.
    """
    if not isinstance(value, str):
        raise MatrixCompilationError("query text must be a string")
    normalized = unicodedata.normalize("NFKC", value).lower()
    if len(normalized) > 160:
        raise MatrixCompilationError("query text cannot exceed 160 characters")
    tokens: list[str] = []
    current: list[str] = []
    for character in normalized:
        category = unicodedata.category(character)
        if character.isalpha() or character.isnumeric() or (current and category.startswith("M")):
            current.append(character)
        elif current:
            tokens.append("".join(current))
            current.clear()
    if current:
        tokens.append("".join(current))
    return tuple(tokens)


def _quantize_vector(
    vector: tuple[float, ...],
    *,
    dimension: int,
    term: str,
) -> tuple[float, tuple[int, ...]]:
    """Normalize and quantize one vector with deterministic float32 arithmetic."""
    if len(vector) != dimension:
        raise MatrixCompilationError(f"embedding for {term!r} has dimension {len(vector)}, expected {dimension}")

    float32_values = tuple(_as_float32(value, term=term) for value in vector)
    sum_squares = 0.0
    for value in float32_values:
        square = _as_float32(value * value, term=term)
        sum_squares = _as_float32(sum_squares + square, term=term)
    if not math.isfinite(sum_squares) or sum_squares <= 0.0:
        raise MatrixCompilationError(f"embedding for {term!r} must be finite and non-zero")

    norm = _as_float32(math.sqrt(sum_squares), term=term)
    if norm <= 0.0:
        raise MatrixCompilationError(f"embedding for {term!r} underflowed during normalization")
    normalized = tuple(_as_float32(value / norm, term=term) for value in float32_values)
    peak = max(abs(value) for value in normalized)
    if not math.isfinite(peak) or peak <= 0.0:
        raise MatrixCompilationError(f"embedding for {term!r} has no non-zero component")
    scale = _as_float32(peak / 127.0, term=term)
    quantized = tuple(
        max(-127, min(127, _round_half_away_from_zero(_as_float32(value / scale, term=term)))) for value in normalized
    )
    return scale, quantized


def _as_float32(value: float, *, term: str) -> float:
    """Round one operation to IEEE-754 binary32 or fail loudly."""
    if not math.isfinite(value):
        raise MatrixCompilationError(f"embedding for {term!r} contains a non-finite value")
    try:
        rounded = struct.unpack("<f", struct.pack("<f", value))[0]
    except (OverflowError, struct.error) as exc:
        raise MatrixCompilationError(f"embedding for {term!r} cannot be represented as float32") from exc
    if not math.isfinite(rounded):
        raise MatrixCompilationError(f"embedding for {term!r} overflows float32")
    return rounded


def _round_half_away_from_zero(value: float) -> int:
    """Round a finite value deterministically, away from zero at ties."""
    return math.floor(value + 0.5) if value >= 0.0 else math.ceil(value - 0.5)


def _fixed_point_serialized_size(payload: dict[str, object]) -> int:
    """Find the stable byte count when the count itself is serialized."""
    size = 0
    for _ in range(8):
        payload["serialized_bytes"] = size
        candidate = len(canonical_json_bytes(payload))
        if candidate == size:
            return size
        size = candidate
    raise MatrixCompilationError("serialized byte count did not converge")
