"""Static Modelo 303 DP30300 envelope declaration compilation.

The generator verifies the official source grammar and carries its typed
declaration into the generated layout.  It never receives a filing period,
product identity value, draft value, body member, payload, digest, or total;
those are filing-instance facts resolved only by the application facade.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cadrumo.core import content_hash_hex
from cadrumo.domain.calculations.registry import (
    ExportLayoutId,
    M303EnvelopePrefixFieldDeclaration,
    M303EnvelopePrefixRole,
    M303FilingEnvelopeDefinition,
    RecordId,
    RegistryValidationError,
    RevisionId,
)

from ._record_design_ir import (
    RecordDesignIntermediateField,
    RecordDesignIntermediateRelativeSuffixMarker,
    RecordDesignIntermediateSource,
    RecordDesignIntermediateVariableEnvelope,
)
from ._semantic_map import M303VariableEnvelopeSemantic, SemanticMapAnchor

__all__ = [
    "M303EnvelopeProvenance",
    "compile_m303_filing_envelope_definition",
    "validate_m303_variable_envelope",
]


_CLOSER_TEMPLATE: Final[str] = '"</T3030AAAAPP0000>"'
_PREFIX_LITERAL_BY_ROLE: Final[dict[M303EnvelopePrefixRole, str]] = {
    M303EnvelopePrefixRole.OPENING_TAG: '"<T"',
    M303EnvelopePrefixRole.MODELO: '"303"',
    M303EnvelopePrefixRole.DISCRIMINANT: '"0"',
    M303EnvelopePrefixRole.RECORD_TYPE: '"0000>"',
    M303EnvelopePrefixRole.AUX_OPENING_TAG: '"<AUX>"',
    M303EnvelopePrefixRole.PRE_PROGRAM_FILLER: "BLANCOS",
    M303EnvelopePrefixRole.BETWEEN_IDENTITIES_FILLER: "BLANCOS",
    M303EnvelopePrefixRole.POST_DEVELOPER_FILLER: "BLANCOS",
    M303EnvelopePrefixRole.AUX_CLOSING_TAG: '"</AUX>"',
}


class _StrictModel(BaseModel):
    """Frozen development-only boundary with no untyped extras."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class M303EnvelopeProvenance(_StrictModel):
    """Static evidence that one generated layout carries the reviewed grammar."""

    schema_version: int = Field(ge=1)
    revision_id: RevisionId
    layout_id: ExportLayoutId
    semantic_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    envelope: M303FilingEnvelopeDefinition
    envelope_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _require_static_attestation(self) -> M303EnvelopeProvenance:
        if self.schema_version != 2:
            raise ValueError("unsupported static M303 filing-envelope provenance schema")
        if self.envelope_sha256 != content_hash_hex(self.envelope.model_dump(mode="json")):
            raise ValueError("M303 filing-envelope provenance digest does not match its typed declaration")
        return self


def compile_m303_filing_envelope_definition(
    semantic: M303VariableEnvelopeSemantic,
    envelope: RecordDesignIntermediateVariableEnvelope,
    *,
    source: RecordDesignIntermediateSource,
    body_record_ids: Sequence[RecordId],
) -> M303FilingEnvelopeDefinition:
    """Compile a source-verified static DP30300 declaration for a layout."""
    validate_m303_variable_envelope(
        semantic,
        envelope,
        source=source,
        body_record_ids=body_record_ids,
    )
    return M303FilingEnvelopeDefinition(
        source_ref=semantic.source_ref,
        source_sha256=semantic.source_sha256,
        record_identity="DP30300",
        prefix_fields=tuple(
            M303EnvelopePrefixFieldDeclaration(role=semantic_field.role, length=parser_field.length)
            for semantic_field, parser_field in zip(semantic.prefix_fields, envelope.prefix_fields, strict=True)
        ),
        body_record_ids=tuple(body_record_ids),
        product_identity_requirement="aeat-product-software-identity-v1",
        closer_derivation="m303-relative-closer-v1",
        total_derivation="m303-emitted-byte-total-v1",
    )


