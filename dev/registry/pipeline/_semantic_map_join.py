"""Exact, source-ordered pairing of record-design fields and reviewed meaning.

This development-only boundary consumes the typed parser intermediate and the
reviewed semantic map after their complete authority validation.  It preserves
parser coordinates and map meaning as separate typed values for the next
generation boundary; it neither produces nor observes a fragment tree.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.ids import (
    ModeloId,
    RevisionId,
)
from cadrumo.domain.calculations.registry.schema_exports import ProjectionEndpointDeclaration
from cadrumo.domain.calculations.registry.static_inspection import GeneratedArtifactInspection

from ._record_design_ir import (
    AnchorKey,
    RecordDesignIntermediate,
    RecordDesignIntermediateAuxiliaryEnvelopeHeader,
    RecordDesignIntermediateField,
    RecordDesignIntermediateSheet,
    RecordDesignIntermediateSource,
    RecordDesignIntermediateVariableEnvelope,
    intermediate_anchor_key,
    intermediate_record_key,
)
from ._semantic_map import (
    SemanticMap,
    SemanticMapEntry,
    SemanticMapRecord,
    VariableEnvelopeSemantic,
    semantic_anchor_key,
    semantic_record_key,
)
from ._semantic_map_validation import (
    SemanticMapAnomalyException,
    validate_semantic_map,
)

__all__ = [
    "JoinedRecordDesign",
    "JoinedRecordDesignField",
    "JoinedRecordDesignRecord",
    "JoinedVariableEnvelope",
    "join_record_design_semantics",
]


class _StrictModel(BaseModel):
    """Frozen development-tool boundary with no untyped extras."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class JoinedRecordDesignField(_StrictModel):
    """One parser-owned coordinate field paired with one reviewed map entry."""

    parser_field: RecordDesignIntermediateField
    semantic_entry: SemanticMapEntry

    @model_validator(mode="after")
    def _require_same_exact_anchor(self) -> JoinedRecordDesignField:
        if intermediate_anchor_key(self.parser_field) != semantic_anchor_key(self.semantic_entry.anchor):
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


class JoinedVariableEnvelope(_StrictModel):
    """The exact parser wrapper paired with its reviewed envelope semantics."""

    parser_envelope: RecordDesignIntermediateVariableEnvelope
    semantic: VariableEnvelopeSemantic

    @model_validator(mode="after")
    def _require_same_parser_identity(self) -> JoinedVariableEnvelope:
        if self.parser_envelope.record_identity != self.semantic.record_identity:
            raise ValueError("joined variable envelope requires the same parser and semantic identity")
        return self


class JoinedRecordDesign(_StrictModel):
    """One complete design with fields in the official parser's source order."""

    modelo: ModeloId
    source: RecordDesignIntermediateSource
    authored_semantic_map: SemanticMap | None = None
    compiled_semantic_map: SemanticMap | None = None
    revision_id: RevisionId | None = None
    records: tuple[JoinedRecordDesignRecord, ...] = Field(min_length=1)
    fields: tuple[JoinedRecordDesignField, ...] = Field(min_length=1)
    projection_endpoints: tuple[ProjectionEndpointDeclaration, ...] = ()
    variable_envelopes: tuple[RecordDesignIntermediateVariableEnvelope, ...] = ()
    auxiliary_envelope_headers: tuple[RecordDesignIntermediateAuxiliaryEnvelopeHeader, ...] = ()
    variable_envelope_contract: JoinedVariableEnvelope | None = None

    @model_validator(mode="after")
    def _require_complete_joined_state(self) -> JoinedRecordDesign:
        if (self.authored_semantic_map is None) != (self.compiled_semantic_map is None):
            raise ValueError("joined record design requires authored and compiled semantic maps together")
        if self.authored_semantic_map is not None and self.compiled_semantic_map is not None:
            if self.authored_semantic_map.model_copy(update={"entries": self.compiled_semantic_map.entries}) != (
                self.compiled_semantic_map
            ):
                raise ValueError("compiled semantic map may change only casilla tokens")
            if any(
                not _entry_is_exact_or_compiled_token(authored, compiled)
                for authored, compiled in zip(
                    self.authored_semantic_map.entries,
                    self.compiled_semantic_map.entries,
                    strict=True,
                )
            ):
                raise ValueError("compiled semantic-map casilla ids must be exact or solely left-zero-padded")
        record_fields = tuple(field for record in self.records for field in record.fields)
        if self.fields != record_fields:
            raise ValueError("joined record-design fields must exactly flatten its records")
        fixed_keys = {(record.parser_sheet.sheet, record.parser_sheet.record_identity) for record in self.records}
        envelope_keys = {(envelope.sheet, envelope.record_identity) for envelope in self.variable_envelopes}
        header_keys = {(header.sheet, header.record_identity) for header in self.auxiliary_envelope_headers}
        has_overlapping_composition_identity = (
            fixed_keys.intersection(envelope_keys)
            or fixed_keys.intersection(header_keys)
            or envelope_keys.intersection(header_keys)
        )
        if has_overlapping_composition_identity:
            raise ValueError("joined record design composition identities must remain disjoint")
        # The composed identity comes from the reviewed map, never a literal:
        # every modelo declaring this wrapper names its own record.
        composed_identity = (
            self.variable_envelope_contract.semantic.record_identity
            if self.variable_envelope_contract is not None
            else None
        )
        if self.variable_envelope_contract is None:
            if self.variable_envelopes:
                raise ValueError("joined parser envelope requires reviewed semantic composition")
        elif tuple(
            envelope for envelope in self.variable_envelopes if envelope.record_identity == composed_identity
        ) != (self.variable_envelope_contract.parser_envelope,):
            raise ValueError(f"joined variable envelope must be the sole parser {composed_identity!r} wrapper")
        elif self.revision_id is None:
            raise ValueError("joined variable envelope requires the exact selected revision")
        return self


