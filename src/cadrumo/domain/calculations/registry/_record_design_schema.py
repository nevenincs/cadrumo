"""Record-design parser output models."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import ConfigDict, Field, model_validator

from ._schema import RegistryModel

__all__ = [
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