def validate_m303_variable_envelope(
    semantic: M303VariableEnvelopeSemantic,
    envelope: RecordDesignIntermediateVariableEnvelope,
    *,
    source: RecordDesignIntermediateSource,
    body_record_ids: Sequence[RecordId],
) -> None:
    """Require one source-pinned semantic contract to match DP30300 exactly."""
    if semantic.source_ref != source.source_ref or semantic.source_sha256 != source.source_sha256:
        raise RegistryValidationError("M303 variable envelope semantic is not pinned to the exact parser source")
    if envelope.record_identity != semantic.record_identity:
        raise RegistryValidationError(
            f"M303 variable envelope identity {semantic.record_identity!r} does not match parser "
            f"identity {envelope.record_identity!r}",
        )
    if len(envelope.prefix_fields) != 13 or envelope.prefix_extent != 328:
        raise RegistryValidationError("M303 DP30300 envelope must retain its exact thirteen-field 328-byte prefix")
    if len(semantic.prefix_fields) != len(envelope.prefix_fields):
        raise RegistryValidationError("M303 variable envelope semantic prefix count does not match parser output")
    for semantic_field, parser_field in zip(semantic.prefix_fields, envelope.prefix_fields, strict=True):
        _require_same_anchor(semantic_field.anchor, parser_field, subject=semantic_field.role.value)
        _require_source_content(semantic_field.role, parser_field)
    _require_body_anchor(semantic, envelope)
    _require_relative_closer(semantic, envelope)
    _require_total_anchor(semantic, envelope)
    declared_body_record_ids = tuple(semantic.body_record_ids)
    actual_body_record_ids = tuple(body_record_ids)
    if declared_body_record_ids != actual_body_record_ids:
        raise RegistryValidationError(
            "M303 variable envelope body records must match the exact reviewed source order; "
            f"declared={declared_body_record_ids!r}, actual={actual_body_record_ids!r}",
        )


def _require_same_anchor(
    semantic_anchor: SemanticMapAnchor,
    parser_field: RecordDesignIntermediateField,
    *,
    subject: str,
) -> None:
    expected = (
        semantic_anchor.sheet,
        semantic_anchor.source_row,
        semantic_anchor.source_cell,
        semantic_anchor.ordinal,
        semantic_anchor.record_identity,
    )
    actual = (
        parser_field.sheet,
        parser_field.source_row,
        parser_field.source_cell,
        parser_field.ordinal,
        parser_field.record_identity,
    )
    if expected != actual:
        raise RegistryValidationError(
            f"M303 variable envelope {subject} anchor does not match the exact official parser anchor: "
            f"expected={expected!r}, actual={actual!r}",
        )


def _require_source_content(role: M303EnvelopePrefixRole, parser_field: RecordDesignIntermediateField) -> None:
    expected = _PREFIX_LITERAL_BY_ROLE.get(role)
    if expected is not None and parser_field.content != expected:
        raise RegistryValidationError(
            f"M303 variable envelope {role.value} conflicts with exact official content: "
            f"expected={expected!r}, actual={parser_field.content!r}",
        )


def _require_body_anchor(
    semantic: M303VariableEnvelopeSemantic,
    envelope: RecordDesignIntermediateVariableEnvelope,
) -> None:
    anchor = semantic.body_anchor
    actual = (
        envelope.sheet,
        envelope.body_source_row,
        envelope.body_source_cell,
        envelope.body_ordinal,
        envelope.record_identity,
    )
    expected = (
        anchor.sheet,
        anchor.source_row,
        anchor.source_cell,
        anchor.ordinal,
        anchor.record_identity,
    )
    if expected != actual or envelope.body_offset != envelope.prefix_extent + 1 or envelope.body_length != "Variable":
        raise RegistryValidationError("M303 variable envelope body does not retain its exact relative Variable marker")


def _require_relative_closer(
    semantic: M303VariableEnvelopeSemantic,
    envelope: RecordDesignIntermediateVariableEnvelope,
) -> None:
    closing = envelope.closing
    if not isinstance(closing, RecordDesignIntermediateRelativeSuffixMarker):
        raise RegistryValidationError("M303 DP30300 requires one uncomposed 18-byte relative closer")
    anchor = semantic.closer_anchor
    expected = (
        anchor.sheet,
        anchor.source_row,
        anchor.source_cell,
        anchor.ordinal,
        anchor.record_identity,
    )
    actual = (
        envelope.sheet,
        closing.source_row,
        closing.source_cell,
        closing.ordinal,
        envelope.record_identity,
    )
    if expected != actual or closing.offset != "***" or closing.length != 18 or closing.content != _CLOSER_TEMPLATE:
        raise RegistryValidationError(
            "M303 variable envelope relative closer does not match its exact 18-byte source marker",
        )


def _require_total_anchor(
    semantic: M303VariableEnvelopeSemantic,
    envelope: RecordDesignIntermediateVariableEnvelope,
) -> None:
    expected = semantic.total_anchor
    actual = (
        envelope.total_source_row,
        envelope.total_source_cell,
        envelope.total_label,
        envelope.total_length,
    )
    if (expected.source_row, expected.source_cell, expected.label, expected.length) != actual:
        raise RegistryValidationError(
            "M303 variable envelope total anchor does not match the parser Variable total marker",
        )
