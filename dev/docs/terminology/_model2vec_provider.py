"""Build-time adapter for the pinned local Model2Vec/Potion model.

The shipped search surface has no embedding dependency.  This module belongs to
the dev-side matrix compiler and imports ``model2vec`` lazily only when an
operator explicitly constructs a provider from an already-present local model
directory.  A repository identifier, URL, missing path, unknown token, special
token, or truncated sequence is refused rather than turned into an implicit
download or a lossy row.

The caller supplies the complete, hash-stamped :class:`ModelMetadata` and the
reviewed local raw-byte manifests that substantiate its content hashes.  The
manifests are verified before the optional provider import or model loader is
reached; no content hash is accepted as caller-only attestation.
"""

from __future__ import annotations

import importlib
import math
import struct
from collections.abc import Sequence
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any, Final, cast

from ._content_manifest import RawByteManifest, RawByteManifestError, verify_raw_byte_manifest
from ._static_matrix import (
    EmbeddingObservation,
    MatrixCompilationError,
    ModelMetadata,
    QueryTokenObservation,
    StaticEmbeddingProvider,
    canonical_query_tokens,
    canonical_vocabulary,
)

__all__ = [
    "POTION_MODEL_DIMENSION",
    "POTION_MODEL_LICENSE",
    "POTION_MODEL_REPOSITORY",
    "POTION_MODEL_REVISION",
    "PotionModel2VecProvider",
]

POTION_MODEL_REPOSITORY: Final[str] = "minishlab/potion-multilingual-128M"
POTION_MODEL_REVISION: Final[str] = "e7421cd79c75fc506b88bb75723ae0a234994720"
POTION_MODEL_LICENSE: Final[str] = "MIT"
POTION_MODEL_DIMENSION: Final[int] = 256
_MODEL2VEC_PACKAGE: Final[str] = "model2vec"
_PROVIDER_MANIFEST_ROLE: Final[str] = "provider-source"
_MODEL_MANIFEST_ROLE: Final[str] = "model-snapshot"
_TOKENIZER_VOCABULARY_ROLE: Final[str] = "tokenizer-vocabulary"
_TOKENIZER_CONFIG_ROLE: Final[str] = "tokenizer-configuration"