def _entry_is_exact_or_compiled_token(authored: SemanticMapEntry, compiled: SemanticMapEntry) -> bool:
    """Prove validation changed an authored token only through its admitted form."""
    if authored == compiled:
        return True
    if authored.casilla_id is None or compiled.casilla_id is None:
        return False
    if authored.model_copy(update={"casilla_id": compiled.casilla_id}) != compiled:
        return False
    token = authored.casilla_id
    resolved = compiled.casilla_id
    if (
        token.isdecimal()
        and resolved.isdecimal()
        and len(resolved) > len(token)
        and resolved.endswith(token)
        and set(resolved[: -len(token)]) == {"0"}
    ):
        return True
    if token.isdecimal() and ":" in resolved:
        _segment, tail = resolved.rsplit(":", 1)
        return tail.isdecimal() and tail.lstrip("0") == token.lstrip("0") and bool(tail.lstrip("0"))
    return False


def join_record_design_semantics(
    semantic_map: SemanticMap,
    intermediate: RecordDesignIntermediate,
    inspection: GeneratedArtifactInspection,
    *,
    anomaly_exceptions: tuple[SemanticMapAnomalyException, ...] = (),
) -> JoinedRecordDesign:
    """Join static parser/map evidence through a non-filing revision inspection."""
    resolved_map = validate_semantic_map(
        semantic_map,
        intermediate,
        inspection,
        anomaly_exceptions=anomaly_exceptions,
    )
    return _join_record_design_semantics(
        resolved_map,
        intermediate,
        authored_semantic_map=semantic_map,
        revision_id=inspection.revision_id,
        projection_endpoints=inspection.projection_endpoints,
    )


def _join_record_design_semantics(
    semantic_map: SemanticMap,
    intermediate: RecordDesignIntermediate,
    *,
    authored_semantic_map: SemanticMap | None = None,
    revision_id: RevisionId,
    projection_endpoints: tuple[ProjectionEndpointDeclaration, ...],
) -> JoinedRecordDesign:
    entries_by_anchor = {semantic_anchor_key(entry.anchor): entry for entry in semantic_map.entries}
    records_by_anchor = {semantic_record_key(record): record for record in semantic_map.records}
    joined_records = tuple(
        JoinedRecordDesignRecord(
            parser_sheet=sheet,
            semantic_record=records_by_anchor[intermediate_record_key(sheet)],
            fields=tuple(
                JoinedRecordDesignField(
                    parser_field=field,
                    semantic_entry=_require_semantic_entry(entries_by_anchor, field),
                )
                for field in sheet.fields
            ),
        )
        for sheet in intermediate.sheets
    )
    return JoinedRecordDesign(
        modelo=semantic_map.modelo,
        source=intermediate.source,
        authored_semantic_map=authored_semantic_map,
        compiled_semantic_map=semantic_map,
        revision_id=revision_id,
        records=joined_records,
        fields=tuple(field for record in joined_records for field in record.fields),
        projection_endpoints=projection_endpoints,
        variable_envelopes=intermediate.variable_envelopes,
        auxiliary_envelope_headers=intermediate.auxiliary_envelope_headers,
        variable_envelope_contract=(
            JoinedVariableEnvelope(
                parser_envelope=next(
                    envelope
                    for envelope in intermediate.variable_envelopes
                    if envelope.record_identity == semantic_map.variable_envelopes[0].record_identity
                ),
                semantic=semantic_map.variable_envelopes[0],
            )
            if semantic_map.variable_envelopes
            else None
        ),
    )


def _require_semantic_entry(
    entries_by_anchor: dict[AnchorKey, SemanticMapEntry],
    field: RecordDesignIntermediateField,
) -> SemanticMapEntry:
    """Resolve one parser field's reviewed meaning, or refuse by name.

    ``join_record_design_semantics`` always runs ``validate_semantic_map``
    first, which already proves an exact bijection between parser anchors and
    semantic-map anchors -- so this lookup cannot miss through that entry
    point. It stays an explicit, named refusal rather than a bare subscript
    because the private join helper below it is not itself gated: a semantic
    map missing an entry for a field the parser can see must surface as a
    legible gap here too, never a bare ``KeyError`` inside the generator that
    authors filing artefacts.
    """
    entry = entries_by_anchor.get(intermediate_anchor_key(field))
    if entry is None:
        raise RegistryValidationError(
            f"semantic map has no entry for parser field: record_identity={field.record_identity!r}, "
            f"sheet={field.sheet!r}, ordinal={field.ordinal!r}, source_row={field.source_row!r}",
        )
    return entry
