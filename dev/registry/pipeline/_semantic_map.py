"""Typed development-only semantics for official AEAT record-design slots.

The official record-design intermediate representation owns coordinates.  This
module deliberately owns only the reviewed registry meaning which is joined to
those coordinates in a later generator step.  It neither resolves catalogue
references nor matches a semantic entry to parser output.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator, model_validator

from cadrumo.core import FilingProducerKey, FilingProjectionRef, hydrate_filing_projection_ref
from cadrumo.core.casilla_id import CasillaId
from cadrumo.domain.calculations.export_field_kind import CasillaFieldKindValue
from cadrumo.domain.calculations.registry.export_semantics import (
    ExportComputedKey,
    ExportDraftAttribute,
    ExportSemanticPayloadAxis,
    export_semantic_payload_axis,
)
from cadrumo.domain.calculations.registry.ids import (
    BindingId,
    ExportFieldId,
    ModeloId,
    RecordId,
    SourceRefId,
)
from cadrumo.domain.calculations.registry.schema_base import LegalRefs, SourceRefs
from cadrumo.domain.calculations.registry.schema_exports import FilingEnvelopePrefixRole, RecordDiscriminator

from ._record_design_ir import AnchorKey, RecordKey

__all__ = [
    "EnvelopePrefixField",
    "EnvelopeTotalAnchor",
    "FilingEnvelopePrefixRole",
    "SemanticMap",
    "SemanticMapAnchor",
    "SemanticMapEntry",
    "SemanticMapRecord",
    "VariableEnvelopeSemantic",
    "semantic_anchor_key",
    "semantic_record_key",
]


class _StrictModel(BaseModel):
    """Frozen development-tool boundary model with no untyped extras."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


def _coerce_ordinal(value: object) -> object:
    """Accept a legacy authored int literal alongside the parser's printed str label.

    Committed semantic-map authoring data predates the parser's widened
    ``str | None`` ordinal and still writes bare integers (``ordinal = 14``).
    Coercing here lets that authored data hydrate unchanged while the anchor's
    stored value matches the parser type exactly, so ``semantic_anchor_key``
    and ``intermediate_anchor_key`` compare like-for-like without re-keying
    committed TOML/JSON.
    """
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    raise ValueError("ordinal must be a printed str label, a legacy int literal, or None")


type _AnchorOrdinal = Annotated[str | None, BeforeValidator(_coerce_ordinal)]


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
    #: The ordinal AEAT printed, verbatim -- a str because it is a printed LABEL,
    #: never an arithmetic value. Mirrors
    #: :attr:`domain.calculations.registry.RecordDesignField.ordinal`, which
    #: :class:`RecordDesignIntermediateField.ordinal` is a straight 1:1
    #: projection of; this anchor field is the same value one join step later.
    #: The type permits ``None`` to match the parser exactly, but stays
    #: REQUIRED (no default): every anchor naming a printed field names a real
    #: printed ordinal, and TOML has no way to author an explicit null, so an
    #: omitted key refuses at load rather than silently defaulting into an
    #: anchor no parser field can ever match. The ONE field that legitimately
    #: has no ordinal declares :attr:`ordinal_absent` instead -- see there.
    ordinal: _AnchorOrdinal | None = Field(default=None, min_length=1)
    #: Declares that AEAT printed this row with NO ordinal, so the anchor's
    #: ``ordinal`` is genuinely ``None`` rather than merely unauthored.
    #:
    #: Required because the parser can now produce such a field and could not
    #: before. A row AEAT prints without a naturaleza is staged as an unnamed
    #: position candidate and admitted only by a gap fill, which cannot invent
    #: the ordinal AEAT never printed: Modelo 184's ``151-155 PORCENTAJE DE
    #: RENTA ATRIBUIBLE A MIEMBROS RESIDENTES`` is the worked case. Giving it a
    #: synthetic ordinal would fabricate a printed LABEL, which is exactly what
    #: the ``ordinal`` field's own contract forbids.
    #:
    #: This stays an EXPLICIT opt-in rather than a default so the safety the
    #: required key bought is kept: omitting both keys still refuses, and only
    #: an author stating "this row has no printed ordinal" reaches ``None``.
    ordinal_absent: bool = False
    record_identity: str = Field(min_length=1)

    @model_validator(mode="after")
    def _require_ordinal_or_declared_absence(self) -> SemanticMapAnchor:
        if self.ordinal_absent and self.ordinal is not None:
            msg = "anchor declares ordinal_absent but also names an ordinal"
            raise ValueError(msg)
        if not self.ordinal_absent and self.ordinal is None:
            msg = (
                "anchor names no ordinal; author the ordinal AEAT printed, or declare "
                "ordinal_absent = true when the design printed the row without one"
            )
            raise ValueError(msg)
        return self


