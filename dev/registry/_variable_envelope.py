"""Static variable-envelope declaration compilation, for any modelo.

The generator verifies the official source grammar and carries its typed
declaration into the generated layout.  It never receives a filing period,
product identity value, draft value, body member, payload, digest, or total;
those are filing-instance facts resolved only by the application facade.

MODELO-AGNOSTIC BY CONSTRUCTION. The thirty-five bundled 328-byte envelopes
share one grammar -- a ``<T…>`` record identifier, an ``<AUX>`` block carrying
the product identity between reserved spans, a ``Variable`` body, a relative
closing identifier -- and differ only in which roles a design prints and how
wide each one is. Both of those are facts the design itself declares, so this
module proves the shared grammar and copies the differences rather than
branching on a modelo id. A design whose content contradicts the grammar (the
one known case is Modelo 220's conditional ``(*)[A|E|I|0]`` discriminant)
refuses here, before its layout can reach the filing renderer.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cadrumo.core import content_hash_hex
from cadrumo.domain.calculations.registry import (
    AuxiliaryEnvelopeHeaderDefinition,
    ExportLayoutId,
    FilingEnvelopeCloserDerivation,
    FilingEnvelopeDefinition,
    FilingEnvelopePrefixFieldDeclaration,
    FilingEnvelopePrefixRole,
    FilingEnvelopeTotalDerivation,
    RecordDesignAuxiliaryEnvelopeHeaderRole,
    RecordId,
    RegistryValidationError,
    RevisionId,
)

from ._record_design_ir import (
    RecordDesignIntermediateAuxiliaryEnvelopeHeader,
    RecordDesignIntermediateField,
    RecordDesignIntermediateRelativeSuffixMarker,
    RecordDesignIntermediateSource,
    RecordDesignIntermediateVariableEnvelope,
)
from ._semantic_map import SemanticMapAnchor, VariableEnvelopeSemantic

__all__ = [
    "AUXILIARY_TO_PREFIX_ROLE",
    "FilingEnvelopeProvenance",
    "compile_auxiliary_envelope_header_definition",
    "compile_filing_envelope_definition",
    "validate_variable_envelope",
]


#: The one vocabulary shift between the parser's auxiliary-header role names
#: and the shared prefix grammar the filing renderer resolves. The mapping is
#: total and order-preserving.
AUXILIARY_TO_PREFIX_ROLE: Final[dict[RecordDesignAuxiliaryEnvelopeHeaderRole, FilingEnvelopePrefixRole]] = {
    RecordDesignAuxiliaryEnvelopeHeaderRole.OPENING_TAG: FilingEnvelopePrefixRole.OPENING_TAG,
    RecordDesignAuxiliaryEnvelopeHeaderRole.MODELO: FilingEnvelopePrefixRole.MODELO,
    RecordDesignAuxiliaryEnvelopeHeaderRole.DISCRIMINANT: FilingEnvelopePrefixRole.DISCRIMINANT,
    RecordDesignAuxiliaryEnvelopeHeaderRole.FILING_YEAR: FilingEnvelopePrefixRole.FILING_YEAR,
    RecordDesignAuxiliaryEnvelopeHeaderRole.ANNUAL_PERIOD: FilingEnvelopePrefixRole.PERIOD,
    RecordDesignAuxiliaryEnvelopeHeaderRole.RECORD_TYPE: FilingEnvelopePrefixRole.RECORD_TYPE,
    RecordDesignAuxiliaryEnvelopeHeaderRole.AUXILIARY_OPENING_TAG: FilingEnvelopePrefixRole.AUX_OPENING_TAG,
    RecordDesignAuxiliaryEnvelopeHeaderRole.PRE_PROGRAM_RESERVED: FilingEnvelopePrefixRole.PRE_PROGRAM_FILLER,
    RecordDesignAuxiliaryEnvelopeHeaderRole.PROGRAM_IDENTIFIER: FilingEnvelopePrefixRole.PROGRAM_IDENTIFIER,
    RecordDesignAuxiliaryEnvelopeHeaderRole.BETWEEN_IDENTITIES_RESERVED: (
        FilingEnvelopePrefixRole.BETWEEN_IDENTITIES_FILLER
    ),
    RecordDesignAuxiliaryEnvelopeHeaderRole.SOFTWARE_DEVELOPER_TAX_ID: (
        FilingEnvelopePrefixRole.DEVELOPER_TAX_ID
    ),
    RecordDesignAuxiliaryEnvelopeHeaderRole.POST_DEVELOPER_RESERVED: (
        FilingEnvelopePrefixRole.POST_DEVELOPER_FILLER
    ),
    RecordDesignAuxiliaryEnvelopeHeaderRole.AUXILIARY_CLOSING_TAG: FilingEnvelopePrefixRole.AUX_CLOSING_TAG,
}


def compile_auxiliary_envelope_header_definition(
    headers: tuple[RecordDesignIntermediateAuxiliaryEnvelopeHeader, ...],
    source: RecordDesignIntermediateSource,
) -> AuxiliaryEnvelopeHeaderDefinition:
    """Compile the parser-proved auxiliary header into a static layout declaration.

    The total-less 328-byte page-zero header a design prints ahead of its fixed
    records. It shares the filing envelope's prefix grammar and carries no
    variable body, closer or total: the layout's records are the payload. The
    declaration is compiled entirely from parser-owned intermediate facts, so
    there is no authored map section.
    """
    if len(headers) != 1:
        raise RegistryValidationError(
            f"auxiliary envelope header generation requires exactly one parser-owned header, got {len(headers)}",
        )
    header = headers[0]
    prefix_fields = tuple(
        FilingEnvelopePrefixFieldDeclaration(role=AUXILIARY_TO_PREFIX_ROLE[item.role], length=item.parser_field.length)
        for item in header.fields
    )
    return AuxiliaryEnvelopeHeaderDefinition(
        source_ref=source.source_ref,
        source_sha256=source.source_sha256,
        record_identity=header.record_identity,
        prefix_fields=prefix_fields,
        prefix_extent=header.emitted_extent,
        product_identity_requirement="aeat-product-software-identity-v1",
    )


#: The relative closing identifier every standard design prints, as its own
#: source content: ``</T`` + modelo + discriminant + year + period + record type.
#:
#: TWO official spellings, both admitted. Most designs print the year and period
#: as the literal ``AAAAPP`` placeholders (``"</T3080AAAAPP0000>"``); Modelos 151
#: and 200 print their own exercise concretely instead
#: (``"</T151020230A0000>"``), exactly as they do in the composed opening tag.
#: Neither is asserted against a filing instance -- the instance supplies both,
#: and pinning a design's own exercise would refuse its next edition. What IS
#: asserted is everything the grammar fixes: the tag, the modelo, the
#: discriminant, the record type, and the exact eighteen-byte width.
_CLOSER_RE: Final[re.Pattern[str]] = re.compile(
    r'^"</T(?P<modelo>\d{3})(?P<discriminant>.)(?:AAAA|\d{4})(?:PP|..)(?P<record_type>0000>)"$',
)
_CLOSER_EXTENT: Final[int] = 18

#: The composed seventeen-byte identifier some designs print as ONE row, with
#: the filing year and period spelled concretely rather than as placeholders.
_COMPOSED_OPENING_TAG_RE: Final[re.Pattern[str]] = re.compile(r'^"<T(?P<modelo>\d{3})(?P<discriminant>.)\d{4}..0000>"$')
_COMPOSED_OPENING_TAG_EXTENT: Final[int] = 17

#: The exact discriminant and record type the shared grammar fixes. Modelo 220
#: prints a conditional discriminant instead and is refused by these.
_DISCRIMINANT: Final[str] = "0"
_RECORD_TYPE: Final[str] = "0000>"

#: Source content each role must carry verbatim, where the grammar fixes one.
#: :attr:`FilingEnvelopePrefixRole.MODELO` is absent deliberately: its literal
#: is the design's own modelo, checked against the semantic map instead, and so
#: are the two opening-tag spellings and the closer.
_PREFIX_LITERAL_BY_ROLE: Final[dict[FilingEnvelopePrefixRole, str]] = {
    FilingEnvelopePrefixRole.OPENING_TAG: '"<T"',
    FilingEnvelopePrefixRole.DISCRIMINANT: f'"{_DISCRIMINANT}"',
    FilingEnvelopePrefixRole.RECORD_TYPE: f'"{_RECORD_TYPE}"',
    FilingEnvelopePrefixRole.AUX_OPENING_TAG: '"<AUX>"',
    FilingEnvelopePrefixRole.AUX_CLOSING_TAG: '"</AUX>"',
}

#: Reserved spans, whose emitted bytes are blanks of the field's declared width.
#:
#: Their content cell carries ``BLANCOS`` in most designs and is EMPTY in some
#: (Modelos 200 and 220), which declare the reservation in the row's description
#: instead. Both are admitted and anything else refuses: an emptied cell says
#: nothing, while a cell carrying a real value would mean the reviewer classified
#: a value-bearing row as reserved.
_FILLER_ROLES: Final[frozenset[FilingEnvelopePrefixRole]] = frozenset(
    {
        FilingEnvelopePrefixRole.PRE_PROGRAM_FILLER,
        FilingEnvelopePrefixRole.BETWEEN_IDENTITIES_FILLER,
        FilingEnvelopePrefixRole.POST_DEVELOPER_FILLER,
    },
)
_FILLER_CONTENT: Final[frozenset[str | None]] = frozenset({None, "BLANCOS"})


class _StrictModel(BaseModel):
    """Frozen development-only boundary with no untyped extras."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class FilingEnvelopeProvenance(_StrictModel):
    """Static evidence that one generated layout carries the reviewed grammar."""

    schema_version: int = Field(ge=1)
    revision_id: RevisionId
    layout_id: ExportLayoutId
    semantic_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    envelope: FilingEnvelopeDefinition
    envelope_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _require_static_attestation(self) -> FilingEnvelopeProvenance:
        if self.schema_version != 2:
            raise ValueError("unsupported static filing-envelope provenance schema")
        if self.envelope_sha256 != content_hash_hex(self.envelope.model_dump(mode="json")):
            raise ValueError("filing-envelope provenance digest does not match its typed declaration")
        return self


