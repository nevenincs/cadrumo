"""Typed development-only intermediate representation of AEAT record designs.

The official record-design binary remains the coordinate authority.  This
module selects that binary through the registry catalogue and projects the
shipped parser output into a frozen, source-anchored representation for the
export-fragment generator.  It does not read extracted derivatives or parse
the source independently.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from cadrumo.domain.calculations.registry import (
    RecordDesignCompositeRelativeClosing,
    RecordDesignRelativeSuffixMarker,
    RecordDesignSheet,
    RecordDesignVariableEnvelope,
    RegistryValidationError,
    ResolvedRecordDesignBinary,
    SourceReference,
    SourceRefId,
    extract_record_design,
    resolve_record_design_binary,
)

__all__ = [
    "RECORD_DESIGN_INTERMEDIATE_SCHEMA_VERSION",
    "RecordDesignIntermediate",
    "RecordDesignIntermediateCompositeRelativeClosing",
    "RecordDesignIntermediateField",
    "RecordDesignIntermediateRelativeSuffixMarker",
    "RecordDesignIntermediateSheet",
    "RecordDesignIntermediateSource",
    "RecordDesignIntermediateVariableEnvelope",
    "RecordDesignWorkbookFormat",
    "load_record_design_intermediate",
]


RECORD_DESIGN_INTERMEDIATE_SCHEMA_VERSION: Final[int] = 3
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
    ordinal: int = Field(gt=0)
    offset: int = Field(gt=0)
    length: int = Field(gt=0)
    aeat_type: str = Field(min_length=1)
    normalized_description: str = Field(min_length=1)
    validation: str | None = None
    content: str | None = None


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
    total_source_row: int = Field(gt=0)
    total_source_cell: str | None = Field(default=None, pattern=r"^[A-Z]+[1-9][0-9]*$")
    total_label: Literal["total"]
    total_length: Literal["Variable"]


class RecordDesignIntermediate(_StrictModel):
    """Verified source metadata plus the shipped parser's complete output."""

    source: RecordDesignIntermediateSource
    sheets: tuple[RecordDesignIntermediateSheet, ...] = Field(min_length=1)
    variable_envelopes: tuple[RecordDesignIntermediateVariableEnvelope, ...] = ()


def load_record_design_intermediate(
    root: Path,
    sources: Mapping[str, SourceReference],
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
    return _build_record_design_intermediate(resolved, extract_record_design(resolved.path))


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
        if sheet.variable_envelope is None
    )
    variable_envelopes = tuple(
        _intermediate_variable_envelope(sheet.variable_envelope, workbook_format=workbook_format)
        for sheet in parsed_sheets
        if sheet.variable_envelope is not None
    )
    return RecordDesignIntermediate(
        source=source_anchor,
        sheets=sheets,
        variable_envelopes=variable_envelopes,
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
            for field in sheet.fields
        ),
    )


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
        total_source_row=envelope.variable_total.row,
        total_source_cell=_source_cell(envelope.variable_total.row, workbook_format),
        total_label=envelope.variable_total.label,
        total_length=envelope.variable_total.length,
    )


def _intermediate_relative_closing(
    closing: RecordDesignRelativeSuffixMarker | RecordDesignCompositeRelativeClosing,
    *,
    workbook_format: RecordDesignWorkbookFormat,
) -> RecordDesignIntermediateRelativeSuffixMarker | RecordDesignIntermediateCompositeRelativeClosing:
    if isinstance(closing, RecordDesignCompositeRelativeClosing):
        parts = tuple(
            _intermediate_relative_suffix(part, workbook_format=workbook_format) for part in closing.parts
        )
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
