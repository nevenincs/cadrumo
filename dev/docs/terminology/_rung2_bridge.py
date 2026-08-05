"""Typed, bounded bridge from Rung-2 terms to authoritative search records.

The matrix contains semantic vectors, but a vector row is not a user-facing
answer.  This module closes that gap without creating a second destination
authority:

* every bridge target is an ordered ``record_id`` / relevance-weight pair;
* every id is validated against a compact manifest built from the authoritative
  :class:`~dev.docs.terminology._unified_record.SearchRecord` projection;
* the bridge hashes the matrix vocabulary and manifest it depends on; and
* input provenance and the complete matrix, bridge, and manifest are measured
  together under the one 3,000,000-byte envelope.

No URL is reconstructed from an opaque id.  The only target URL retained for a
semantic result comes from the same ``SearchRecord`` object that Pagefind
injection consumes.  This module defines source contracts and loaders only;
it does not generate an artifact, invoke a provider, or enable a browser tier.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from hashlib import sha256
from pathlib import Path
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from ._rung2_provenance import Rung2InputProvenance
from ._search_record import ResultDisplayClass, SearchRecordKind
from ._static_matrix import (
    DEFAULT_MAX_SERIALIZED_BYTES,
    MatrixCompilationError,
    StaticEmbeddingMatrix,
    canonical_vocabulary,
)
from ._sweep import SweepResult
from ._unified_record import SearchRecord, derive_display_class

__all__ = [
    "BRIDGE_SCHEMA_VERSION",
    "BUNDLE_SCHEMA_VERSION",
    "BridgeCompilationError",
    "RecordManifest",
    "RecordManifestEntry",
    "Rung2SearchBundle",
    "SemanticBridge",
    "SemanticBridgeEntry",
    "SemanticBridgeTarget",
    "build_record_manifest",
    "build_rung2_search_bundle",
    "load_rung2_search_bundle",
    "write_rung2_search_bundle",
]

_UTF_8: Final[str] = "utf-8"
BRIDGE_SCHEMA_VERSION: Final[int] = 1
BUNDLE_SCHEMA_VERSION: Final[int] = 2
_ROW_ORDER: Final[str] = "canonical-utf8-byte-order-v1"
_SHA256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
_RecordId = Annotated[str, StringConstraints(min_length=1, max_length=320)]
_Target = Annotated[str, StringConstraints(min_length=1, max_length=512)]


class BridgeCompilationError(MatrixCompilationError):
    """Raised when a semantic bridge cannot be proven self-consistent."""


class SemanticBridgeTarget(BaseModel):
    """One ordered semantic target, carrying no independently derived URL."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    record_id: _RecordId
    ranking_weight: float = Field(ge=0.0, le=1.0)

    @field_validator("ranking_weight")
    @classmethod
    def _require_finite_weight(cls, value: float) -> float:
        """Reject non-finite relevance weights before they enter the bridge."""
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError("semantic ranking weights must be finite")
        return value