def compile_filing_envelope_definition(
    semantic: VariableEnvelopeSemantic,
    envelope: RecordDesignIntermediateVariableEnvelope,
    *,
    modelo: str,
    source: RecordDesignIntermediateSource,
    body_record_ids: Sequence[RecordId],
) -> FilingEnvelopeDefinition:
    """Compile a source-verified static envelope declaration for a layout."""
    validate_variable_envelope(
        semantic,
        envelope,
        modelo=modelo,
        source=source,
        body_record_ids=body_record_ids,
    )
    return FilingEnvelopeDefinition(
        source_ref=semantic.source_ref,
        source_sha256=semantic.source_sha256,
        record_identity=semantic.record_identity,
        prefix_fields=tuple(
            FilingEnvelopePrefixFieldDeclaration(role=semantic_field.role, length=parser_field.length)
            for semantic_field, parser_field in zip(semantic.prefix_fields, envelope.prefix_fields, strict=True)
        ),
        prefix_extent=envelope.prefix_extent,
        body_record_ids=tuple(body_record_ids),
        product_identity_requirement="aeat-product-software-identity-v1",
        closer_derivation=FilingEnvelopeCloserDerivation.RELATIVE_CLOSER_V1,
        total_derivation=FilingEnvelopeTotalDerivation.EMITTED_BYTE_TOTAL_V1,
    )


