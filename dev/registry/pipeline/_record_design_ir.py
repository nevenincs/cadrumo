"""Typed development-only intermediate representation of AEAT record designs.

The official record-design binary remains the coordinate authority.  This
module selects that binary through the registry catalogue and projects the
shipped parser output into a frozen, source-anchored representation for the
export-fragment generator.  It does not read extracted derivatives or parse
the source independently.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cadrumo.domain.calculations.registry import (
    AUXILIARY_ENVELOPE_HEADER_LENGTHS,
    AUXILIARY_ENVELOPE_HEADER_ORDINALS,
    AUXILIARY_ENVELOPE_HEADER_ROWS,
    GeneratedArtifactSource,
    RecordDesignAuxiliaryEnvelopeHeader,
    RecordDesignAuxiliaryEnvelopeHeaderRole,
    RecordDesignCompositeRelativeClosing,
    RecordDesignField,
    RecordDesignRelativeSuffixMarker,
    RecordDesignSheet,
    RecordDesignVariableEnvelope,
    RegistryValidationError,
    ResolvedRecordDesignBinary,
    SourceRefId,
    extract_record_design,
    resolve_record_design_binary,
    validate_auxiliary_envelope_header_contents,
)

__all__ = [
    "RECORD_DESIGN_INTERMEDIATE_SCHEMA_VERSION",
    "RecordDesignIntermediate",
    "RecordDesignIntermediateAuxiliaryEnvelopeHeader",
    "RecordDesignIntermediateAuxiliaryEnvelopeHeaderField",
    "RecordDesignIntermediateCompositeRelativeClosing",
    "RecordDesignIntermediateField",
    "RecordDesignIntermediateRelativeSuffixMarker",
    "RecordDesignIntermediateSheet",
    "RecordDesignIntermediateSource",
    "RecordDesignIntermediateVariableEnvelope",
    "RecordDesignWorkbookFormat",
    "load_record_design_intermediate",
]


RECORD_DESIGN_INTERMEDIATE_SCHEMA_VERSION: Final[int] = 4
"""Schema version for the parser-owned intermediate representation.

The provenance contract records this value beside every generated revision. A
shape change must deliberately advance the value rather than making an older
manifest appear to attest to a different parser projection.
"""


class _StrictModel(BaseModel):
    """Frozen development-tool boundary model with no untyped extras."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class RecordDesignWorkbookFormat(StrEnum):
    """Exact official binary formats the shipped parser supports."""

    PDF = "pdf"
    XLS = "xls"
    XLSM = "xlsm"
    XLSX = "xlsx"


class RecordDesignIntermediateSource(_StrictModel):
    """Verified official binary authority for one parsed design epoch."""

    source_ref: SourceRefId
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    workbook_format: RecordDesignWorkbookFormat
    design_epoch: str = Field(min_length=1)


class RecordDesignIntermediateField(_StrictModel):
    """One parser-derived field with its exact official source anchor."""

    sheet: str = Field(min_length=1)
    record_identity: str = Field(min_length=1)
    source_row: int = Field(gt=0)
    source_cell: str | None = Field(default=None, pattern=r"^[A-Z]+[1-9][0-9]*$")
    #: The ordinal AEAT printed, verbatim -- a str because it is a printed LABEL
    #: (``14bis``), never an arithmetic value. Mirrors
    #: :attr:`domain.calculations.registry.RecordDesignField.ordinal`, which this
    #: field is a straight 1:1 projection of.
    ordinal: str | None = None
    offset: int = Field(gt=0)
    length: int = Field(gt=0)
    aeat_type: str = Field(min_length=1)
    normalized_description: str = Field(min_length=1)
    validation: str | None = None
    content: str | None = None


class RecordDesignIntermediateAuxiliaryEnvelopeHeaderField(_StrictModel):
    """One source-anchored role in the fixed Modelo 390 auxiliary header."""

    role: RecordDesignAuxiliaryEnvelopeHeaderRole
    parser_field: RecordDesignIntermediateField


