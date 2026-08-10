"""Exact, source-ordered pairing of record-design fields and reviewed meaning.

This development-only boundary consumes the typed parser intermediate and the
reviewed semantic map after their complete authority validation.  It preserves
parser coordinates and map meaning as separate typed values for the next
generation boundary; it neither produces nor observes a fragment tree.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cadrumo.domain.calculations.registry import RegistrySnapshot

from ._record_design_ir import (
    RecordDesignIntermediate,
    RecordDesignIntermediateField,
    RecordDesignIntermediateSource,
)
from ._semantic_map import SemanticMap, SemanticMapAnchor, SemanticMapEntry
from ._semantic_map_validation import SemanticMapAnomalyException, validate_semantic_map

__all__ = [
    "JoinedRecordDesign",
    "JoinedRecordDesignField",
    "join_record_design_semantics",
]


class _StrictModel(BaseModel):
    """Frozen development-tool boundary with no untyped extras."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


type _AnchorKey = tuple[str, int, str | None, int, str]


class JoinedRecordDesignField(_StrictModel):
    """One parser-owned coordinate field paired with one reviewed map entry."""

    parser_field: RecordDesignIntermediateField
    semantic_entry: SemanticMapEntry

    @model_validator(mode="after")
    def _require_same_exact_anchor(self) -> JoinedRecordDesignField:
        if _parser_anchor_key(self.parser_field) != _semantic_anchor_key(self.semantic_entry.anchor):
            raise ValueError("joined record-design field requires the same complete exact anchor")
        return self


class JoinedRecordDesign(_StrictModel):
    """One complete design with fields in the official parser's source order."""

    source: RecordDesignIntermediateSource
    fields: tuple[JoinedRecordDesignField, ...] = Field(min_length=1)


def join_record_design_semantics(
    semantic_map: SemanticMap,
    intermediate: RecordDesignIntermediate,
    snapshot: RegistrySnapshot,
    *,
    anomaly_exceptions: tuple[SemanticMapAnomalyException, ...] = (),
) -> JoinedRecordDesign:
    """Pair every parser field with exactly one reviewed semantic entry.

    Validation precedes indexing, so the direct lookup below is reachable only
    for a source/applicability-valid complete bijection.  Iteration follows the
    parser-owned sheet and field order unchanged.
    """
    validate_semantic_map(
        semantic_map,
        intermediate,
        snapshot,
        anomaly_exceptions=anomaly_exceptions,
    )
    entries_by_anchor = {
        _semantic_anchor_key(entry.anchor): entry
        for entry in semantic_map.entries
    }
    return JoinedRecordDesign(
        source=intermediate.source,
        fields=tuple(
            JoinedRecordDesignField(
                parser_field=field,
                semantic_entry=entries_by_anchor[_parser_anchor_key(field)],
            )
            for sheet in intermediate.sheets
            for field in sheet.fields
        ),
    )


def _parser_anchor_key(field: RecordDesignIntermediateField) -> _AnchorKey:
    return field.sheet, field.source_row, field.source_cell, field.ordinal, field.record_identity


def _semantic_anchor_key(anchor: SemanticMapAnchor) -> _AnchorKey:
    return anchor.sheet, anchor.source_row, anchor.source_cell, anchor.ordinal, anchor.record_identity