def _coerce_envelope_prefix_role(value: object) -> object:
    """Hydrate the authored TOML token into its one closed envelope role."""
    if isinstance(value, FilingEnvelopePrefixRole):
        return value
    if isinstance(value, str):
        try:
            return FilingEnvelopePrefixRole(value)
        except ValueError as exc:
            raise ValueError(f"unknown envelope prefix role {value!r}") from exc
    raise ValueError("envelope prefix role must be a string")


type FilingEnvelopePrefixRoleValue = Annotated[
    FilingEnvelopePrefixRole,
    BeforeValidator(_coerce_envelope_prefix_role),
]


_PREFIX_ROLE_ORDER: tuple[FilingEnvelopePrefixRole, ...] = tuple(FilingEnvelopePrefixRole)


class EnvelopePrefixField(_StrictModel):
    """One exact source anchor and its non-inferable envelope prefix role."""

    role: FilingEnvelopePrefixRoleValue
    anchor: SemanticMapAnchor


class EnvelopeTotalAnchor(_StrictModel):
    """The parser-owned ``Total: Variable`` marker addressed without a field slot."""

    source_row: int = Field(gt=0)
    source_cell: str | None = Field(default=None, pattern=r"^[A-Z]+[1-9][0-9]*$")
    label: Literal["total"]
    length: Literal["Variable"]