class RecordDesignIntermediateAuxiliaryEnvelopeHeader(_StrictModel):
    """A total-less source-proved M390 header outside fixed-record generation."""

    sheet: str = Field(min_length=1)
    record_identity: str = Field(min_length=1)
    fields: tuple[RecordDesignIntermediateAuxiliaryEnvelopeHeaderField, ...] = Field(min_length=13, max_length=13)
    emitted_extent: Literal[328]

    @model_validator(mode="after")
    def _require_exact_m390_header_shape(self) -> RecordDesignIntermediateAuxiliaryEnvelopeHeader:
        expected_roles = tuple(RecordDesignAuxiliaryEnvelopeHeaderRole)
        if tuple(item.role for item in self.fields) != expected_roles:
            msg = "Modelo 390 auxiliary header roles must retain official source order"
            raise ValueError(msg)

        source_fields = self.source_fields
        if tuple(field.length for field in source_fields) != AUXILIARY_ENVELOPE_HEADER_LENGTHS:
            msg = "Modelo 390 auxiliary header field widths must retain official anchors"
            raise ValueError(msg)
        if tuple(field.offset for field in source_fields) != (1, 3, 6, 7, 11, 13, 18, 23, 93, 97, 101, 110, 323):
            msg = "Modelo 390 auxiliary header offsets must retain official anchors"
            raise ValueError(msg)
        if tuple(field.source_row for field in source_fields) != AUXILIARY_ENVELOPE_HEADER_ROWS:
            msg = "Modelo 390 auxiliary header source rows must retain official anchors"
            raise ValueError(msg)
        if tuple(field.source_cell for field in source_fields) != tuple(
            f"A{row}" for row in AUXILIARY_ENVELOPE_HEADER_ROWS
        ):
            msg = "Modelo 390 auxiliary header source cells must retain official anchors"
            raise ValueError(msg)
        if tuple(field.ordinal for field in source_fields) != AUXILIARY_ENVELOPE_HEADER_ORDINALS:
            msg = "Modelo 390 auxiliary header ordinals must retain official anchors"
            raise ValueError(msg)
        validate_auxiliary_envelope_header_contents(tuple(field.content for field in source_fields))
        if any(field.sheet != self.sheet or field.record_identity != self.record_identity for field in source_fields):
            msg = "Modelo 390 auxiliary header anchors must belong to one source sheet"
            raise ValueError(msg)
        if tuple(field.offset + field.length - 1 for field in source_fields)[-1] != self.emitted_extent:
            msg = "Modelo 390 auxiliary header extent must end at byte 328"
            raise ValueError(msg)
        return self

    @property
    def source_fields(self) -> tuple[RecordDesignIntermediateField, ...]:
        """Return header fields in exact source order."""
        return tuple(item.parser_field for item in self.fields)


class RecordDesignIntermediateSheet(_StrictModel):
    """One exact record identity and its parser-derived fields."""

    sheet: str = Field(min_length=1)
    record_identity: str = Field(min_length=1)
    declared_total: int | None = Field(default=None, gt=0)
    fields: tuple[RecordDesignIntermediateField, ...] = Field(min_length=1)


class RecordDesignIntermediateRelativeSuffixMarker(_StrictModel):
    """One exact parser-owned relative closing row."""

    source_row: int = Field(gt=0)
    source_cell: str | None = Field(default=None, pattern=r"^[A-Z]+[1-9][0-9]*$")
    ordinal: int = Field(gt=0)
    offset: Literal["***"]
    length: int = Field(gt=0)
    aeat_type: str = Field(min_length=1)
    normalized_description: str = Field(min_length=1)
    validation: str | None = None
    content: str | None = None


class RecordDesignIntermediateCompositeRelativeClosing(_StrictModel):
    """Six distinct Modelo 220 closing rows, retained without concatenation."""

    tag_prefix: RecordDesignIntermediateRelativeSuffixMarker
    modelo: RecordDesignIntermediateRelativeSuffixMarker
    discriminant: RecordDesignIntermediateRelativeSuffixMarker
    filing_year: RecordDesignIntermediateRelativeSuffixMarker
    period: RecordDesignIntermediateRelativeSuffixMarker
    tag_suffix: RecordDesignIntermediateRelativeSuffixMarker

    @property
    def parts(self) -> tuple[RecordDesignIntermediateRelativeSuffixMarker, ...]:
        """Return the six exact source rows in official order."""
        return (
            self.tag_prefix,
            self.modelo,
            self.discriminant,
            self.filing_year,
            self.period,
            self.tag_suffix,
        )