class RecordManifestEntry(BaseModel):
    """Compact browser hydration data projected from one ``SearchRecord``."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    record_id: _RecordId
    kind: SearchRecordKind
    display_class: ResultDisplayClass
    title: Annotated[str, StringConstraints(min_length=1, max_length=320)]
    target: _Target
    ranking_weight: float = Field(ge=0.0, le=1.0)

    @field_validator("ranking_weight")
    @classmethod
    def _require_finite_weight(cls, value: float) -> float:
        """Reject a manifest row that cannot be ranked deterministically."""
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError("manifest ranking weights must be finite")
        return value


class RecordManifest(BaseModel):
    """Hash-addressed compact manifest for stable semantic-result hydration."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    schema_version: Literal[1]
    row_order: Literal["canonical-utf8-byte-order-v1"]
    record_count: int = Field(ge=1)
    records: tuple[RecordManifestEntry, ...] = Field(min_length=1)
    records_sha256: _SHA256
    serialized_bytes: int = Field(gt=0, le=DEFAULT_MAX_SERIALIZED_BYTES)

    @model_validator(mode="after")
    def _enforce_manifest_invariants(self) -> RecordManifest:
        """Validate identity order, count, content hash, and byte stamp."""
        record_ids = tuple(entry.record_id for entry in self.records)
        expected_order = tuple(sorted(record_ids, key=lambda record_id: record_id.encode(_UTF_8)))
        if self.record_count != len(self.records):
            raise ValueError("record_count must match records")
        if record_ids != expected_order or len(record_ids) != len(set(record_ids)):
            raise ValueError("manifest records must be unique and UTF-8 byte ordered")
        if self.records_sha256 != _hash_json([entry.model_dump(mode="json") for entry in self.records]):
            raise ValueError("records_sha256 does not match the canonical manifest rows")
        if self.serialized_bytes != len(self.to_json_bytes()):
            raise ValueError("manifest serialized_bytes does not match canonical bytes")
        return self

    def to_json_bytes(self) -> bytes:
        """Return the canonical newline-terminated manifest bytes."""
        return _canonical_json_bytes(self.model_dump(mode="json"))


class SemanticBridgeEntry(BaseModel):
    """One canonical semantic term and its ordered target list."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    term: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    targets: tuple[SemanticBridgeTarget, ...] = Field(min_length=1)
    targets_sha256: _SHA256

    @model_validator(mode="after")
    def _enforce_entry_invariants(self) -> SemanticBridgeEntry:
        """Validate canonical term identity, target order, and uniqueness."""
        if canonical_vocabulary((self.term,)) != (self.term,):
            raise ValueError("bridge terms must use the canonical vocabulary form")
        record_ids = tuple(target.record_id for target in self.targets)
        if len(record_ids) != len(set(record_ids)):
            raise ValueError("a semantic bridge entry cannot repeat a record id")
        expected_order = tuple(
            sorted(
                self.targets,
                key=lambda target: (-target.ranking_weight, target.record_id.encode(_UTF_8)),
            ),
        )
        if self.targets != expected_order:
            raise ValueError("semantic bridge targets must be deterministically ordered")
        expected_hash = _hash_json([target.model_dump(mode="json") for target in self.targets])
        if self.targets_sha256 != expected_hash:
            raise ValueError("targets_sha256 does not match the ordered target list")
        return self


class SemanticBridge(BaseModel):
    """Hash-linked term-to-record bridge for one matrix vocabulary."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    schema_version: Literal[1]
    row_order: Literal["canonical-utf8-byte-order-v1"]
    matrix_vocabulary_sha256: _SHA256
    record_manifest_sha256: _SHA256
    term_count: int = Field(ge=1)
    entries: tuple[SemanticBridgeEntry, ...] = Field(min_length=1)
    artifact_sha256: _SHA256
    serialized_bytes: int = Field(gt=0, le=DEFAULT_MAX_SERIALIZED_BYTES)

    @model_validator(mode="after")
    def _enforce_bridge_invariants(self) -> SemanticBridge:
        """Validate term order and the bridge's self-attested bytes."""
        terms = tuple(entry.term for entry in self.entries)
        expected_order = tuple(sorted(terms, key=lambda term: term.encode(_UTF_8)))
        if self.term_count != len(self.entries):
            raise ValueError("term_count must match bridge entries")
        if terms != expected_order or len(terms) != len(set(terms)):
            raise ValueError("bridge terms must be unique and UTF-8 byte ordered")
        unsigned = self.model_dump(mode="json", exclude={"artifact_sha256", "serialized_bytes"})
        if self.artifact_sha256 != _hash_json(unsigned):
            raise ValueError("bridge artifact_sha256 does not match the unsigned bridge")
        if self.serialized_bytes != len(self.to_json_bytes()):
            raise ValueError("bridge serialized_bytes does not match canonical bytes")
        return self

    def to_json_bytes(self) -> bytes:
        """Return the canonical newline-terminated bridge bytes."""
        return _canonical_json_bytes(self.model_dump(mode="json"))