class PotionModel2VecProvider(StaticEmbeddingProvider):
    """Adapt one local, pinned Model2Vec model to the matrix provider contract.

    Construction is intentionally explicit and fail-closed.  The model path
    must already exist as a directory, and the metadata must name the exact
    model revision/licence/dimension selected by the ADR.  The provider package
    version is checked against the installed environment.  Every provider,
    model, and tokenizer role must have explicit local manifest evidence before
    the provider package is imported.
    """

    def __init__(
        self,
        *,
        model_path: Path,
        metadata: ModelMetadata,
        provider_root: Path,
        provider_manifest: RawByteManifest,
        model_manifest: RawByteManifest,
        tokenizer_vocabulary_manifest: RawByteManifest,
        tokenizer_config_manifest: RawByteManifest,
    ) -> None:
        self._model_path = _require_local_model_path(model_path)
        self._metadata = ModelMetadata.model_validate(metadata)
        _validate_potion_metadata(self._metadata)
        _verify_content_manifests(
            metadata=self._metadata,
            provider_root=provider_root,
            provider_manifest=provider_manifest,
            model_root=self._model_path,
            model_manifest=model_manifest,
            tokenizer_vocabulary_manifest=tokenizer_vocabulary_manifest,
            tokenizer_config_manifest=tokenizer_config_manifest,
        )

        _require_installed_package_version(self._metadata)
        model2vec = _import_model2vec()
        static_model = getattr(model2vec, "StaticModel", None)
        if static_model is None:
            raise MatrixCompilationError("model2vec.StaticModel is unavailable")
        try:
            # The path check above is what makes this call local-only.  The
            # explicit flag also prevents a cache miss from becoming a network
            # download if a future Model2Vec loader changes its default.
            self._model = static_model.from_pretrained(self._model_path, force_download=False)
        except Exception as exc:  # model loader errors are provider-boundary failures
            raise MatrixCompilationError(f"cannot load local Model2Vec model {self._model_path}: {exc}") from exc

        actual_dimension = getattr(self._model, "dim", None)
        if actual_dimension != self._metadata.dimension:
            raise MatrixCompilationError(
                f"local Model2Vec dimension {actual_dimension!r} does not match "
                f"the pinned dimension {self._metadata.dimension}"
            )
        tokenizer = getattr(self._model, "tokenizer", None)
        if tokenizer is None or not callable(getattr(tokenizer, "encode", None)):
            raise MatrixCompilationError("local Model2Vec model does not expose its tokenizer")
        if not callable(getattr(self._model, "encode_as_sequence", None)):
            raise MatrixCompilationError("local Model2Vec model does not expose encode_as_sequence")

    @property
    def metadata(self) -> ModelMetadata:
        """Return the caller-supplied immutable provenance record."""
        return self._metadata

    def embed(self, terms: tuple[str, ...]) -> tuple[EmbeddingObservation, ...]:
        """Embed canonical result terms with complete tokenizer provenance."""
        requested = tuple(terms)
        if requested != canonical_vocabulary(requested):
            raise MatrixCompilationError("provider terms must already be canonical and UTF-8 ordered")
        return tuple(
            EmbeddingObservation(
                term=term,
                token_ids=token_ids,
                token_count=len(token_ids),
                vector=vector,
            )
            for term in requested
            for token_ids, vector in (self._embed_text(term),)
        )

    def embed_query_tokens(self, tokens: tuple[str, ...]) -> tuple[QueryTokenObservation, ...]:
        """Embed canonical browser words without special tokens or truncation."""
        requested = tuple(tokens)
        if requested != canonical_query_tokens(requested):
            raise MatrixCompilationError("provider query tokens must already be canonical and UTF-8 ordered")
        observations: list[QueryTokenObservation] = []
        for token in requested:
            if len(token.split()) != 1:
                raise MatrixCompilationError(f"query-token provider input is not one word: {token!r}")
            token_ids, vector = self._embed_text(token)
            observations.append(
                QueryTokenObservation(
                    token=token,
                    model_token_ids=token_ids,
                    token_count=len(token_ids),
                    vector=vector,
                )
            )
        return tuple(observations)

    def _embed_text(self, text: str) -> tuple[tuple[int, ...], tuple[float, ...]]:
        """Return an exact id tuple and a float32 mean of its token vectors."""
        tokenizer = self._model.tokenizer
        try:
            encoding = tokenizer.encode(text, add_special_tokens=False)
        except Exception as exc:  # tokenizer errors are provider-boundary failures
            raise MatrixCompilationError(f"tokenization failed for {text!r}: {exc}") from exc
        raw_ids = getattr(encoding, "ids", None)
        if not isinstance(raw_ids, (list, tuple)) or not raw_ids:
            raise MatrixCompilationError(f"provider produced no model tokens for {text!r}")
        try:
            token_ids = tuple(int(token_id) for token_id in cast(Sequence[Any], raw_ids))
        except (TypeError, ValueError) as exc:
            raise MatrixCompilationError(f"provider returned invalid token ids for {text!r}") from exc
        if any(token_id < 0 for token_id in token_ids):
            raise MatrixCompilationError(f"provider returned a negative token id for {text!r}")

        unknown_id = getattr(self._model, "unk_token_id", None)
        if unknown_id is not None and int(unknown_id) in token_ids:
            raise MatrixCompilationError(f"provider encountered an unknown token in {text!r}")

        try:
            sequences = self._model.encode_as_sequence(
                [text],
                max_length=None,
                show_progress_bar=False,
                use_multiprocessing=False,
            )
        except Exception as exc:  # encoding errors are provider-boundary failures
            raise MatrixCompilationError(f"embedding failed for {text!r}: {exc}") from exc
        if not isinstance(sequences, Sequence):
            raise MatrixCompilationError(f"provider returned an invalid token sequence for {text!r}")
        typed_sequences = cast(Sequence[Sequence[Any]], sequences)
        if len(typed_sequences) != 1:
            raise MatrixCompilationError(f"provider returned an invalid token sequence for {text!r}")
        rows = typed_sequences[0]
        try:
            row_count = len(rows)
        except TypeError as exc:
            raise MatrixCompilationError(f"provider returned an unreadable token sequence for {text!r}") from exc
        if row_count != len(token_ids):
            raise MatrixCompilationError(
                f"provider token/vector count mismatch for {text!r}: "
                f"{row_count} vectors for {len(token_ids)} token ids"
            )
        if row_count == 0:
            raise MatrixCompilationError(f"provider returned an empty token sequence for {text!r}")

        vectors: list[tuple[float, ...]] = []
        for row in rows:
            try:
                values = tuple(_as_float32(value, text=text) for value in cast(Sequence[Any], row))
            except (TypeError, ValueError) as exc:
                raise MatrixCompilationError(f"provider returned an invalid vector for {text!r}") from exc
            if len(values) != self._metadata.dimension:
                raise MatrixCompilationError(
                    f"provider vector for {text!r} has dimension {len(values)}, "
                    f"expected {self._metadata.dimension}"
                )
            vectors.append(values)

        pooled: list[float] = []
        for column in range(self._metadata.dimension):
            total = 0.0
            for row in vectors:
                total = _as_float32(total + row[column], text=text)
            pooled.append(_as_float32(total / len(vectors), text=text))
        return token_ids, tuple(pooled)