class RecordDesignIntermediateVariableEnvelope(_StrictModel):
    """Parser-owned composition wrapper excluded from fixed-record consumers."""

    sheet: str = Field(min_length=1)
    record_identity: str = Field(min_length=1)
    prefix_extent: int = Field(gt=0)
    prefix_fields: tuple[RecordDesignIntermediateField, ...] = Field(min_length=1)
    body_source_row: int = Field(gt=0)
    body_source_cell: str | None = Field(default=None, pattern=r"^[A-Z]+[1-9][0-9]*$")
    body_ordinal: int = Field(gt=0)
    body_offset: int = Field(gt=0)
    body_length: Literal["Variable"]
    body_aeat_type: str = Field(min_length=1)
    body_normalized_description: str = Field(min_length=1)
    body_validation: str | None = None
    body_content: str | None = None
    closing: RecordDesignIntermediateRelativeSuffixMarker | RecordDesignIntermediateCompositeRelativeClosing
    #: The physical end-of-record marker, carried through rather than dropped.
    #: The parser separates it from the closing identifier because the two are
    #: different things; if the projection then omitted it, every record built from
    #: this intermediate would be two bytes shorter than AEAT declares, and the
    #: separation would have bought a clean-looking wrong answer instead of a
    #: refusal.
    terminator: RecordDesignIntermediateRelativeSuffixMarker | None = None
    total_source_row: int = Field(gt=0)
    total_source_cell: str | None = Field(default=None, pattern=r"^[A-Z]+[1-9][0-9]*$")
    total_label: Literal["total"]
    total_length: Literal["Variable"]


class RecordDesignIntermediate(_StrictModel):
    """Verified source metadata plus the shipped parser's complete output."""

    source: RecordDesignIntermediateSource
    sheets: tuple[RecordDesignIntermediateSheet, ...] = Field(min_length=1)
    variable_envelopes: tuple[RecordDesignIntermediateVariableEnvelope, ...] = ()
    auxiliary_envelope_headers: tuple[RecordDesignIntermediateAuxiliaryEnvelopeHeader, ...] = ()

    @model_validator(mode="after")
    def _require_disjoint_record_composition_roles(self) -> RecordDesignIntermediate:
        fixed = {sheet.record_identity for sheet in self.sheets}
        variable = {envelope.record_identity for envelope in self.variable_envelopes}
        headers = {header.record_identity for header in self.auxiliary_envelope_headers}
        composition_lengths = (len(self.sheets), len(self.variable_envelopes), len(self.auxiliary_envelope_headers))
        if (len(fixed), len(variable), len(headers)) != composition_lengths:
            msg = "record design composition identities must each be unique"
            raise ValueError(msg)
        if fixed & variable or fixed & headers or variable & headers:
            msg = "fixed records, variable envelopes, and auxiliary headers must be disjoint"
            raise ValueError(msg)
        return self


def load_record_design_intermediate(
    root: Path,
    sources: Mapping[str, GeneratedArtifactSource],
    *,
    source_ref: str,
    filing_year: int,
    design_epoch: str,
) -> RecordDesignIntermediate:
    """Load one hash-verified official design through the shipped parser only."""
    resolved = resolve_record_design_binary(
        root,
        sources,
        source_ref=source_ref,
        filing_year=filing_year,
        design_epoch=design_epoch,
    )
    # REQUIRES A COMPLETE READ, unlike the coverage derivation, and the asymmetry
    # is deliberate. This intermediate is what the export-tree generator authors a
    # revision's byte layout from, so a design read only in part would produce a
    # layout that is internally consistent, digest-valid, and missing whole
    # records -- the failure the fixed-width completeness gate exists to catch,
    # arriving through the generator instead of past it.
    return _build_record_design_intermediate(resolved, extract_record_design(resolved.path).require_complete())


