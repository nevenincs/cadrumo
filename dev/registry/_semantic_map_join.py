"""Exact, source-ordered pairing of record-design fields and reviewed meaning.

This development-only boundary consumes the typed parser intermediate and the
reviewed semantic map after their complete authority validation.  It preserves
parser coordinates and map meaning as separate typed values for the next
generation boundary; it neither produces nor observes a fragment tree.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cadrumo.core import Period
from cadrumo.domain.calculations.registry import (
    ModeloId,
    ProjectionEndpointDeclaration,
    RegistrySnapshot,
    RevisionId,
)

from ._record_design_ir import (
    RecordDesignIntermediate,
    RecordDesignIntermediateField,
    RecordDesignIntermediateSheet,
    RecordDesignIntermediateSource,
    RecordDesignIntermediateVariableEnvelope,
)
from ._semantic_map import (
    M303VariableEnvelopeSemantic,
    SemanticMap,
    SemanticMapAnchor,
    SemanticMapEntry,
    SemanticMapRecord,
)
from ._semantic_map_validation import SemanticMapAnomalyException, validate_semantic_map

__all__ = [
    "JoinedM303VariableEnvelope",
    "JoinedRecordDesign",
    "JoinedRecordDesignField",
    "JoinedRecordDesignRecord",
    "join_record_design_semantics",
]


class _StrictModel(BaseModel):
    """Frozen development-tool boundary with no untyped extras."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


type _AnchorKey = tuple[str, int, str | None, int, str]
type _RecordKey = tuple[str, str]


class JoinedRecordDesignField(_StrictModel):
    """One parser-owned coordinate field paired with one reviewed map entry."""

    parser_field: RecordDesignIntermediateField
    semantic_entry: SemanticMapEntry

    @model_validator(mode="after")
    def _require_same_exact_anchor(self) -> JoinedRecordDesignField:
        if _parser_anchor_key(self.parser_field) != _semantic_anchor_key(self.semantic_entry.anchor):
            raise ValueError("joined record-design field requires the same complete exact anchor")
        return self


class JoinedRecordDesignRecord(_StrictModel):
    """One parser-owned record paired with its reviewed canonical meaning."""

    parser_sheet: RecordDesignIntermediateSheet
    semantic_record: SemanticMapRecord
    fields: tuple[JoinedRecordDesignField, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _require_same_exact_record_anchor(self) -> JoinedRecordDesignRecord:
        parser_key = self.parser_sheet.sheet, self.parser_sheet.record_identity
        semantic_key = self.semantic_record.sheet, self.semantic_record.record_identity
        if parser_key != semantic_key:
            raise ValueError("joined record-design record requires the same complete exact record anchor")
        if any(field.parser_field.record_identity != self.parser_sheet.record_identity for field in self.fields):
            raise ValueError("joined record-design record fields must belong to its parser record")
        return self


class JoinedM303VariableEnvelope(_StrictModel):
    """The exact parser wrapper paired with its reviewed DP30300 semantics."""

    parser_envelope: RecordDesignIntermediateVariableEnvelope
    semantic: M303VariableEnvelopeSemantic

    @model_validator(mode="after")
    def _require_same_parser_identity(self) -> JoinedM303VariableEnvelope:
        if self.parser_envelope.record_identity != self.semantic.record_identity:
            raise ValueError("joined M303 variable envelope requires the same parser and semantic identity")
        return self


class JoinedRecordDesign(_StrictModel):
    """One complete design with fields in the official parser's source order."""

    modelo: ModeloId
    source: RecordDesignIntermediateSource
    revision_id: RevisionId | None = None
    filing_period: Period | None = None
    records: tuple[JoinedRecordDesignRecord, ...] = Field(min_length=1)
    fields: tuple[JoinedRecordDesignField, ...] = Field(min_length=1)
    projection_endpoints: tuple[ProjectionEndpointDeclaration, ...] = ()
    variable_envelopes: tuple[RecordDesignIntermediateVariableEnvelope, ...] = ()
    m303_variable_envelope: JoinedM303VariableEnvelope | None = None

    @model_validator(mode="after")
    def _require_complete_joined_state(self) -> JoinedRecordDesign:
        record_fields = tuple(field for record in self.records for field in record.fields)
        if self.fields != record_fields:
            raise ValueError("joined record-design fields must exactly flatten its records")
        fixed_keys = {(record.parser_sheet.sheet, record.parser_sheet.record_identity) for record in self.records}
        envelope_keys = {(envelope.sheet, envelope.record_identity) for envelope in self.variable_envelopes}
        if fixed_keys.intersection(envelope_keys):
            raise ValueError("joined record design cannot classify one identity as fixed and variable")
        parser_m303_envelopes = tuple(
            envelope for envelope in self.variable_envelopes if envelope.record_identity == "DP30300"
        )
        if self.m303_variable_envelope is None:
            if parser_m303_envelopes:
                raise ValueError("joined DP30300 parser envelope requires reviewed semantic composition")
        elif parser_m303_envelopes != (self.m303_variable_envelope.parser_envelope,):
            raise ValueError("joined M303 variable envelope must be the sole parser DP30300 wrapper")
        elif self.revision_id is None or self.filing_period is None:
            raise ValueError(
                "joined M303 variable envelope requires the exact selected snapshot revision and filing period",
            )
        return self


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
    entries_by_anchor = {_semantic_anchor_key(entry.anchor): entry for entry in semantic_map.entries}
    records_by_anchor = {_semantic_record_key(record): record for record in semantic_map.records}
    joined_records = tuple(
        JoinedRecordDesignRecord(
            parser_sheet=sheet,
            semantic_record=records_by_anchor[_intermediate_record_key(sheet)],
            fields=tuple(
                JoinedRecordDesignField(
                    parser_field=field,
                    semantic_entry=entries_by_anchor[_parser_anchor_key(field)],
                )
                for field in sheet.fields
            ),
        )
        for sheet in intermediate.sheets
    )
    return JoinedRecordDesign(
        modelo=semantic_map.modelo,
        source=intermediate.source,
        revision_id=snapshot.revision.id,
        filing_period=snapshot.filing_period,
        records=joined_records,
        fields=tuple(field for record in joined_records for field in record.fields),
        projection_endpoints=snapshot.revision.projection_endpoints,
        variable_envelopes=intermediate.variable_envelopes,
        m303_variable_envelope=(
            JoinedM303VariableEnvelope(
                parser_envelope=next(
                    envelope for envelope in intermediate.variable_envelopes if envelope.record_identity == "DP30300"
                ),
                semantic=semantic_map.variable_envelopes[0],
            )
            if semantic_map.variable_envelopes
            else None
        ),
    )


def _parser_anchor_key(field: RecordDesignIntermediateField) -> _AnchorKey:
    return field.sheet, field.source_row, field.source_cell, field.ordinal, field.record_identity


def _semantic_anchor_key(anchor: SemanticMapAnchor) -> _AnchorKey:
    return anchor.sheet, anchor.source_row, anchor.source_cell, anchor.ordinal, anchor.record_identity


def _intermediate_record_key(sheet: RecordDesignIntermediateSheet) -> _RecordKey:
    return sheet.sheet, sheet.record_identity


def _semantic_record_key(record: SemanticMapRecord) -> _RecordKey:
    return record.sheet, record.record_identity
