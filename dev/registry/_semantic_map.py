"""Typed development-only semantics for official AEAT record-design slots.

The official record-design intermediate representation owns coordinates.  This
module deliberately owns only the reviewed registry meaning which is joined to
those coordinates in a later generator step.  It neither resolves catalogue
references nor matches a semantic entry to parser output.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cadrumo.core import CasillaId
from cadrumo.domain.calculations.registry import (
    BindingId,
    CasillaFieldKindValue,
    ExportComputedKeyValue,
    ExportDraftAttributeValue,
    ExportFieldId,
    ExportHeaderKeyValue,
    ExportSemanticPayloadAxis,
    LegalRefs,
    ModeloId,
    RecordId,
    SourceRefs,
    export_semantic_payload_axis,
)

__all__ = [
    "SemanticMap",
    "SemanticMapAnchor",
    "SemanticMapEntry",
    "SemanticMapRecord",
]


class _StrictModel(BaseModel):
    """Frozen development-tool boundary model with no untyped extras."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class SemanticMapAnchor(_StrictModel):
    """The complete parser-owned identity of one official design slot.

    ``record_identity`` is the parsed slot identity carried by
    :class:`RecordDesignIntermediateField`.  The optional cell intentionally
    mirrors the intermediate representation: workbook designs have a stable
    parser-column cell anchor, while a PDF design has no such cell.
    """

    sheet: str = Field(min_length=1)
    source_row: int = Field(gt=0)
    source_cell: str | None = Field(default=None, pattern=r"^[A-Z]+[1-9][0-9]*$")
    ordinal: int = Field(gt=0)
    record_identity: str = Field(min_length=1)


class SemanticMapEntry(_StrictModel):
    """Reviewed registry meaning for one exact parser anchor.

    Coordinates, field shape, and renderer formatting are intentionally absent:
    they belong to the hash-verified official design.  The following generator
    steps may use this entry only after they have established an exact bijection
    to parser output and resolved all canonical references through the registry.
    """

    anchor: SemanticMapAnchor
    export_field_id: ExportFieldId
    kind: CasillaFieldKindValue
    casilla_id: CasillaId | None = None
    binding: BindingId | None = None
    literal: str | None = None
    header_key: ExportHeaderKeyValue | None = None
    draft_attribute: ExportDraftAttributeValue | None = None
    computed_key: ExportComputedKeyValue | None = None
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @model_validator(mode="after")
    def _validate_exact_kind_semantics(self) -> SemanticMapEntry:
        """Require exactly the one semantic payload applicable to ``kind``."""
        payloads = {
            ExportSemanticPayloadAxis.CASILLA_ID: self.casilla_id,
            ExportSemanticPayloadAxis.BINDING: self.binding,
            ExportSemanticPayloadAxis.LITERAL: self.literal,
            ExportSemanticPayloadAxis.HEADER_KEY: self.header_key,
            ExportSemanticPayloadAxis.DRAFT_ATTRIBUTE: self.draft_attribute,
            ExportSemanticPayloadAxis.COMPUTED_KEY: self.computed_key,
        }
        required = export_semantic_payload_axis(self.kind)
        declared = tuple(axis for axis, value in payloads.items() if value is not None)
        if required is None:
            if declared:
                raise ValueError(
                    f"semantic-map {self.kind.value} field {self.export_field_id!r} "
                    f"must not declare semantic payloads: {', '.join(axis.value for axis in declared)}",
                )
            return self
        if declared != (required,):
            declared_description = ", ".join(axis.value for axis in declared) if declared else "none"
            raise ValueError(
                f"semantic-map {self.kind.value} field {self.export_field_id!r} must declare "
                f"only {required.value}; declared {declared_description}",
            )
        return self


class SemanticMapRecord(_StrictModel):
    """Reviewed semantic identity for one exact parser record.

    The source design still owns record order, length, fields, and every wire
    characteristic.  This map supplies only the canonical registry identifier
    and business record type that cannot be inferred from a workbook tab name.
    """

    sheet: str = Field(min_length=1)
    record_identity: str = Field(min_length=1)
    export_record_id: RecordId
    record_type: str = Field(min_length=1)


class SemanticMap(_StrictModel):
    """One authored semantic map for one modelo and one design epoch.

    Entries and records are exact parser keys only at this stage.  Exact parser
    joining, uniqueness, catalogue resolution, source applicability, and anomaly
    handling remain later explicit generator contracts.
    """

    modelo: ModeloId
    design_epoch: str = Field(min_length=1)
    records: tuple[SemanticMapRecord, ...] = Field(min_length=1)
    entries: tuple[SemanticMapEntry, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _require_unique_record_semantics(self) -> SemanticMap:
        record_keys = tuple((record.sheet, record.record_identity) for record in self.records)
        duplicate_keys = sorted({key for key in record_keys if record_keys.count(key) > 1})
        if duplicate_keys:
            raise ValueError(f"semantic map contains duplicate exact record anchors: {duplicate_keys!r}")
        record_ids = tuple(str(record.export_record_id) for record in self.records)
        duplicate_ids = sorted({record_id for record_id in record_ids if record_ids.count(record_id) > 1})
        if duplicate_ids:
            raise ValueError(f"semantic map contains duplicate canonical export record ids: {duplicate_ids!r}")
        return self
