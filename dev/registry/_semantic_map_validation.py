"""Fail-closed validation for authored semantic maps and parser output.

This development-only boundary verifies the two authorities before a later
generator step joins them.  It deliberately validates the structural join but
does not render, derive, or publish export fragments.
"""

from __future__ import annotations

from collections import Counter
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from cadrumo.domain.calculations.registry import (
    RegistrySnapshot,
    RegistryValidationError,
    SourceRefId,
    casillas_by_id,
)

from ._record_design_ir import RecordDesignIntermediate, RecordDesignIntermediateField
from ._semantic_map import SemanticMap, SemanticMapAnchor, SemanticMapEntry

__all__ = [
    "SemanticMapAnomalyException",
    "validate_semantic_map",
]


class _StrictModel(BaseModel):
    """Frozen development-tool boundary model with no untyped extras."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class SemanticMapAnomalyException(_StrictModel):
    """A hash-pinned parser or source anomaly noted without changing mapping.

    Exceptions document the limited parser/source anomalies that future
    maintenance may need to explain.  They intentionally contain no anchor,
    coordinate, or semantic fields, and :func:`validate_semantic_map` never
    consults them to waive source, reference, or bijection validation.
    """

    source_ref: SourceRefId
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    category: Literal["parser_anomaly", "source_anomaly"]
    reason: str = Field(min_length=1)


_AnchorKey = tuple[str, int, str | None, int, str]


def validate_semantic_map(
    semantic_map: SemanticMap,
    intermediate: RecordDesignIntermediate,
    snapshot: RegistrySnapshot,
    *,
    anomaly_exceptions: tuple[SemanticMapAnomalyException, ...] = (),
) -> None:
    """Validate one complete semantic map against one parser intermediate.

    The snapshot is the target revision authority for semantic identities; it
    is never used to infer official coordinates or to admit a legacy export
    layout.  Export field identifiers are already grammar-checked by the
    semantic-map schema and must be unique in this generated-layout map.

    Raises:
        RegistryValidationError: If source authority, exact bijection, or a
            canonical registry reference is invalid.
    """
    _validate_scope(semantic_map, intermediate, snapshot)
    _validate_source_authority(intermediate, snapshot)
    _validate_anomaly_exceptions(anomaly_exceptions, intermediate)
    _validate_exact_bijection(semantic_map, intermediate)
    _validate_entry_references(semantic_map, snapshot)


def _validate_scope(
    semantic_map: SemanticMap,
    intermediate: RecordDesignIntermediate,
    snapshot: RegistrySnapshot,
) -> None:
    if semantic_map.modelo != snapshot.modelo.id:
        raise RegistryValidationError(
            f"semantic map modelo {semantic_map.modelo!r} does not match target snapshot modelo {snapshot.modelo.id!r}",
        )
    if semantic_map.design_epoch != intermediate.source.design_epoch:
        raise RegistryValidationError(
            f"semantic map design epoch {semantic_map.design_epoch!r} does not match parser "
            f"design epoch {intermediate.source.design_epoch!r}",
        )


def _validate_source_authority(
    intermediate: RecordDesignIntermediate,
    snapshot: RegistrySnapshot,
) -> None:
    source = snapshot.sources.get(intermediate.source.source_ref)
    if source is None:
        raise RegistryValidationError(
            f"parser intermediate source {intermediate.source.source_ref!r} is absent from the target "
            "registry source catalogue",
        )
    if source.kind != "record_design":
        raise RegistryValidationError(
            f"parser intermediate source {source.id!r} must resolve to a record-design source",
        )
    if source.sha256 != intermediate.source.source_sha256:
        raise RegistryValidationError(
            f"parser intermediate source {source.id!r} SHA-256 does not match the target registry catalogue",
        )
    if source.record_design_epoch != intermediate.source.design_epoch:
        raise RegistryValidationError(
            f"parser intermediate source {source.id!r} design epoch {intermediate.source.design_epoch!r} "
            "does not match the target registry catalogue",
        )


def _validate_anomaly_exceptions(
    anomaly_exceptions: tuple[SemanticMapAnomalyException, ...],
    intermediate: RecordDesignIntermediate,
) -> None:
    seen: set[SemanticMapAnomalyException] = set()
    for exception in anomaly_exceptions:
        if exception in seen:
            raise RegistryValidationError(
                f"duplicate semantic-map anomaly exception for source {exception.source_ref!r}: "
                f"{exception.category} {exception.reason!r}",
            )
        seen.add(exception)
        if exception.source_ref != intermediate.source.source_ref:
            raise RegistryValidationError(
                f"semantic-map anomaly exception source {exception.source_ref!r} does not match parser "
                f"intermediate source {intermediate.source.source_ref!r}",
            )
        if exception.source_sha256 != intermediate.source.source_sha256:
            raise RegistryValidationError(
                f"semantic-map anomaly exception for source {exception.source_ref!r} is not pinned to the "
                "parser intermediate SHA-256",
            )


def _validate_exact_bijection(
    semantic_map: SemanticMap,
    intermediate: RecordDesignIntermediate,
) -> None:
    intermediate_keys = tuple(
        _intermediate_anchor_key(field) for sheet in intermediate.sheets for field in sheet.fields
    )
    semantic_keys = tuple(_semantic_anchor_key(entry.anchor) for entry in semantic_map.entries)
    duplicate_intermediate = _duplicate_anchor_keys(intermediate_keys)
    if duplicate_intermediate:
        raise RegistryValidationError(
            "parser intermediate contains duplicate exact anchors; refusing ambiguous semantic-map join: "
            f"{_format_anchor_keys(duplicate_intermediate)}",
        )
    duplicate_semantic = _duplicate_anchor_keys(semantic_keys)
    if duplicate_semantic:
        raise RegistryValidationError(
            "semantic map contains duplicate exact anchors; refusing ambiguous parser join: "
            f"{_format_anchor_keys(duplicate_semantic)}",
        )

    intermediate_set = set(intermediate_keys)
    semantic_set = set(semantic_keys)
    missing = tuple(sorted(intermediate_set - semantic_set))
    extra = tuple(sorted(semantic_set - intermediate_set))
    if missing or extra:
        details: list[str] = []
        if missing:
            details.append(f"missing semantic entries {_format_anchor_keys(missing)}")
        if extra:
            details.append(f"extra semantic entries {_format_anchor_keys(extra)}")
        raise RegistryValidationError(
            "semantic map must form a complete exact bijection with parser output; " + "; ".join(details),
        )


def _validate_entry_references(semantic_map: SemanticMap, snapshot: RegistrySnapshot) -> None:
    duplicate_export_ids = _duplicate_string_keys(tuple(str(entry.export_field_id) for entry in semantic_map.entries))
    if duplicate_export_ids:
        raise RegistryValidationError(
            "semantic map contains duplicate canonical export field ids in one generated layout: "
            f"{', '.join(duplicate_export_ids)}",
        )

    casilla_ids = casillas_by_id(snapshot.revision)
    binding_ids = {binding.id for binding in snapshot.revision.bindings}
    for entry in semantic_map.entries:
        if entry.casilla_id is not None and entry.casilla_id not in casilla_ids:
            raise RegistryValidationError(
                f"semantic map export field {entry.export_field_id!r} references unknown target-revision "
                f"casilla {entry.casilla_id!r}",
            )
        if entry.binding is not None and entry.binding not in binding_ids:
            raise RegistryValidationError(
                f"semantic map export field {entry.export_field_id!r} references unknown target-revision "
                f"binding {entry.binding!r}",
            )
        _validate_catalogue_refs(entry, snapshot)


def _validate_catalogue_refs(entry: SemanticMapEntry, snapshot: RegistrySnapshot) -> None:
    unknown_legal = tuple(sorted(set(entry.legal_refs) - set(snapshot.legal)))
    if unknown_legal:
        raise RegistryValidationError(
            f"semantic map export field {entry.export_field_id!r} has unresolved legal refs: {unknown_legal!r}",
        )
    unknown_sources = tuple(sorted(set(entry.source_refs) - set(snapshot.sources)))
    if unknown_sources:
        raise RegistryValidationError(
            f"semantic map export field {entry.export_field_id!r} has unresolved source refs: {unknown_sources!r}",
        )


def _intermediate_anchor_key(field: RecordDesignIntermediateField) -> _AnchorKey:
    return field.sheet, field.source_row, field.source_cell, field.ordinal, field.record_identity


def _semantic_anchor_key(anchor: SemanticMapAnchor) -> _AnchorKey:
    return anchor.sheet, anchor.source_row, anchor.source_cell, anchor.ordinal, anchor.record_identity


def _duplicate_anchor_keys(keys: tuple[_AnchorKey, ...]) -> tuple[_AnchorKey, ...]:
    counts = Counter(keys)
    return tuple(sorted(key for key, count in counts.items() if count > 1))


def _duplicate_string_keys(keys: tuple[str, ...]) -> tuple[str, ...]:
    counts = Counter(keys)
    return tuple(sorted(key for key, count in counts.items() if count > 1))


def _format_anchor_keys(keys: tuple[_AnchorKey, ...]) -> str:
    return ", ".join(
        f"(sheet={sheet!r}, source_row={source_row}, source_cell={source_cell!r}, ordinal={ordinal}, "
        f"record_identity={record_identity!r})"
        for sheet, source_row, source_cell, ordinal, record_identity in keys
    )