def _verify_content_manifests(
    *,
    metadata: ModelMetadata,
    provider_root: Path,
    provider_manifest: RawByteManifest,
    model_root: Path,
    model_manifest: RawByteManifest,
    tokenizer_vocabulary_manifest: RawByteManifest,
    tokenizer_config_manifest: RawByteManifest,
) -> None:
    """Verify all local content roots before importing the optional provider."""
    _verify_manifest(
        root=provider_root,
        manifest=provider_manifest,
        role=_PROVIDER_MANIFEST_ROLE,
        repository=metadata.provider.package,
        expected_sha256=metadata.provider.source_sha256,
    )
    _verify_manifest(
        root=model_root,
        manifest=model_manifest,
        role=_MODEL_MANIFEST_ROLE,
        repository=metadata.repository,
        revision=metadata.revision,
        expected_sha256=metadata.model_snapshot_sha256,
    )
    _verify_manifest(
        root=model_root,
        manifest=tokenizer_vocabulary_manifest,
        role=_TOKENIZER_VOCABULARY_ROLE,
        repository=metadata.tokenizer.repository,
        revision=metadata.tokenizer.revision,
        expected_sha256=metadata.tokenizer.vocabulary_sha256,
        reject_unexpected=False,
    )
    _verify_manifest(
        root=model_root,
        manifest=tokenizer_config_manifest,
        role=_TOKENIZER_CONFIG_ROLE,
        repository=metadata.tokenizer.repository,
        revision=metadata.tokenizer.revision,
        expected_sha256=metadata.tokenizer.config_sha256,
        reject_unexpected=False,
    )
    tokenizer_vocabulary_paths = {entry.relative_path for entry in tokenizer_vocabulary_manifest.entries}
    tokenizer_config_paths = {entry.relative_path for entry in tokenizer_config_manifest.entries}
    overlapping_paths = tokenizer_vocabulary_paths & tokenizer_config_paths
    if overlapping_paths:
        raise MatrixCompilationError(
            "tokenizer-vocabulary and tokenizer-configuration manifest roles overlap on "
            f"paths: {sorted(overlapping_paths)!r}"
        )
    model_entries = {
        entry.relative_path: (entry.byte_length, entry.sha256) for entry in model_manifest.entries
    }
    for role_manifest in (tokenizer_vocabulary_manifest, tokenizer_config_manifest):
        for entry in role_manifest.entries:
            if model_entries.get(entry.relative_path) != (entry.byte_length, entry.sha256):
                raise MatrixCompilationError(
                    f"{role_manifest.role} entry {entry.relative_path!r} is not covered by the model snapshot"
                )