class Rung2SearchBundle(BaseModel):
    """The complete matrix/bridge/manifest/provenance envelope with one byte bound."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    schema_version: Literal[2]
    matrix: StaticEmbeddingMatrix
    bridge: SemanticBridge
    record_manifest: RecordManifest
    input_provenance: Rung2InputProvenance
    serialized_bytes: int = Field(gt=0, le=DEFAULT_MAX_SERIALIZED_BYTES)
    artifact_sha256: _SHA256

    @model_validator(mode="after")
    def _enforce_bundle_invariants(self) -> Rung2SearchBundle:
        """Link every semantic row to a manifest record under one bound."""
        if self.bridge.matrix_vocabulary_sha256 != self.matrix.vocabulary_sha256:
            raise ValueError("bridge vocabulary hash does not match the matrix")
        if self.bridge.record_manifest_sha256 != self.record_manifest.records_sha256:
            raise ValueError("bridge manifest hash does not match the record manifest")
        if self.input_provenance.vocabulary_sha256 != self.matrix.vocabulary_sha256:
            raise ValueError("input provenance vocabulary hash does not match the matrix")
        if self.input_provenance.query_token_sha256 != self.matrix.query_token_sha256:
            raise ValueError("input provenance query-token hash does not match the matrix")
        matrix_terms = tuple(row.term for row in self.matrix.rows)
        bridge_terms = tuple(entry.term for entry in self.bridge.entries)
        if bridge_terms != matrix_terms:
            raise ValueError("bridge entries must cover the matrix vocabulary in row order")
        manifest_ids = {entry.record_id for entry in self.record_manifest.records}
        for entry in self.bridge.entries:
            for target in entry.targets:
                if target.record_id not in manifest_ids:
                    raise ValueError(f"bridge target {target.record_id!r} is absent from the record manifest")
        unsigned = self.model_dump(mode="json", exclude={"artifact_sha256", "serialized_bytes"})
        if self.artifact_sha256 != _hash_json(unsigned):
            raise ValueError("bundle artifact_sha256 does not match the unsigned payload")
        if self.serialized_bytes != len(self.to_json_bytes()):
            raise ValueError("bundle serialized_bytes does not match canonical bytes")
        return self

    def to_json_bytes(self) -> bytes:
        """Return the canonical complete payload bytes."""
        return _canonical_json_bytes(self.model_dump(mode="json"))


def build_record_manifest(records: Iterable[SearchRecord]) -> RecordManifest:
    """Project authoritative ``SearchRecord`` objects into a compact manifest.

    Duplicate ids are accepted only when the complete projected records are
    identical.  The target is copied from ``SearchRecord.target``; no URL is
    reconstructed from the opaque id.
    """
    by_id: dict[str, SearchRecord] = {}
    for candidate in records:
        record = SearchRecord.model_validate(candidate)
        prior = by_id.get(record.id)
        if prior is not None and prior != record:
            raise BridgeCompilationError(f"conflicting SearchRecord projections for {record.id!r}")
        by_id[record.id] = record
    if not by_id:
        raise BridgeCompilationError("the Rung-2 record manifest cannot be empty")

    entries = tuple(
        RecordManifestEntry(
            record_id=record.id,
            kind=record.kind,
            display_class=derive_display_class(record),
            title=record.title,
            target=record.target,
            ranking_weight=record.ranking_weight,
        )
        for record in sorted(by_id.values(), key=lambda item: item.id.encode(_UTF_8))
    )
    core: dict[str, object] = {
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "row_order": _ROW_ORDER,
        "record_count": len(entries),
        "records": [entry.model_dump(mode="json") for entry in entries],
        "records_sha256": _hash_json([entry.model_dump(mode="json") for entry in entries]),
        "serialized_bytes": 0,
    }
    core["serialized_bytes"] = _fixed_point_serialized_size(core)
    return RecordManifest.model_validate(core)


def build_rung2_search_bundle(
    matrix: StaticEmbeddingMatrix,
    sweep: SweepResult,
    records: Iterable[SearchRecord],
    *,
    provenance: object,
    max_serialized_bytes: int = DEFAULT_MAX_SERIALIZED_BYTES,
) -> Rung2SearchBundle:
    """Build a fully linked source payload without trusting mapping URLs.

    A degraded or partial sweep is rejected.  Every mapping term must belong to
    the matrix vocabulary, every mapping target must resolve to the
    authoritative manifest, and the laundering target's kind and URL must
    still agree with that projection.  The URL is never serialized into the
    bridge entry; the manifest's ``SearchRecord.target`` is the sole copy.
    The required provenance object is included in the bundle identity and
    must match the matrix's canonical vocabulary and query-token fingerprints.
    """
    _validate_max_serialized_bytes(max_serialized_bytes)
    if not isinstance(provenance, Rung2InputProvenance):
        raise BridgeCompilationError("Rung-2 input provenance must be a validated Rung2InputProvenance")
    if sweep.failed_query_count:
        raise BridgeCompilationError("cannot build a Rung-2 bundle from a degraded sweep")
    if sweep.query_count != len(sweep.mappings):
        raise BridgeCompilationError("sweep query_count does not match its mappings")

    manifest = build_record_manifest(records)
    manifest_by_id = {entry.record_id: entry for entry in manifest.records}
    matrix_terms = {row.term for row in matrix.rows}
    grouped: dict[str, list[SemanticBridgeTarget]] = {}
    positions: dict[tuple[str, str], int] = {}
    for mapping in sweep.mappings:
        term = canonical_vocabulary((mapping.query,))[0]
        if term not in matrix_terms:
            raise BridgeCompilationError(f"sweep term {term!r} is absent from the matrix vocabulary")
        targets = grouped.setdefault(term, [])
        mapping_record_ids: set[str] = set()
        for target in mapping.targets:
            if target.record_id in mapping_record_ids:
                raise BridgeCompilationError(
                    f"mapping {mapping.query!r} repeats target {target.record_id!r}"
                )
            mapping_record_ids.add(target.record_id)
            manifest_entry = manifest_by_id.get(target.record_id)
            if manifest_entry is None:
                raise BridgeCompilationError(
                    f"mapping target {target.record_id!r} is absent from the authoritative record manifest"
                )
            if target.kind is not manifest_entry.kind:
                raise BridgeCompilationError(f"mapping kind disagrees with SearchRecord {target.record_id!r}")
            if target.target != manifest_entry.target:
                raise BridgeCompilationError(f"mapping target disagrees with SearchRecord {target.record_id!r}")
            key = (term, target.record_id)
            if key in positions:
                index = positions[key]
                targets[index] = SemanticBridgeTarget(
                    record_id=target.record_id,
                    ranking_weight=max(target.ranking_weight, targets[index].ranking_weight),
                )
                continue
            positions[key] = len(targets)
            targets.append(
                SemanticBridgeTarget(record_id=target.record_id, ranking_weight=target.ranking_weight),
            )

    if set(grouped) != matrix_terms:
        missing = sorted(matrix_terms - set(grouped), key=lambda term: term.encode(_UTF_8))
        raise BridgeCompilationError(f"matrix terms have no semantic bridge mapping: {missing[0]!r}")
    entries_list: list[SemanticBridgeEntry] = []
    for term in sorted(grouped, key=lambda item: item.encode(_UTF_8)):
        ordered_targets = tuple(
            sorted(
                grouped[term],
                key=lambda target: (-target.ranking_weight, target.record_id.encode(_UTF_8)),
            ),
        )
        entries_list.append(
            SemanticBridgeEntry(
                term=term,
                targets=ordered_targets,
                targets_sha256=_hash_json([target.model_dump(mode="json") for target in ordered_targets]),
            ),
        )
    entries = tuple(entries_list)
    bridge_core: dict[str, object] = {
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "row_order": _ROW_ORDER,
        "matrix_vocabulary_sha256": matrix.vocabulary_sha256,
        "record_manifest_sha256": manifest.records_sha256,
        "term_count": len(entries),
        "entries": [entry.model_dump(mode="json") for entry in entries],
        "artifact_sha256": "0" * 64,
        "serialized_bytes": 0,
    }
    bridge_core["artifact_sha256"] = _hash_json(
        {key: value for key, value in bridge_core.items() if key not in {"artifact_sha256", "serialized_bytes"}},
    )
    bridge_core["serialized_bytes"] = _fixed_point_serialized_size(bridge_core)
    bridge = SemanticBridge.model_validate(bridge_core)

    bundle_core: dict[str, object] = {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "matrix": matrix.model_dump(mode="json"),
        "bridge": bridge.model_dump(mode="json"),
        "record_manifest": manifest.model_dump(mode="json"),
        "input_provenance": provenance.model_dump(mode="json"),
        "serialized_bytes": 0,
        "artifact_sha256": "0" * 64,
    }
    bundle_core["artifact_sha256"] = _hash_json(
        {key: value for key, value in bundle_core.items() if key not in {"artifact_sha256", "serialized_bytes"}},
    )
    bundle_core["serialized_bytes"] = _fixed_point_serialized_size(bundle_core)
    if bundle_core["serialized_bytes"] > max_serialized_bytes:
        raise BridgeCompilationError(
            f"matrix, bridge, manifest, and input provenance serialize to {bundle_core['serialized_bytes']} bytes; "
            f"maximum is {max_serialized_bytes}"
        )
    return Rung2SearchBundle.model_validate(bundle_core)


def load_rung2_search_bundle(path: Path) -> Rung2SearchBundle:
    """Load one canonical bundle and fail closed on absent or altered bytes."""
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise BridgeCompilationError(f"cannot read Rung-2 bundle {path}: {exc}") from exc
    try:
        bundle = Rung2SearchBundle.model_validate_json(payload)
    except ValueError as exc:
        raise BridgeCompilationError(f"invalid Rung-2 bundle {path}: {exc}") from exc
    if payload != bundle.to_json_bytes():
        raise BridgeCompilationError(f"Rung-2 bundle {path} is not in canonical JSON form")
    if len(payload) != bundle.serialized_bytes or len(payload) > DEFAULT_MAX_SERIALIZED_BYTES:
        raise BridgeCompilationError(f"Rung-2 bundle {path} exceeds or misstates the shared byte bound")
    return bundle


def write_rung2_search_bundle(bundle: Rung2SearchBundle, destination: Path) -> None:
    """Write an already validated bundle without changing its bytes."""
    destination.write_bytes(bundle.to_json_bytes())


def _validate_max_serialized_bytes(value: int) -> None:
    """Reject a caller-supplied bound that weakens the shared contract."""
    if value <= 0 or value > DEFAULT_MAX_SERIALIZED_BYTES:
        raise BridgeCompilationError(
            f"max_serialized_bytes must be between 1 and {DEFAULT_MAX_SERIALIZED_BYTES}"
        )


def _fixed_point_serialized_size(payload: dict[str, object]) -> int:
    """Find the stable byte count when the count itself is serialized."""
    size = 0
    for _ in range(8):
        payload["serialized_bytes"] = size
        candidate = len(_canonical_json_bytes(payload))
        if candidate == size:
            return size
        size = candidate
    raise BridgeCompilationError("serialized byte count did not converge")


def _hash_json(payload: object) -> str:
    """Hash one canonical JSON value."""
    return sha256(_canonical_json_bytes(payload)).hexdigest()


def _canonical_json_bytes(payload: object) -> bytes:
    """Serialize JSON with stable ordering, compact separators, and newline."""
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode(_UTF_8)
