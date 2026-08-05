"""Compose the validated build-time contracts for one Rung-2 compilation.

This module is intentionally an orchestration seam, not a third artifact
compiler.  The static-matrix module owns provider, model, normalization, and
matrix validation; the bridge module owns sweep, authoritative-record, and
bundle validation.  This seam passes their outputs through in that order and
never writes an artifact or derives a search destination.
"""

from __future__ import annotations

from collections.abc import Iterable

from ._rung2_bridge import Rung2SearchBundle, build_rung2_search_bundle
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

__all__ = ["Rung2CompilationError", "compile_rung2_search_bundle"]


class Rung2CompilationError(MatrixCompilationError):
    """Raised when the composed Rung-2 input or contract is invalid."""


def compile_rung2_search_bundle(
    *,
    vocabulary: tuple[str, ...],
    query_tokens: tuple[str, ...],
    provider: StaticEmbeddingProvider,
    sweep: SweepResult,
    records: Iterable[SearchRecord],
    max_serialized_bytes: int = DEFAULT_MAX_SERIALIZED_BYTES,
) -> Rung2SearchBundle:
    """Compile a matrix and immediately link it to one authoritative sweep.

    ``vocabulary`` and ``query_tokens`` must already be the canonical tuples
    produced by the existing normalization helpers.  ``provider`` is the
    build-time model boundary; its validated metadata becomes
    ``bundle.matrix.model``.  ``bundle`` is the validated artifact boundary.
    The supplied record iterable is materialized once so it cannot be consumed
    before the bridge builds its manifest.

    All matrix, model-provenance, size, sweep, mapping, URL, manifest, and
    bundle invariants remain owned by the existing contracts.  This function
    only rejects empty or structurally invalid seam inputs and composes those
    contracts in order.
    """
    _require_canonical_vocabulary(vocabulary)
    _require_canonical_query_tokens(query_tokens)
    _require_provider(provider)
    _require_sweep(sweep)
    record_tuple = _materialize_records(records)

    try:
        matrix = compile_static_embedding_matrix(
            vocabulary,
            provider,
            query_tokens=query_tokens,
            max_serialized_bytes=max_serialized_bytes,
        )
        return build_rung2_search_bundle(
            matrix,
            sweep,
            record_tuple,
            max_serialized_bytes=max_serialized_bytes,
        )
    except (TypeError, ValueError) as exc:
        raise Rung2CompilationError(f"Rung-2 compilation failed: {exc}") from exc


def _require_canonical_vocabulary(vocabulary: tuple[str, ...]) -> None:
    """Reject a missing or non-canonical closed result vocabulary."""
    if not isinstance(vocabulary, tuple) or not vocabulary:
        raise Rung2CompilationError("vocabulary must be a non-empty canonical tuple")
    try:
        canonical = canonical_vocabulary(vocabulary)
    except MatrixCompilationError as exc:
        raise Rung2CompilationError(f"invalid vocabulary: {exc}") from exc
    if canonical != vocabulary:
        raise Rung2CompilationError("vocabulary must be canonical, unique, and UTF-8 ordered")


def _require_canonical_query_tokens(query_tokens: tuple[str, ...]) -> None:
    """Reject a missing or non-canonical browser query-token vocabulary."""
    if not isinstance(query_tokens, tuple) or not query_tokens:
        raise Rung2CompilationError("query_tokens must be a non-empty canonical tuple")
    try:
        canonical = canonical_query_tokens(query_tokens)
    except MatrixCompilationError as exc:
        raise Rung2CompilationError(f"invalid query_tokens: {exc}") from exc
    if canonical != query_tokens:
        raise Rung2CompilationError("query_tokens must be canonical, unique, and UTF-8 ordered")


def _require_provider(provider: StaticEmbeddingProvider) -> None:
    """Fail clearly when the model provider cannot satisfy its protocol."""
    if provider is None or not hasattr(provider, "metadata"):
        raise Rung2CompilationError("provider must expose model metadata")
    if not callable(getattr(provider, "embed", None)):
        raise Rung2CompilationError("provider must expose callable embed(terms)")
    if not callable(getattr(provider, "embed_query_tokens", None)):
        raise Rung2CompilationError("provider must expose callable embed_query_tokens(tokens)")


def _require_sweep(sweep: SweepResult) -> None:
    """Reject an absent or empty sweep before invoking the bridge."""
    if not isinstance(sweep, SweepResult):
        raise Rung2CompilationError("sweep must be a SweepResult")
    if not sweep.mappings:
        raise Rung2CompilationError("sweep mappings cannot be empty")


def _materialize_records(records: Iterable[SearchRecord]) -> tuple[SearchRecord, ...]:
    """Materialize and type-check the authoritative record iterable once."""
    try:
        materialized = tuple(records)
    except TypeError as exc:
        raise Rung2CompilationError("records must be an iterable of SearchRecord") from exc
    if not materialized:
        raise Rung2CompilationError("authoritative SearchRecord records cannot be empty")
    if any(not isinstance(record, SearchRecord) for record in materialized):
        raise Rung2CompilationError("records must contain only authoritative SearchRecord instances")
    return materialized