def _verify_manifest(
    *,
    root: Path,
    manifest: RawByteManifest,
    role: str,
    expected_sha256: str,
    repository: str | None = None,
    revision: str | None = None,
    reject_unexpected: bool = True,
) -> None:
    """Check one role, its metadata root, and its local bytes."""
    if manifest.role != role:
        raise MatrixCompilationError(f"manifest role {manifest.role!r} does not satisfy {role!r}")
    if repository is not None and manifest.repository != repository:
        raise MatrixCompilationError(
            f"{role} manifest repository {manifest.repository!r} does not match {repository!r}"
        )
    if revision is not None and manifest.revision != revision:
        raise MatrixCompilationError(f"{role} manifest revision does not match the pinned revision")
    if manifest.manifest_sha256 != expected_sha256:
        raise MatrixCompilationError(f"{role} manifest root does not match the metadata provenance")
    try:
        verify_raw_byte_manifest(root, manifest, reject_unexpected=reject_unexpected)
    except (RawByteManifestError, ValueError) as exc:
        raise MatrixCompilationError(f"{role} manifest verification failed: {exc}") from exc


def _require_local_model_path(model_path: object) -> Path:
    """Reject remote identifiers and missing model directories before loading."""
    if not isinstance(model_path, Path):
        raise MatrixCompilationError("Model2Vec model_path must be a pathlib.Path")
    if "://" in str(model_path):
        raise MatrixCompilationError("Model2Vec model_path must be local, not a URL or repository identifier")
    path = model_path.expanduser()
    if not path.is_dir():
        raise MatrixCompilationError(f"Model2Vec local model directory does not exist: {path}")
    return path


def _import_model2vec() -> Any:
    """Import the optional provider only after a caller requests it."""
    try:
        return importlib.import_module(_MODEL2VEC_PACKAGE)
    except ImportError as exc:
        raise MatrixCompilationError(
            "model2vec is required only for the dev-side provider and is not installed"
        ) from exc


def _require_installed_package_version(metadata: ModelMetadata) -> None:
    """Require the installed provider version to equal its pinned provenance."""
    if metadata.provider.package != _MODEL2VEC_PACKAGE:
        raise MatrixCompilationError(
            f"Potion provider metadata must name {_MODEL2VEC_PACKAGE!r}, "
            f"got {metadata.provider.package!r}"
        )
    try:
        installed = importlib_metadata.version(_MODEL2VEC_PACKAGE)
    except importlib_metadata.PackageNotFoundError as exc:
        raise MatrixCompilationError("model2vec package metadata is unavailable") from exc
    if installed != metadata.provider.version:
        raise MatrixCompilationError(
            f"installed model2vec version {installed!r} does not match pinned {metadata.provider.version!r}"
        )


def _validate_potion_metadata(metadata: ModelMetadata) -> None:
    """Refuse a provider configured for a different model or licence."""
    if metadata.repository != POTION_MODEL_REPOSITORY:
        raise MatrixCompilationError(
            f"Potion provider requires {POTION_MODEL_REPOSITORY!r}, got {metadata.repository!r}"
        )
    if metadata.revision != POTION_MODEL_REVISION:
        raise MatrixCompilationError(
            f"Potion provider requires immutable revision {POTION_MODEL_REVISION}, got {metadata.revision}"
        )
    if metadata.spdx_license != POTION_MODEL_LICENSE:
        raise MatrixCompilationError("Potion provider requires an MIT model licence")
    if metadata.dimension != POTION_MODEL_DIMENSION:
        raise MatrixCompilationError(
            f"Potion provider requires dimension {POTION_MODEL_DIMENSION}, got {metadata.dimension}"
        )


def _as_float32(value: object, *, text: str) -> float:
    """Round one provider component to binary32 and reject non-finite values."""
    try:
        numeric = float(cast(Any, value))
        rounded = struct.unpack("<f", struct.pack("<f", numeric))[0]
    except (OverflowError, TypeError, ValueError, struct.error) as exc:
        raise MatrixCompilationError(f"provider vector for {text!r} is not float32-representable") from exc
    if not math.isfinite(rounded):
        raise MatrixCompilationError(f"provider vector for {text!r} contains a non-finite value")
    return rounded