def validate_variable_envelope(
    semantic: VariableEnvelopeSemantic,
    envelope: RecordDesignIntermediateVariableEnvelope,
    *,
    modelo: str,
    source: RecordDesignIntermediateSource,
    body_record_ids: Sequence[RecordId],
) -> None:
    """Require one source-pinned semantic contract to match the parser exactly."""
    if semantic.source_ref != source.source_ref or semantic.source_sha256 != source.source_sha256:
        raise RegistryValidationError("variable envelope semantic is not pinned to the exact parser source")
    if envelope.record_identity != semantic.record_identity:
        raise RegistryValidationError(
            f"variable envelope identity {semantic.record_identity!r} does not match parser "
            f"identity {envelope.record_identity!r}",
        )
    if len(semantic.prefix_fields) != len(envelope.prefix_fields):
        raise RegistryValidationError(
            f"variable envelope {semantic.record_identity!r} semantic prefix count "
            f"{len(semantic.prefix_fields)} does not match parser output {len(envelope.prefix_fields)}",
        )
    declared_extent = sum(field.length for field in envelope.prefix_fields)
    if declared_extent != envelope.prefix_extent:
        raise RegistryValidationError(
            f"variable envelope {semantic.record_identity!r} prefix fields sum to {declared_extent} bytes "
            f"but the parser measured a {envelope.prefix_extent}-byte prefix",
        )
    for semantic_field, parser_field in zip(semantic.prefix_fields, envelope.prefix_fields, strict=True):
        _require_same_anchor(semantic_field.anchor, parser_field, subject=semantic_field.role.value)
        _require_source_content(modelo, semantic_field.role, parser_field)
    _require_body_anchor(semantic, envelope)
    _require_relative_closer(semantic, envelope, modelo=modelo)
    _require_total_anchor(semantic, envelope)
    declared_body_record_ids = tuple(semantic.body_record_ids)
    actual_body_record_ids = tuple(body_record_ids)
    if declared_body_record_ids != actual_body_record_ids:
        raise RegistryValidationError(
            "variable envelope body records must match the exact reviewed source order; "
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
            f"variable envelope {subject} anchor does not match the exact official parser anchor: "
            f"expected={expected!r}, actual={actual!r}",
        )


