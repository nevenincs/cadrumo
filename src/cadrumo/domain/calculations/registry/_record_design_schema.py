"""Record-design parser output models."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import ConfigDict, Field, model_validator

from ._schema import RegistryModel

__all__ = [
    "RecordDesignAuxiliaryEnvelopeHeader",
    "RecordDesignAuxiliaryEnvelopeHeaderField",
    "RecordDesignAuxiliaryEnvelopeHeaderRole",
    "RecordDesignCompositeRelativeClosing",
    "RecordDesignField",
    "RecordDesignRelativeSuffixMarker",
    "RecordDesignSheet",
    "RecordDesignVariableBodyMarker",
    "RecordDesignVariableEnvelope",
    "RecordDesignVariableTotalMarker",
]


class RecordDesignField(RegistryModel):
    """One fixed-width field described by an AEAT record-design sheet."""

    sheet: str
    row: int
    ordinal: int
    offset: int
    length: int
    type_code: str
    complementary: str | None = None
    description: str
    validation: str | None = None
    content: str | None = None


class RecordDesignAuxiliaryEnvelopeHeaderRole(StrEnum):
    """One exact source role in the fixed Modelo 390 page-zero header."""

    OPENING_TAG = "opening_tag"
    MODELO = "modelo"
    DISCRIMINANT = "discriminant"
    FILING_YEAR = "filing_year"
    ANNUAL_PERIOD = "annual_period"
    RECORD_TYPE = "record_type"
    AUXILIARY_OPENING_TAG = "auxiliary_opening_tag"
    PRE_PROGRAM_RESERVED = "pre_program_reserved"
    PROGRAM_IDENTIFIER = "program_identifier"
    BETWEEN_IDENTITIES_RESERVED = "between_identities_reserved"
    SOFTWARE_DEVELOPER_TAX_ID = "software_developer_tax_id"
    POST_DEVELOPER_RESERVED = "post_developer_reserved"
    AUXILIARY_CLOSING_TAG = "auxiliary_closing_tag"


_M390_AUXILIARY_HEADER_ROLES: tuple[RecordDesignAuxiliaryEnvelopeHeaderRole, ...] = tuple(
    RecordDesignAuxiliaryEnvelopeHeaderRole,
)
_M390_AUXILIARY_HEADER_LENGTHS: tuple[int, ...] = (2, 3, 1, 4, 2, 5, 5, 70, 4, 4, 9, 213, 6)
_M390_AUXILIARY_HEADER_CONTENT: tuple[str | None, ...] = (
    'Constante "<T"',
    'Constante "390"',
    'Constante "0"',
    "Nota 2",
    '"0A"',
    '"0000>"',
    '"<AUX>"',
    "BLANCOS",
    "Nota 1",
    "BLANCOS",
    "Nota 1",
    "BLANCOS",
    '"</AUX>"',
)
_M390_AUXILIARY_HEADER_ROWS: tuple[int, ...] = tuple(range(6, 19))
_M390_AUXILIARY_HEADER_ORDINALS: tuple[int, ...] = tuple(range(1, 14))


class RecordDesignAuxiliaryEnvelopeHeaderField(RegistryModel):
    """One exact parser field with its source-proved auxiliary-header role."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    role: RecordDesignAuxiliaryEnvelopeHeaderRole
    field: RecordDesignField


