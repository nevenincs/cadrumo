"""Typed development-only semantics for official AEAT record-design slots.

The official record-design intermediate representation owns coordinates.  This
module deliberately owns only the reviewed registry meaning which is joined to
those coordinates in a later generator step.  It neither resolves catalogue
references nor matches a semantic entry to parser output.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator, model_validator

from cadrumo.core import CasillaId, FilingProducerKey, FilingProjectionRef
from cadrumo.domain.calculations.registry import (
    BindingId,
    CasillaFieldKindValue,
    ExportComputedKey,
    ExportDraftAttribute,
    ExportFieldId,
    ExportSemanticPayloadAxis,
    LegalRefs,
    ModeloId,
    RecordId,
    SourceRefId,
    SourceRefs,
    export_semantic_payload_axis,
)

__all__ = [
    "M303EnvelopePrefixField",
    "M303EnvelopePrefixRole",
    "M303EnvelopeTotalAnchor",
    "M303VariableEnvelopeSemantic",
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


class M303EnvelopePrefixRole(StrEnum):
    """The closed semantic roles of the thirteen DP30300 prefix slots."""

    OPENING_TAG = "opening_tag"
    MODELO = "modelo"
    DISCRIMINANT = "discriminant"
    FILING_YEAR = "filing_year"
    PERIOD = "period"
    RECORD_TYPE = "record_type"
    AUX_OPENING_TAG = "aux_opening_tag"
    PRE_PROGRAM_FILLER = "pre_program_filler"
    PROGRAM_IDENTIFIER = "program_identifier"
    BETWEEN_IDENTITIES_FILLER = "between_identities_filler"
    DEVELOPER_TAX_ID = "developer_tax_id"
    POST_DEVELOPER_FILLER = "post_developer_filler"
    AUX_CLOSING_TAG = "aux_closing_tag"


def _coerce_m303_envelope_prefix_role(value: object) -> object:
    """Hydrate the authored TOML token into its one closed envelope role."""
    if isinstance(value, M303EnvelopePrefixRole):
        return value
    if isinstance(value, str):
        try:
            return M303EnvelopePrefixRole(value)
        except ValueError as exc:
            raise ValueError(f"unknown M303 envelope prefix role {value!r}") from exc
    raise ValueError("M303 envelope prefix role must be a string")


type M303EnvelopePrefixRoleValue = Annotated[
    M303EnvelopePrefixRole,
    BeforeValidator(_coerce_m303_envelope_prefix_role),
]


_M303_PREFIX_ROLE_ORDER: tuple[M303EnvelopePrefixRole, ...] = tuple(M303EnvelopePrefixRole)


class M303EnvelopePrefixField(_StrictModel):
    """One exact source anchor and its non-inferable DP30300 prefix role."""

    role: M303EnvelopePrefixRoleValue
    anchor: SemanticMapAnchor


class M303EnvelopeTotalAnchor(_StrictModel):
    """The parser-owned ``Total: Variable`` marker addressed without a field slot."""

    source_row: int = Field(gt=0)
    source_cell: str | None = Field(default=None, pattern=r"^[A-Z]+[1-9][0-9]*$")
    label: Literal["total"]
    length: Literal["Variable"]


class M303VariableEnvelopeSemantic(_StrictModel):
    """Hash-pinned semantic and composition authority for one DP30300 envelope.

    The ordinary semantic map deliberately excludes variable-envelope fields.
    This separate contract retains the thirteen exact prefix anchors, ordered
    references to the already-owned fixed body records, the relative closer,
    and the parser's variable total marker without turning the wrapper into a
    seventh fixed-width record.
    """

    source_ref: SourceRefId
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    record_identity: Literal["DP30300"]
    prefix_fields: tuple[M303EnvelopePrefixField, ...] = Field(min_length=13, max_length=13)
    body_anchor: SemanticMapAnchor
    body_record_ids: tuple[RecordId, ...] = Field(min_length=1)
    closer_anchor: SemanticMapAnchor
    total_anchor: M303EnvelopeTotalAnchor

    @model_validator(mode="after")
    def _require_complete_ordered_semantics(self) -> M303VariableEnvelopeSemantic:
        roles = tuple(field.role for field in self.prefix_fields)
        if roles != _M303_PREFIX_ROLE_ORDER:
            raise ValueError(
                "M303 variable envelope prefix roles must be the exact ordered thirteen-slot DP30300 sequence",
            )
        anchors = tuple(field.anchor for field in self.prefix_fields)
        if len(set(anchors)) != len(anchors):
            raise ValueError("M303 variable envelope prefix anchors must be unique")
        if self.body_anchor.record_identity != self.record_identity:
            raise ValueError("M303 variable envelope body anchor must belong to DP30300")
        if self.closer_anchor.record_identity != self.record_identity:
            raise ValueError("M303 variable envelope closer anchor must belong to DP30300")
        if len(set(self.body_record_ids)) != len(self.body_record_ids):
            raise ValueError("M303 variable envelope body record identities must be unique and ordered")
        return self


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
    producer_key: FilingProducerKey | None = None
    projection_ref: FilingProjectionRef | None = None
    draft_attribute: ExportDraftAttribute | None = None
    computed_key: ExportComputedKey | None = None
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @field_validator("projection_ref", mode="before")
    @classmethod
    def _require_loader_hydrated_projection_ref(cls, value: object) -> object:
        """Refuse raw reference payloads outside the sole TOML compiler boundary."""
        if value is not None and not isinstance(value, BaseModel):
            raise ValueError("projection_ref must be a typed FilingProjectionRef hydrated by load_semantic_map")
        return value

    @model_validator(mode="after")
    def _validate_exact_kind_semantics(self) -> SemanticMapEntry:
        """Require exactly the one semantic payload applicable to ``kind``."""
        payloads = {
            ExportSemanticPayloadAxis.CASILLA_ID: self.casilla_id,
            ExportSemanticPayloadAxis.BINDING: self.binding,
            ExportSemanticPayloadAxis.LITERAL: self.literal,
            ExportSemanticPayloadAxis.PRODUCER_KEY: self.producer_key,
            ExportSemanticPayloadAxis.PROJECTION_REF: self.projection_ref,
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
    required: bool = True
    repeat: Literal["projection_rows"] | None = None


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
    variable_envelopes: tuple[M303VariableEnvelopeSemantic, ...] = ()

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
        envelope_identities = tuple(envelope.record_identity for envelope in self.variable_envelopes)
        duplicate_envelopes = sorted(
            {identity for identity in envelope_identities if envelope_identities.count(identity) > 1},
        )
        if duplicate_envelopes:
            raise ValueError(f"semantic map contains duplicate variable-envelope identities: {duplicate_envelopes!r}")
        return self