def _require_source_content(
    modelo: str,
    role: FilingEnvelopePrefixRole,
    parser_field: RecordDesignIntermediateField,
) -> None:
    """Prove one prefix row's official content against the shared grammar."""
    if role is FilingEnvelopePrefixRole.MODELO:
        if parser_field.content != f'"{modelo}"':
            raise RegistryValidationError(
                f"variable envelope modelo row carries {parser_field.content!r}, not the reviewed "
                f"design modelo {modelo!r}",
            )
        return
    if role is FilingEnvelopePrefixRole.COMPOSED_OPENING_TAG:
        _require_composed_opening_tag(modelo, parser_field)
        return
    if role in _FILLER_ROLES:
        if parser_field.content not in _FILLER_CONTENT:
            raise RegistryValidationError(
                f"variable envelope {role.value} is reviewed as a reserved span but its official content "
                f"is {parser_field.content!r}, not a blank cell or 'BLANCOS'",
            )
        return
    expected = _PREFIX_LITERAL_BY_ROLE.get(role)
    if expected is not None and parser_field.content != expected:
        raise RegistryValidationError(
            f"variable envelope {role.value} conflicts with exact official content: "
            f"expected={expected!r}, actual={parser_field.content!r}",
        )


def _require_composed_opening_tag(modelo: str, parser_field: RecordDesignIntermediateField) -> None:
    """Prove a one-row opening identifier spells the same six component roles.

    Its year and period are printed CONCRETELY in the source (``<T200020250A…>``
    names 2025 and the annual period) because the design is published per
    exercise. Neither is asserted here: the filing instance supplies both, and
    pinning the design's own exercise would refuse the very next edition. What
    is asserted is everything the grammar does fix -- the tag, the modelo, the
    discriminant, the record type, and the exact seventeen-byte width.
    """
    match = _COMPOSED_OPENING_TAG_RE.match(parser_field.content or "")
    if match is None:
        raise RegistryValidationError(
            f"variable envelope composed opening tag {parser_field.content!r} is not the official "
            "<T + modelo + discriminant + ejercicio + periodo + tipo + > identifier",
        )
    if match.group("modelo") != modelo:
        raise RegistryValidationError(
            f"variable envelope composed opening tag names modelo {match.group('modelo')!r}, "
            f"not the reviewed design modelo {modelo!r}",
        )
    if match.group("discriminant") != _DISCRIMINANT:
        raise RegistryValidationError(
            f"variable envelope composed opening tag carries discriminant {match.group('discriminant')!r}; "
            f"only the shared-grammar {_DISCRIMINANT!r} is compiled without its own adjudication",
        )
    if parser_field.length != _COMPOSED_OPENING_TAG_EXTENT:
        raise RegistryValidationError(
            f"variable envelope composed opening tag declares {parser_field.length} bytes, "
            f"expected {_COMPOSED_OPENING_TAG_EXTENT}",
        )