class RecordDesignAuxiliaryEnvelopeHeader(RegistryModel):
    """A source-proved fixed header deliberately outside fixed-record totals.

    The only admitted shape is Modelo 390 page zero's thirteen slots.  Its
    terminal extent is an emitted-byte property, never a parser
    ``declared_total`` for a fixed record.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    sheet: str
    record_identity: str
    fields: tuple[RecordDesignAuxiliaryEnvelopeHeaderField, ...] = Field(min_length=13, max_length=13)
    emitted_extent: Literal[328]

    @model_validator(mode="after")
    def _require_exact_m390_source_shape(self) -> Self:
        raw_fields = tuple(item.field for item in self.fields)
        _validate_auxiliary_header_roles(self.fields)
        _validate_auxiliary_header_lengths(raw_fields)
        _validate_auxiliary_header_content(raw_fields)
        _validate_auxiliary_header_positions(raw_fields)
        _validate_auxiliary_header_extent(raw_fields, self.emitted_extent)
        return self

    @property
    def source_fields(self) -> tuple[RecordDesignField, ...]:
        """Return the thirteen parser fields in their official source order."""
        return tuple(item.field for item in self.fields)


def _validate_auxiliary_header_roles(
    fields: tuple[RecordDesignAuxiliaryEnvelopeHeaderField, ...],
) -> None:
    if tuple(item.role for item in fields) != _M390_AUXILIARY_HEADER_ROLES:
        raise ValueError("auxiliary envelope header does not retain its exact thirteen source roles")


def _validate_auxiliary_header_lengths(fields: tuple[RecordDesignField, ...]) -> None:
    if tuple(field.length for field in fields) != _M390_AUXILIARY_HEADER_LENGTHS:
        raise ValueError("auxiliary envelope header has an unsupported source length sequence")


def _validate_auxiliary_header_content(fields: tuple[RecordDesignField, ...]) -> None:
    if tuple(field.content for field in fields) != _M390_AUXILIARY_HEADER_CONTENT:
        raise ValueError("auxiliary envelope header does not match exact Modelo 390 source content")


def _validate_auxiliary_header_positions(fields: tuple[RecordDesignField, ...]) -> None:
    if tuple(field.row for field in fields) != _M390_AUXILIARY_HEADER_ROWS:
        raise ValueError("auxiliary envelope header does not match exact Modelo 390 source rows")
    if tuple(field.ordinal for field in fields) != _M390_AUXILIARY_HEADER_ORDINALS:
        raise ValueError("auxiliary envelope header does not match exact Modelo 390 source ordinals")


def _validate_auxiliary_header_extent(fields: tuple[RecordDesignField, ...], emitted_extent: int) -> None:
    expected_offset = 1
    for field in fields:
        if field.offset != expected_offset:
            raise ValueError("auxiliary envelope header source geometry is not contiguous")
        expected_offset += field.length
    if expected_offset - 1 != emitted_extent:
        raise ValueError("auxiliary envelope header extent must derive from all thirteen source fields")


class RecordDesignVariableBodyMarker(RegistryModel):
    """Official marker that opens a variable-length composed body."""

    sheet: str
    row: int = Field(gt=0)
    ordinal: int = Field(gt=0)
    offset: int = Field(gt=0)
    length: Literal["Variable"]
    type_code: str
    description: str
    validation: str | None = None
    content: str | None = None


class RecordDesignRelativeSuffixMarker(RegistryModel):
    """Official closing suffix positioned relative to a variable body."""

    sheet: str
    row: int = Field(gt=0)
    ordinal: int = Field(gt=0)
    offset: Literal["***"]
    length: int = Field(gt=0)
    type_code: str
    description: str
    validation: str | None = None
    content: str | None = None


def _validate_m220_closing_part_shape(parts: tuple[RecordDesignRelativeSuffixMarker, ...]) -> None:
    if tuple(part.offset for part in parts) != ("***",) * 6:
        raise ValueError("composite relative closing requires six relative offsets")
    if tuple(part.length for part in parts) != (3, 3, 1, 4, 2, 5):
        raise ValueError("composite relative closing has an unsupported length sequence")
    if tuple(part.type_code.strip().casefold() for part in parts) != ("an",) * 6:
        raise ValueError("composite relative closing requires six alphanumeric parts")
    if tuple(part.content for part in parts) != (
        "</T",
        "220",
        "(*)[A|E|I|0]",
        None,
        "0A",
        "0000>",
    ):
        raise ValueError("composite relative closing does not match the exact Modelo 220 source content")


def _validate_m220_closing_source_sequence(parts: tuple[RecordDesignRelativeSuffixMarker, ...]) -> None:
    if tuple(part.row for part in parts) != tuple(range(parts[0].row, parts[0].row + 6)):
        raise ValueError("composite relative closing source rows are not consecutive")
    if tuple(part.ordinal for part in parts) != tuple(range(parts[0].ordinal, parts[0].ordinal + 6)):
        raise ValueError("composite relative closing ordinals are not consecutive")


class RecordDesignCompositeRelativeClosing(RegistryModel):
    """Exact six-row relative closing declared by Modelo 220 designs."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tag_prefix: RecordDesignRelativeSuffixMarker
    modelo: RecordDesignRelativeSuffixMarker
    discriminant: RecordDesignRelativeSuffixMarker
    filing_year: RecordDesignRelativeSuffixMarker
    period: RecordDesignRelativeSuffixMarker
    tag_suffix: RecordDesignRelativeSuffixMarker

    @model_validator(mode="after")
    def _validate_exact_m220_sequence(self) -> Self:
        parts = self.parts
        _validate_m220_closing_part_shape(parts)
        _validate_m220_closing_source_sequence(parts)
        return self

    @property
    def parts(self) -> tuple[RecordDesignRelativeSuffixMarker, ...]:
        """Return the six source rows in official order without concatenating them."""
        return (
            self.tag_prefix,
            self.modelo,
            self.discriminant,
            self.filing_year,
            self.period,
            self.tag_suffix,
        )


class RecordDesignVariableTotalMarker(RegistryModel):
    """Official declaration that the composed record has variable total length."""

    sheet: str
    row: int = Field(gt=0)
    label: Literal["total"]
    length: Literal["Variable"]


class RecordDesignVariableEnvelope(RegistryModel):
    """Variable composition wrapper, distinct from a fixed-width record."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    prefix_fields: tuple[RecordDesignField, ...] = Field(min_length=1)
    prefix_extent: int = Field(gt=0)
    body: RecordDesignVariableBodyMarker
    closing: RecordDesignRelativeSuffixMarker | RecordDesignCompositeRelativeClosing
    variable_total: RecordDesignVariableTotalMarker


class RecordDesignSheet(RegistryModel):
    """Parsed field rows and declared total length for one workbook sheet."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    fields: tuple[RecordDesignField, ...]
    total_positions: int | None = None
    variable_envelope: RecordDesignVariableEnvelope | None = None
    auxiliary_envelope_header: RecordDesignAuxiliaryEnvelopeHeader | None = None

    @model_validator(mode="after")
    def _require_one_record_composition_kind(self) -> Self:
        if self.variable_envelope is not None and self.auxiliary_envelope_header is not None:
            raise ValueError("record-design sheet cannot be both variable envelope and auxiliary header")
        if self.auxiliary_envelope_header is not None:
            if self.total_positions is not None:
                raise ValueError("auxiliary envelope header must not declare a fixed-record total")
            if self.auxiliary_envelope_header.sheet != self.name:
                raise ValueError("auxiliary envelope header sheet identity does not match its parser sheet")
            if self.auxiliary_envelope_header.record_identity != self.name:
                raise ValueError("auxiliary envelope header record identity does not match its parser sheet")
            if self.auxiliary_envelope_header.source_fields != self.fields:
                raise ValueError("auxiliary envelope header fields must exactly be its parser sheet fields")
        return self
