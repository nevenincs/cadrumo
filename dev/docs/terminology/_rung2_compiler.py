"""Compose the validated build-time contracts for one Rung-2 compilation.

This module is intentionally an orchestration seam, not a third artifact
compiler.  The static-matrix module owns provider, model, normalization, and
matrix validation; the bridge module owns sweep, authoritative-record, bundle
validation, canonical serialization, and the explicit writer.  This seam
passes their outputs through in that order and never derives a search
destination.  Writing is available only through the explicit wrapper after the
complete bundle has been validated.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import cast

from ._rung2_bridge import Rung2SearchBundle, build_rung2_search_bundle, write_rung2_search_bundle
from ._rung2_provenance import Rung2InputProvenance
from ._static_matrix import (
    DEFAULT_MAX_SERIALIZED_BYTES,
    MatrixCompilationError,
    StaticEmbeddingProvider,
    canonical_query_tokens,
    canonical_vocabulary,
    compile_static_embedding_matrix,
)
from ._sweep import SweepResult
from ._unified_record import SearchRecord

__all__ = [
    "Rung2CompilationError",
    "compile_and_write_rung2_search_bundle",
    "compile_project_rung2_search_bundle",
    "compile_rung2_search_bundle",
]


class Rung2CompilationError(MatrixCompilationError):
    """Raised when the composed Rung-2 input or contract is invalid."""


def compile_rung2_search_bundle(
    *,
    vocabulary: object,
    query_tokens: object,
    provider: object,
    sweep: object,
    records: object,
    provenance: object,
    max_serialized_bytes: int = DEFAULT_MAX_SERIALIZED_BYTES,
) -> Rung2SearchBundle:
    """Compile a matrix and immediately link it to one authoritative sweep.

    ``vocabulary`` and ``query_tokens`` must already be the canonical tuples
    produced by the existing normalization helpers.  ``provider`` is the
    build-time model boundary; its validated metadata becomes
    ``bundle.matrix.model``.  ``bundle`` is the validated artifact boundary.
    The supplied record iterable is materialized once so it cannot be consumed
    before the bridge builds its manifest.

    All matrix, model-provenance, input-provenance, size, sweep, mapping, URL,
    manifest, and bundle invariants remain owned by the existing contracts.
    This function only rejects empty or structurally invalid seam inputs and
    composes those contracts in order.
    """
    validated_vocabulary = _require_canonical_vocabulary(vocabulary)
    validated_query_tokens = _require_canonical_query_tokens(query_tokens)
    validated_provider = _require_provider(provider)
    validated_sweep = _require_sweep(sweep)
    validated_provenance = _require_provenance(provenance)
    record_tuple = _materialize_records(records)

    try:
        matrix = compile_static_embedding_matrix(
            validated_vocabulary,
            validated_provider,
            query_tokens=validated_query_tokens,
            max_serialized_bytes=max_serialized_bytes,
        )
        return build_rung2_search_bundle(
            matrix,
            validated_sweep,
            record_tuple,
            provenance=validated_provenance,
            max_serialized_bytes=max_serialized_bytes,
        )
    except (TypeError, ValueError) as exc:
        raise Rung2CompilationError(f"Rung-2 compilation failed: {exc}") from exc


def compile_and_write_rung2_search_bundle(
    *,
    vocabulary: object,
    query_tokens: object,
    provider: object,
    sweep: object,
    records: object,
    destination: object,
    provenance: object,
    max_serialized_bytes: int = DEFAULT_MAX_SERIALIZED_BYTES,
) -> Rung2SearchBundle:
    """Compile one validated bundle and write its canonical bytes explicitly.

    The destination is a dev-side operator choice.  No parent directory is
    created and no artifact is written until :func:`compile_rung2_search_bundle`
    has accepted the provider, matrix, sweep, record manifest, bridge, input
    provenance, and shared byte bound.  The validated bundle is returned for
    an immediate caller-side measurement or manifest handoff.
    """
    if not isinstance(destination, Path):
        raise Rung2CompilationError("destination must be a pathlib.Path")
    bundle = compile_rung2_search_bundle(
        vocabulary=vocabulary,
        query_tokens=query_tokens,
        provider=provider,
        sweep=sweep,
        records=records,
        provenance=provenance,
        max_serialized_bytes=max_serialized_bytes,
    )
    try:
        write_rung2_search_bundle(bundle, destination)
    except OSError as exc:
        raise Rung2CompilationError(f"cannot write Rung-2 bundle {destination}: {exc}") from exc
    return bundle


def compile_project_rung2_search_bundle(
    *,
    provider: object,
    destination: object,
    repo_root: Path | None = None,
    max_serialized_bytes: int = DEFAULT_MAX_SERIALIZED_BYTES,
) -> Rung2SearchBundle:
    """Compile the project-authoritative sweep and Pagefind record bundle.

    This is the intended dev-box entry point.  It derives the closed vocabulary,
    browser query-token vocabulary, committed sweep, and authoritative record
    projection through :func:`build_rung2_compilation_inputs`, then delegates to
    the explicit validated writer.  It never runs a live RAG sweep or chooses a
    model; the caller must provide the already-pinned local provider.
    """
    from ._rung2_inputs import build_rung2_compilation_inputs

    inputs = build_rung2_compilation_inputs(repo_root)
    return compile_and_write_rung2_search_bundle(
        vocabulary=inputs.vocabulary,
        query_tokens=inputs.query_tokens,
        provider=provider,
        sweep=inputs.sweep,
        records=inputs.records,
        destination=destination,
        provenance=inputs.provenance,
        max_serialized_bytes=max_serialized_bytes,
    )


def _require_canonical_vocabulary(vocabulary: object) -> tuple[str, ...]:
    """Reject a missing or non-canonical closed result vocabulary."""
    if not isinstance(vocabulary, tuple) or not vocabulary:
        raise Rung2CompilationError("vocabulary must be a non-empty canonical tuple")
    raw_terms = cast(tuple[object, ...], vocabulary)
    terms = tuple(term for term in raw_terms if isinstance(term, str))
    if len(terms) != len(raw_terms):
        raise Rung2CompilationError("invalid vocabulary: terms must be strings")
    try:
        canonical = canonical_vocabulary(terms)
    except MatrixCompilationError as exc:
        raise Rung2CompilationError(f"invalid vocabulary: {exc}") from exc
    if canonical != terms:
        raise Rung2CompilationError("vocabulary must be canonical, unique, and UTF-8 ordered")
    return canonical


def _require_canonical_query_tokens(query_tokens: object) -> tuple[str, ...]:
    """Reject a missing or non-canonical browser query-token vocabulary."""
    if not isinstance(query_tokens, tuple) or not query_tokens:
        raise Rung2CompilationError("query_tokens must be a non-empty canonical tuple")
    raw_tokens = cast(tuple[object, ...], query_tokens)
    tokens = tuple(token for token in raw_tokens if isinstance(token, str))
    if len(tokens) != len(raw_tokens):
        raise Rung2CompilationError("invalid query_tokens: query-token identities must be strings")
    try:
        canonical = canonical_query_tokens(tokens)
    except MatrixCompilationError as exc:
        raise Rung2CompilationError(f"invalid query_tokens: {exc}") from exc
    if canonical != tokens:
        raise Rung2CompilationError("query_tokens must be canonical, unique, and UTF-8 ordered")
    return canonical


def _require_provider(provider: object) -> StaticEmbeddingProvider:
    """Fail clearly when the model provider cannot satisfy its protocol."""
    if provider is None or not hasattr(provider, "metadata"):
        raise Rung2CompilationError("provider must expose model metadata")
    if not callable(getattr(provider, "embed", None)):
        raise Rung2CompilationError("provider must expose callable embed(terms)")
    if not callable(getattr(provider, "embed_query_tokens", None)):
        raise Rung2CompilationError("provider must expose callable embed_query_tokens(tokens)")
    return cast(StaticEmbeddingProvider, provider)


def _require_sweep(sweep: object) -> SweepResult:
    """Reject an absent or empty sweep before invoking the bridge."""
    if not isinstance(sweep, SweepResult):
        raise Rung2CompilationError("sweep must be a SweepResult")
    if not sweep.mappings:
        raise Rung2CompilationError("sweep mappings cannot be empty")
    return sweep


def _require_provenance(provenance: object) -> Rung2InputProvenance:
    """Reject an unvalidated provenance value before bundle construction."""
    if not isinstance(provenance, Rung2InputProvenance):
        raise Rung2CompilationError("provenance must be a validated Rung2InputProvenance")
    return provenance


def _materialize_records(records: object) -> tuple[SearchRecord, ...]:
    """Materialize and type-check the authoritative record iterable once."""
    try:
        iterator = iter(cast(Iterable[object], records))
        materialized: tuple[object, ...] = tuple(iterator)
    except TypeError as exc:
        raise Rung2CompilationError("records must be an iterable of SearchRecord") from exc
    if not materialized:
        raise Rung2CompilationError("authoritative SearchRecord records cannot be empty")
    validated = tuple(record for record in materialized if isinstance(record, SearchRecord))
    if len(validated) != len(materialized):
        raise Rung2CompilationError("records must contain only authoritative SearchRecord instances")
    return validated