def _build_record_design_intermediate(
    resolved: ResolvedRecordDesignBinary,
    parsed_sheets: tuple[RecordDesignSheet, ...],
) -> RecordDesignIntermediate:
    """Project already-parsed official fields without reinterpreting coordinates."""
    source = resolved.source
    if source.kind != "record_design":
        raise RegistryValidationError(f"source {source.id!r} is not a record-design binary")
    if source.record_design_epoch is None:
        raise RegistryValidationError(f"record-design source {source.id!r} does not declare a design epoch")
    if not resolved.path.is_file():
        raise RegistryValidationError(f"record-design source {source.id!r} has no readable binary")
    if not parsed_sheets:
        raise RegistryValidationError(f"record-design source {source.id!r} produced no parsed sheets")
    if len({sheet.name for sheet in parsed_sheets}) != len(parsed_sheets):
        raise RegistryValidationError(f"record-design source {source.id!r} produced duplicate sheet identities")

    workbook_format = _workbook_format(resolved.path)
    source_anchor = RecordDesignIntermediateSource(
        source_ref=str(source.id),
        source_sha256=source.sha256,
        workbook_format=workbook_format,
        design_epoch=source.record_design_epoch,
    )
    sheets = tuple(
        _intermediate_sheet(sheet, workbook_format=workbook_format)
        for sheet in parsed_sheets
        if sheet.variable_envelope is None and sheet.auxiliary_envelope_header is None
    )
    variable_envelopes = tuple(
        _intermediate_variable_envelope(sheet.variable_envelope, workbook_format=workbook_format)
        for sheet in parsed_sheets
        if sheet.variable_envelope is not None
    )
    auxiliary_envelope_headers = tuple(
        _intermediate_auxiliary_envelope_header(sheet.auxiliary_envelope_header, workbook_format=workbook_format)
        for sheet in parsed_sheets
        if sheet.auxiliary_envelope_header is not None
    )
    return RecordDesignIntermediate(
        source=source_anchor,
        sheets=sheets,
        variable_envelopes=variable_envelopes,
        auxiliary_envelope_headers=auxiliary_envelope_headers,
    )


def _workbook_format(path: Path) -> RecordDesignWorkbookFormat:
    try:
        return RecordDesignWorkbookFormat(path.suffix.lower().removeprefix("."))
    except ValueError as exc:
        raise RegistryValidationError(f"unsupported record-design source extension: {path.suffix}") from exc


def _intermediate_sheet(
    sheet: RecordDesignSheet,
    *,
    workbook_format: RecordDesignWorkbookFormat,
) -> RecordDesignIntermediateSheet:
    if not sheet.fields:
        raise RegistryValidationError(f"record-design sheet {sheet.name!r} contains no parsed fields")
    return RecordDesignIntermediateSheet(
        sheet=sheet.name,
        record_identity=sheet.name,
        declared_total=sheet.total_positions,
        fields=tuple(
            RecordDesignIntermediateField(
                sheet=sheet.name,
                record_identity=sheet.name,
                source_row=field.row,
                source_cell=_source_cell(field.row, workbook_format),
                ordinal=field.ordinal,
                offset=field.offset,
                length=field.length,
                aeat_type=field.type_code,
                normalized_description=field.description,
                validation=field.validation,
                content=field.content,
            )
            for field in _wire_positions(sheet.fields)
        ),
    )


def _wire_positions(fields: Sequence[RecordDesignField]) -> list[RecordDesignField]:
    """Return the LEAF positions of ``fields``, descending into every desglose.

    Where AEAT desglosa a printed row into sub-fields, the sub-fields are the
    wire positions and the parent's span is not one -- the same resolution
    ``_required_positions`` applies in the coverage validator. Emitting the
    parent instead would hand the renderer one field spanning the whole group,
    which is the Modelo 576 blob: it covers every sub-position by byte extent, so
    coverage cannot object, while writing the group as a single value and
    claiming any bytes AEAT reserves inside it.

    This must descend, not merely tolerate: the parser only began nesting these
    when it learned to read a desglose AEAT prints WITHOUT dotted ordinals, and
    before that the children arrived here as flat siblings and the geometry check
    refused the record outright. Refusing was safe. Silently rendering the parent
    as one field would not be, so the nesting the parser gained has to be spent
    here rather than ignored.
    """
    positions: list[RecordDesignField] = []
    for field in fields:
        if field.components:
            positions.extend(_wire_positions(field.components))
            continue
        positions.append(field)
    return positions


def _source_cell(row: int, workbook_format: RecordDesignWorkbookFormat) -> str | None:
    """Return the parser's ordinal-column anchor where the binary is a workbook."""
    if workbook_format in {
        RecordDesignWorkbookFormat.XLS,
        RecordDesignWorkbookFormat.XLSM,
        RecordDesignWorkbookFormat.XLSX,
    }:
        return f"A{row}"
    return None