def _require_body_anchor(
    semantic: VariableEnvelopeSemantic,
    envelope: RecordDesignIntermediateVariableEnvelope,
) -> None:
    anchor = semantic.body_anchor
    # ``body_ordinal`` stays the marker's genuine ``int`` -- a sequential
    # envelope marker, never a printed field label -- rendered to ``str`` only
    # here, at the boundary with the now-``str`` anchor it is compared against.
    actual = (
        envelope.sheet,
        envelope.body_source_row,
        envelope.body_source_cell,
        str(envelope.body_ordinal),
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
        raise RegistryValidationError(
            f"variable envelope {semantic.record_identity!r} body does not retain its exact relative Variable marker",
        )


def _require_relative_closer(
    semantic: VariableEnvelopeSemantic,
    envelope: RecordDesignIntermediateVariableEnvelope,
    *,
    modelo: str,
) -> None:
    closing = envelope.closing
    if not isinstance(closing, RecordDesignIntermediateRelativeSuffixMarker):
        raise RegistryValidationError(
            f"variable envelope {semantic.record_identity!r} requires one uncomposed "
            f"{_CLOSER_EXTENT}-byte relative closer",
        )
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
        str(closing.ordinal),
        envelope.record_identity,
    )
    if expected != actual or closing.offset != "***" or closing.length != _CLOSER_EXTENT:
        raise RegistryValidationError(
            f"variable envelope {semantic.record_identity!r} relative closer does not match its exact "
            f"{_CLOSER_EXTENT}-byte source anchor",
        )
    match = _CLOSER_RE.match(closing.content or "")
    if match is None:
        raise RegistryValidationError(
            f"variable envelope {semantic.record_identity!r} relative closer {closing.content!r} is not the "
            f"official </T + modelo + discriminant + ejercicio + periodo + tipo + > identifier",
        )
    if match.group("modelo") != modelo:
        raise RegistryValidationError(
            f"variable envelope {semantic.record_identity!r} relative closer names modelo "
            f"{match.group('modelo')!r}, not the reviewed design modelo {modelo!r}",
        )
    if match.group("discriminant") != _DISCRIMINANT:
        raise RegistryValidationError(
            f"variable envelope {semantic.record_identity!r} relative closer carries discriminant "
            f"{match.group('discriminant')!r}; only the shared-grammar {_DISCRIMINANT!r} is compiled "
            "without its own adjudication",
        )


def _require_total_anchor(
    semantic: VariableEnvelopeSemantic,
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
            f"variable envelope {semantic.record_identity!r} total anchor does not match the parser "
            "Variable total marker",
        )