class VariableEnvelopeSemantic(_StrictModel):
    """Hash-pinned semantic and composition authority for one variable envelope.

    The ordinary semantic map deliberately excludes variable-envelope fields.
    This separate contract retains the exact prefix anchors, ordered references
    to the already-owned fixed body records, the relative closer, and the
    parser's variable total marker without turning the wrapper into one more
    fixed-width record.
    """

    source_ref: SourceRefId
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    #: The parser record this wrapper composes. Declared by the map rather than
    #: pinned to one modelo: Modelos 151, 202, 322 and 353 carry the identical
    #: thirteen-anchor 328-byte prefix under their own record identities, so a
    #: literal here made one modelo's envelope the only composable one by
    #: accident rather than by contract.
    record_identity: str = Field(min_length=1)
    #: Which roles this design PRINTS, in source order. Not a fixed count: the
    #: shared ``<AUX>`` grammar is spelled in thirteen rows by Modelo 303 and in
    #: eight by Modelo 200, which fuses the first six into one composed opening
    #: tag. A fixed width here made the thirteen-row spelling the only
    #: expressible one, so a design differing only in how it PRINTS the same
    #: grammar was indistinguishable from one that violates it.
    prefix_fields: tuple[EnvelopePrefixField, ...] = Field(min_length=1)
    body_anchor: SemanticMapAnchor
    body_record_ids: tuple[RecordId, ...] = Field(min_length=1)
    closer_anchor: SemanticMapAnchor
    total_anchor: EnvelopeTotalAnchor

    @model_validator(mode="after")
    def _require_complete_ordered_semantics(self) -> VariableEnvelopeSemantic:
        roles = tuple(field.role for field in self.prefix_fields)
        if len(set(roles)) != len(roles):
            raise ValueError(f"variable envelope {self.record_identity!r} prefix roles must be unique")
        remaining = iter(_PREFIX_ROLE_ORDER)
        if not all(role in remaining for role in roles):
            raise ValueError(
                f"variable envelope {self.record_identity!r} prefix roles must appear in canonical source order",
            )
        anchors = tuple(field.anchor for field in self.prefix_fields)
        if len(set(anchors)) != len(anchors):
            raise ValueError(f"variable envelope {self.record_identity!r} prefix anchors must be unique")
        if self.body_anchor.record_identity != self.record_identity:
            raise ValueError(f"variable envelope body anchor must belong to {self.record_identity!r}")
        if self.closer_anchor.record_identity != self.record_identity:
            raise ValueError(f"variable envelope closer anchor must belong to {self.record_identity!r}")
        if len(set(self.body_record_ids)) != len(self.body_record_ids):
            raise ValueError("variable envelope body record identities must be unique and ordered")
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
    def _compile_projection_ref_through_the_canonical_compiler(cls, value: object) -> object:
        """Compile a still-raw reference, so every persisted boundary round-trips.

        This entry is embedded in the export provenance manifest, which is
        written as JSON and read back by design.  Demanding an already-typed
        reference made that impossible: from JSON a reference can only arrive as
        a mapping.  Delegating to the one canonical compiler keeps the real
        invariant -- every reference was compiled by it -- while giving TOML and
        JSON the same single path.  A malformed payload still refuses there.
        """
        return value if value is None else hydrate_filing_projection_ref(value)

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
    discriminator: RecordDiscriminator | None = None
    """Reviewed runtime record-shape fact, carried unchanged into generated output.

    This is deliberately the existing registry discriminator model rather than
    a second mapping-only vocabulary: the generator neither interprets nor
    derives it.  An authored rule must therefore already satisfy the strict
    production schema that consumes it while parsing filed records.
    """


class SemanticMap(_StrictModel):
    """One authored semantic map for one exact official source design.

    Entries and records are exact parser keys only at this stage.  Exact parser
    joining, uniqueness, catalogue resolution, source applicability, and anomaly
    handling remain later explicit generator contracts.
    """

    modelo: ModeloId
    design_epoch: str = Field(min_length=1)
    source_ref: SourceRefId
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    records: tuple[SemanticMapRecord, ...] = Field(min_length=1)
    entries: tuple[SemanticMapEntry, ...] = Field(min_length=1)
    variable_envelopes: tuple[VariableEnvelopeSemantic, ...] = ()

    @model_validator(mode="after")
    def _require_unique_record_semantics(self) -> SemanticMap:
        mismatched_envelopes = tuple(
            envelope.record_identity
            for envelope in self.variable_envelopes
            if (envelope.source_ref != self.source_ref or envelope.source_sha256 != self.source_sha256)
        )
        if mismatched_envelopes:
            raise ValueError(
                "semantic map variable-envelope identities must match the exact semantic-map source: "
                f"{mismatched_envelopes!r}",
            )
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


def semantic_anchor_key(anchor: SemanticMapAnchor) -> AnchorKey:
    """Return the identity one anchor is matched and de-duplicated by.

    The join and the validation both key anchors, and they must key them the
    SAME way: the join looks an entry up by this tuple while the validation
    decides whether two anchors collide. Two spellings that drift make a pair
    the validation calls distinct unreachable to the join, which then reports
    a missing anchor rather than the collision that caused it.
    """
    return anchor.sheet, anchor.source_row, anchor.source_cell, anchor.ordinal, anchor.record_identity


def semantic_record_key(record: SemanticMapRecord) -> RecordKey:
    """Return the identity one record is matched and de-duplicated by."""
    return record.sheet, record.record_identity