def _intermediate_variable_envelope(
    envelope: RecordDesignVariableEnvelope,
    *,
    workbook_format: RecordDesignWorkbookFormat,
) -> RecordDesignIntermediateVariableEnvelope:
    return RecordDesignIntermediateVariableEnvelope(
        sheet=envelope.name,
        record_identity=envelope.name,
        prefix_extent=envelope.prefix_extent,
        prefix_fields=tuple(
            RecordDesignIntermediateField(
                sheet=envelope.name,
                record_identity=envelope.name,
                source_row=field.row,
                source_cell=_source_cell(field.row, workbook_format),
                ordinal=field.ordinal,
                offset=field.offset,
                length=field.length,
                aeat_type=field.type_code,
                normalized_description=field.description,
                validation=field.validation,
                content=field.content,
            )
            for field in envelope.prefix_fields
        ),
        body_source_row=envelope.body.row,
        body_source_cell=_source_cell(envelope.body.row, workbook_format),
        body_ordinal=envelope.body.ordinal,
        body_offset=envelope.body.offset,
        body_length=envelope.body.length,
        body_aeat_type=envelope.body.type_code,
        body_normalized_description=envelope.body.description,
        body_validation=envelope.body.validation,
        body_content=envelope.body.content,
        closing=_intermediate_relative_closing(envelope.closing, workbook_format=workbook_format),
        terminator=(
            None
            if envelope.terminator is None
            else _intermediate_relative_suffix(envelope.terminator, workbook_format=workbook_format)
        ),
        total_source_row=envelope.variable_total.row,
        total_source_cell=_source_cell(envelope.variable_total.row, workbook_format),
        total_label=envelope.variable_total.label,
        total_length=envelope.variable_total.length,
    )


def _intermediate_auxiliary_envelope_header(
    header: RecordDesignAuxiliaryEnvelopeHeader,
    *,
    workbook_format: RecordDesignWorkbookFormat,
) -> RecordDesignIntermediateAuxiliaryEnvelopeHeader:
    """Project the parser-owned total-less header without inventing a total."""
    return RecordDesignIntermediateAuxiliaryEnvelopeHeader(
        sheet=header.sheet,
        record_identity=header.record_identity,
        fields=tuple(
            RecordDesignIntermediateAuxiliaryEnvelopeHeaderField(
                role=item.role,
                parser_field=RecordDesignIntermediateField(
                    sheet=header.sheet,
                    record_identity=header.record_identity,
                    source_row=item.field.row,
                    source_cell=_source_cell(item.field.row, workbook_format),
                    ordinal=item.field.ordinal,
                    offset=item.field.offset,
                    length=item.field.length,
                    aeat_type=item.field.type_code,
                    normalized_description=item.field.description,
                    validation=item.field.validation,
                    content=item.field.content,
                ),
            )
            for item in header.fields
        ),
        emitted_extent=header.emitted_extent,
    )


def _intermediate_relative_closing(
    closing: RecordDesignRelativeSuffixMarker | RecordDesignCompositeRelativeClosing,
    *,
    workbook_format: RecordDesignWorkbookFormat,
) -> RecordDesignIntermediateRelativeSuffixMarker | RecordDesignIntermediateCompositeRelativeClosing:
    if isinstance(closing, RecordDesignCompositeRelativeClosing):
        parts = tuple(_intermediate_relative_suffix(part, workbook_format=workbook_format) for part in closing.parts)
        return RecordDesignIntermediateCompositeRelativeClosing(
            tag_prefix=parts[0],
            modelo=parts[1],
            discriminant=parts[2],
            filing_year=parts[3],
            period=parts[4],
            tag_suffix=parts[5],
        )
    return _intermediate_relative_suffix(closing, workbook_format=workbook_format)


def _intermediate_relative_suffix(
    suffix: RecordDesignRelativeSuffixMarker,
    *,
    workbook_format: RecordDesignWorkbookFormat,
) -> RecordDesignIntermediateRelativeSuffixMarker:
    return RecordDesignIntermediateRelativeSuffixMarker(
        source_row=suffix.row,
        source_cell=_source_cell(suffix.row, workbook_format),
        ordinal=suffix.ordinal,
        offset=suffix.offset,
        length=suffix.length,
        aeat_type=suffix.type_code,
        normalized_description=suffix.description,
        validation=suffix.validation,
        content=suffix.content,
    )
