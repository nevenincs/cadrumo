"""Typed Modelo 303 DP30300 variable-envelope composition and byte rendering.

The official record-design binary owns every source coordinate.  The reviewed
semantic map owns the thirteen prefix roles and body-member order.  This module
only joins those two authorities with an explicit product/software identity; it
does not consult a previous layout, producer key, presenter, taxpayer or
neighbouring design.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cadrumo.core import (
    AeatProductSoftwareIdentity,
    CasillaId,
    Period,
    StandardPeriodCode,
    content_hash_hex,
    sha256_hex,
)
from cadrumo.domain.calculations.registry import RecordId, RegistryValidationError, RevisionId

from ._record_design_ir import (
    RecordDesignIntermediateField,
    RecordDesignIntermediateRelativeSuffixMarker,
    RecordDesignIntermediateSource,
    RecordDesignIntermediateVariableEnvelope,
)
from ._semantic_map import (
    M303EnvelopePrefixRole,
    M303VariableEnvelopeSemantic,
    SemanticMapAnchor,
)

__all__ = [
    "M303EnvelopeBodyMember",
    "M303EnvelopeBodyRecordValues",
    "M303EnvelopeBytes",
    "M303EnvelopeCasillaValue",
    "M303EnvelopeGenerationInput",
    "M303EnvelopeMemberDigest",
    "M303EnvelopeProvenance",
    "render_m303_variable_envelope_bytes",
    "validate_m303_variable_envelope",
]


_CLOSER_TEMPLATE: Final[str] = '"</T3030AAAAPP0000>"'
_M303_STANDARD_PERIODS: Final[frozenset[StandardPeriodCode]] = frozenset(
    {
        StandardPeriodCode.Q1,
        StandardPeriodCode.Q2,
        StandardPeriodCode.Q3,
        StandardPeriodCode.Q4,
        StandardPeriodCode.JAN,
        StandardPeriodCode.FEB,
        StandardPeriodCode.MAR,
        StandardPeriodCode.APR,
        StandardPeriodCode.MAY,
        StandardPeriodCode.JUN,
        StandardPeriodCode.JUL,
        StandardPeriodCode.AUG,
        StandardPeriodCode.SEP,
        StandardPeriodCode.OCT,
        StandardPeriodCode.NOV,
        StandardPeriodCode.DEC,
    },
)
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


class M303EnvelopeBodyMember(_StrictModel):
    """One already-rendered body record addressed by canonical semantic id."""

    record_id: RecordId
    payload: bytes = Field(min_length=1)


class M303EnvelopeCasillaValue(_StrictModel):
    """One explicit in-memory value admitted to a declared DP30300 body record."""

    casilla_id: CasillaId
    value: str | None


class M303EnvelopeBodyRecordValues(_StrictModel):
    """All explicit casilla values for one source-ordered DP30300 body record."""

    record_id: RecordId
    casilla_values: tuple[M303EnvelopeCasillaValue, ...] = ()

    @model_validator(mode="after")
    def _require_unique_casilla_values(self) -> M303EnvelopeBodyRecordValues:
        casilla_ids = tuple(value.casilla_id for value in self.casilla_values)
        if len(set(casilla_ids)) != len(casilla_ids):
            raise ValueError("M303 envelope body record values must not repeat a casilla")
        return self


class M303EnvelopeGenerationInput(_StrictModel):
    """Explicit transient values required to compose one DP30300 envelope."""

    filing_period: Period
    body_records: tuple[M303EnvelopeBodyRecordValues, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _require_m303_period_and_body_order(self) -> M303EnvelopeGenerationInput:
        if self.filing_period.standard_code not in _M303_STANDARD_PERIODS:
            accepted = tuple(str(item) for item in sorted(_M303_STANDARD_PERIODS, key=str))
            raise ValueError(f"M303 envelope period must be one of {accepted!r}")
        record_ids = tuple(record.record_id for record in self.body_records)
        if len(set(record_ids)) != len(record_ids):
            raise ValueError("M303 envelope body record values must be unique and ordered")
        return self


class M303EnvelopeBytes(_StrictModel):
    """The measured byte composition for one fully supplied DP30300 envelope."""

    filing_period: Period
    prefix: bytes = Field(min_length=1)
    body_members: tuple[M303EnvelopeBodyMember, ...] = Field(min_length=1)
    closer: bytes = Field(min_length=1)
    payload: bytes = Field(min_length=1)
    payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    total_length: int = Field(gt=0)

    @model_validator(mode="after")
    def _require_exact_byte_derivation(self) -> M303EnvelopeBytes:
        body = b"".join(member.payload for member in self.body_members)
        expected = self.prefix + body + self.closer
        if self.payload != expected:
            raise ValueError("M303 envelope payload must be its exact prefix, ordered body, and closer concatenation")
        if self.total_length != len(self.payload):
            raise ValueError("M303 envelope total must be derived from emitted bytes")
        if self.payload_sha256 != sha256_hex(self.payload):
            raise ValueError("M303 envelope payload digest must be derived from emitted bytes")
        expected_closer = f"</T3030{self.filing_period.filing_year:04d}{self.filing_period.registry_token}0000>".encode(
            "ascii"
        )
        if self.closer != expected_closer:
            raise ValueError("M303 envelope closer must use the selected filing period")
        return self


class M303EnvelopeMemberDigest(_StrictModel):
    """One source-ordered rendered body member attested by canonical digest."""

    record_id: RecordId
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class M303EnvelopeProvenance(_StrictModel):
    """Static reviewed evidence carried into generated-tree provenance."""

    schema_version: int = Field(ge=1)
    revision_id: RevisionId
    filing_period: Period
    semantic: M303VariableEnvelopeSemantic
    semantic_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    prefix_derivations: tuple[M303EnvelopePrefixRole, ...] = Field(min_length=13, max_length=13)
    body_member_digests: tuple[M303EnvelopeMemberDigest, ...] = Field(min_length=1)
    payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    total_length: int = Field(gt=0)
    product_software_identity: AeatProductSoftwareIdentity
    closer_derivation: str = Field(pattern=r"^m303-relative-closer-v1$")
    total_derivation: str = Field(pattern=r"^m303-emitted-byte-total-v1$")

    @model_validator(mode="after")
    def _require_complete_envelope_attestation(self) -> M303EnvelopeProvenance:
        if self.schema_version != 1:
            raise ValueError("unsupported M303 variable-envelope provenance schema")
        if self.semantic_sha256 != content_hash_hex(self.semantic.model_dump(mode="json")):
            raise ValueError("M303 envelope provenance semantic digest does not match its typed semantic contract")
        if self.prefix_derivations != tuple(field.role for field in self.semantic.prefix_fields):
            raise ValueError("M303 envelope provenance must retain every source-ordered prefix derivation")
        member_ids = tuple(member.record_id for member in self.body_member_digests)
        if member_ids != self.semantic.body_record_ids:
            raise ValueError("M303 envelope provenance body-member digests must retain the reviewed source order")
        if len(set(member_ids)) != len(member_ids):
            raise ValueError("M303 envelope provenance body-member digests must be unique")
        if self.filing_period.standard_code not in _M303_STANDARD_PERIODS:
            raise ValueError("M303 envelope provenance must retain a monthly or quarterly filing period")
        return self


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


def render_m303_variable_envelope_bytes(
    semantic: M303VariableEnvelopeSemantic,
    envelope: RecordDesignIntermediateVariableEnvelope,
    *,
    source: RecordDesignIntermediateSource,
    product_software_identity: AeatProductSoftwareIdentity,
    filing_period: Period,
    body_members: tuple[M303EnvelopeBodyMember, ...],
) -> M303EnvelopeBytes:
    """Render one complete DP30300 envelope and measure its emitted-byte total.

    The caller supplies body bytes only after each member has been rendered by
    its own canonical record writer.  This method merely enforces the authored
    body order and wraps it with the source-proven envelope; it cannot choose,
    generate, omit, or reorder a body record.
    """
    if filing_period.standard_code not in _M303_STANDARD_PERIODS:
        raise RegistryValidationError(
            "M303 envelope period must be an official Modelo 303 monthly or quarterly period, "
            f"got {filing_period.registry_token!r}",
        )
    member_ids = tuple(member.record_id for member in body_members)
    validate_m303_variable_envelope(
        semantic,
        envelope,
        source=source,
        body_record_ids=member_ids,
    )
    prefix_parts = tuple(
        _render_prefix_part(
            semantic_field.role,
            parser_field,
            product_software_identity=product_software_identity,
            filing_period=filing_period,
        )
        for semantic_field, parser_field in zip(semantic.prefix_fields, envelope.prefix_fields, strict=True)
    )
    prefix = b"".join(prefix_parts)
    if len(prefix) != envelope.prefix_extent:
        raise RegistryValidationError(
            f"M303 envelope prefix renders to {len(prefix)} bytes, expected parser extent {envelope.prefix_extent}",
        )
    closer = f"</T3030{filing_period.filing_year:04d}{filing_period.registry_token}0000>".encode("ascii")
    closing = envelope.closing
    assert isinstance(closing, RecordDesignIntermediateRelativeSuffixMarker)
    if len(closer) != closing.length:
        raise RegistryValidationError(
            f"M303 envelope relative closer renders to {len(closer)} bytes, expected {closing.length}",
        )
    payload = prefix + b"".join(member.payload for member in body_members) + closer
    return M303EnvelopeBytes(
        filing_period=filing_period,
        prefix=prefix,
        body_members=body_members,
        closer=closer,
        payload=payload,
        payload_sha256=sha256_hex(payload),
        total_length=len(payload),
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


def _render_prefix_part(
    role: M303EnvelopePrefixRole,
    parser_field: RecordDesignIntermediateField,
    *,
    product_software_identity: AeatProductSoftwareIdentity,
    filing_period: Period,
) -> bytes:
    values: dict[M303EnvelopePrefixRole, str] = {
        M303EnvelopePrefixRole.OPENING_TAG: "<T",
        M303EnvelopePrefixRole.MODELO: "303",
        M303EnvelopePrefixRole.DISCRIMINANT: "0",
        M303EnvelopePrefixRole.FILING_YEAR: f"{filing_period.filing_year:04d}",
        M303EnvelopePrefixRole.PERIOD: filing_period.registry_token,
        M303EnvelopePrefixRole.RECORD_TYPE: "0000>",
        M303EnvelopePrefixRole.AUX_OPENING_TAG: "<AUX>",
        M303EnvelopePrefixRole.PRE_PROGRAM_FILLER: " " * parser_field.length,
        M303EnvelopePrefixRole.PROGRAM_IDENTIFIER: product_software_identity.program_identifier,
        M303EnvelopePrefixRole.BETWEEN_IDENTITIES_FILLER: " " * parser_field.length,
        M303EnvelopePrefixRole.DEVELOPER_TAX_ID: product_software_identity.developer_tax_id,
        M303EnvelopePrefixRole.POST_DEVELOPER_FILLER: " " * parser_field.length,
        M303EnvelopePrefixRole.AUX_CLOSING_TAG: "</AUX>",
    }
    try:
        payload = values[role].encode("ascii")
    except UnicodeEncodeError as exc:
        raise RegistryValidationError(f"M303 variable envelope {role.value} is not ASCII encodable") from exc
    if len(payload) != parser_field.length:
        raise RegistryValidationError(
            f"M303 variable envelope {role.value} renders to {len(payload)} bytes, expected {parser_field.length}",
        )
    return payload
